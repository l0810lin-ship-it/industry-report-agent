#!/usr/bin/env python3
"""Normalize discovery output, deduplicate it, and deep-read source URLs."""

from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from pipeline_lock import pipeline_stage_lock


AGENT_DIR = Path(os.environ.get("AGENT_DIR", Path(__file__).resolve().parent.parent))
RAW_DIR = AGENT_DIR / "output" / "raw"
CONFIG = json.loads((AGENT_DIR / "config.json").read_text(encoding="utf-8"))
RELEVANCE_STOP_TERMS = {
    "市场", "行业", "分析", "报告", "研究", "发展", "趋势", "官方", "中国", "海外",
    "本地", "生活", "平台", "公司", "企业", "产品", "服务", "2024", "2025", "2026",
    "the", "and", "for", "with", "from", "official", "market", "industry", "report",
    "analysis", "strategy", "local", "services", "results", "china",
}


def canonical_url(url: str) -> str:
    try:
        parsed = urllib.parse.urlsplit(url.strip())
        query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        query = [(k, v) for k, v in query if not k.lower().startswith(("utm_", "spm", "ref"))]
        return urllib.parse.urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip("/"), urllib.parse.urlencode(query), ""))
    except ValueError:
        return url.strip()


def parse_exa(raw: str) -> list[dict]:
    records = []
    for block in re.split(r"(?m)(?=^Title:\s*)", raw or ""):
        if not block.startswith("Title:"):
            continue
        fields = {}
        for key in ("Title", "URL", "Published", "Author"):
            match = re.search(rf"(?m)^{key}:\s*(.*)$", block)
            fields[key.lower()] = match.group(1).strip() if match else ""
        highlight = re.search(r"(?ms)^Highlights:\s*(.*)$", block)
        fields["summary"] = highlight.group(1).strip() if highlight else ""
        if fields["title"] or fields["url"]:
            records.append(fields)
    return records


def domain_type(url: str, platform: str = "") -> tuple[str, str, str]:
    domain = urllib.parse.urlsplit(url).netloc.lower().removeprefix("www.") if url else platform
    rules = CONFIG.get("source_rules", {})
    groups = (
        ("official", rules.get("official_domains", [])),
        ("regulatory", rules.get("regulatory_domains", [])),
        ("research", rules.get("research_domains", [])),
        ("media", rules.get("media_domains", [])),
    )
    if platform:
        return domain, "community", domain or platform
    for source_type, domains in groups:
        if any(domain == item or domain.endswith(f".{item}") for item in domains):
            family = next(item for item in domains if domain == item or domain.endswith(f".{item}"))
            return domain, source_type, family
    return domain, "web", domain


def fetch_reader(url: str, timeout: int, max_chars: int) -> tuple[str, str]:
    if not url.startswith(("http://", "https://")):
        return "deep_read_failed", "无有效 HTTP URL"
    reader_url = f"https://r.jina.ai/{url}"
    request = urllib.request.Request(reader_url, headers={"User-Agent": "industry-report-agent/0.9"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            content = response.read(max_chars * 3).decode("utf-8", errors="replace").strip()
        if len(content) < 200:
            return "deep_read_failed", f"正文过短（{len(content)} 字符）"
        return "deep_read", content[:max_chars]
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        return "deep_read_failed", str(exc)[:500]


def result_origin(result: dict) -> str:
    return "direct" if str(result.get("backend", "")).startswith("Direct authoritative URL") else "search"


def meaningful_terms(value: str) -> set[str]:
    value = str(value or "").lower()
    terms = set(re.findall(r"[a-z0-9][a-z0-9.+-]{2,}", value))
    for run in re.findall(r"[\u4e00-\u9fff]{2,}", value):
        if len(run) <= 6:
            terms.add(run)
        terms.update(run[index:index + 2] for index in range(len(run) - 1))
    return {term for term in terms if term not in RELEVANCE_STOP_TERMS}


def assess_relevance(item: dict) -> tuple[str, float, str]:
    origins = set(item.get("source_origins", []))
    if "direct" in origins:
        return "anchor", 1.0, "planned authoritative source"
    if "community" in origins:
        return "relevant", 1.0, "selected platform result"

    text = " ".join([
        item.get("title", ""), item.get("discovery_excerpt", ""), item.get("url", "")
    ]).lower()
    query = str(item.get("query", ""))
    query_terms = meaningful_terms(query)
    text_terms = meaningful_terms(text)
    query_overlap = query_terms & text_terms

    target = CONFIG.get("target", {})
    anchors = [item.get("entity", ""), target.get("company", ""), target.get("industry", "")]
    anchor_hit = next((
        str(anchor).strip() for anchor in anchors
        if len(str(anchor).strip()) >= 2 and str(anchor).strip().lower() in text
    ), "")
    topic_terms = meaningful_terms(" ".join(str(anchor) for anchor in anchors))
    topic_overlap = topic_terms & text_terms
    denominator = max(1, min(8, len(query_terms)))
    score = round(min(1.0, (len(query_overlap) + 0.5 * len(topic_overlap)) / denominator), 4)

    if anchor_hit:
        return "relevant", max(score, 0.75), f"anchor match: {anchor_hit}"
    if len(query_overlap) >= 2:
        return "relevant", score, f"query term overlap: {', '.join(sorted(query_overlap)[:6])}"
    if query_overlap and topic_overlap:
        return "relevant", score, "query and topic terms both matched"
    return "rejected_low_relevance", score, "no anchor match and insufficient query/topic overlap"


def add_exa_candidates(candidates: list[dict], result: dict, stage: str, entity: str = "") -> None:
    origin = result_origin(result)
    for item in parse_exa(result.get("raw_evidence", "")):
        candidates.append({
            "stage": stage,
            "entity": entity,
            "platform": "",
            "query": result.get("query", ""),
            "question_ids": result.get("question_ids", []),
            "hypothesis_ids": result.get("hypothesis_ids", []),
            "trend_ids": result.get("trend_ids", []),
            "module_ids": result.get("module_ids", []),
            "query_stance": result.get("stance", "neutral"),
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "published_at": item.get("published", ""),
            "author": item.get("author", ""),
            "discovery_excerpt": item.get("summary", ""),
            "source_origins": [origin],
            "discovery_backends": [str(result.get("backend", "unknown"))],
        })


def _main() -> int:
    industry = json.loads((RAW_DIR / "industry_data.json").read_text(encoding="utf-8"))
    competitors = json.loads((RAW_DIR / "competitor_data.json").read_text(encoding="utf-8"))
    social = json.loads((RAW_DIR / "social_data.json").read_text(encoding="utf-8"))
    candidates: list[dict] = []

    for result in industry.get("direct_results", []):
        add_exa_candidates(
            candidates,
            result,
            result.get("direct_stage", "industry"),
            result.get("direct_entity", ""),
        )
    for result in industry.get("search_results", []):
        add_exa_candidates(candidates, result, "industry")
    for group in industry.get("focus_results", []):
        for result in group.get("results", []):
            add_exa_candidates(candidates, result, "focus", group.get("label", ""))
    for competitor, payload in competitors.get("competitors", {}).items():
        for result in payload.get("queries", []):
            add_exa_candidates(candidates, result, "competitor", competitor)
    for platform, query_results in social.get("platforms", {}).items():
        for result in query_results:
            items = result.get("items", [])
            if isinstance(items, dict):
                items = items.get("items", items.get("data", [items]))
            for item in items:
                if not isinstance(item, dict):
                    continue
                candidates.append({
                    "stage": "community", "entity": "", "platform": platform,
                    "query": result.get("query", ""), "question_ids": result.get("question_ids", []),
                    "hypothesis_ids": result.get("hypothesis_ids", []),
                    "trend_ids": result.get("trend_ids", []),
                    "module_ids": result.get("module_ids", []),
                    "query_stance": result.get("stance", "neutral"),
                    "title": item.get("title", item.get("desc", item.get("text", ""))),
                    "url": item.get("url", ""), "published_at": item.get("published_at", item.get("created_at", "")),
                    "author": item.get("author", ""),
                    "discovery_excerpt": json.dumps(item, ensure_ascii=False),
                    "source_origins": ["community"],
                    "discovery_backends": [f"OpenCLI:{platform}"],
                })

    raw_candidate_count = len(candidates)
    rejected_candidates = []
    relevant_candidates = []
    for item in candidates:
        status, score, reason = assess_relevance(item)
        item["relevance_status"] = status
        item["relevance_score"] = score
        item["relevance_reason"] = reason
        if status == "rejected_low_relevance":
            rejected_candidates.append({
                "title": item.get("title", ""), "url": item.get("url", ""),
                "query": item.get("query", ""), "stage": item.get("stage", ""),
                "entity": item.get("entity", ""), "relevance_score": score,
                "rejection_reason": reason,
            })
        else:
            relevant_candidates.append(item)
    candidates = relevant_candidates

    deduped = {}
    for item in candidates:
        item["url"] = canonical_url(item.get("url", ""))
        identity = item["url"] or re.sub(r"\s+", " ", item.get("title", "").strip().lower())
        if not identity:
            continue
        if identity in deduped:
            existing = deduped[identity]
            existing["question_ids"] = sorted(set(existing["question_ids"] + item["question_ids"]))
            existing["hypothesis_ids"] = sorted(set(existing.get("hypothesis_ids", []) + item.get("hypothesis_ids", [])))
            existing["trend_ids"] = sorted(set(existing.get("trend_ids", []) + item.get("trend_ids", [])))
            existing["module_ids"] = sorted(set(existing.get("module_ids", []) + item.get("module_ids", [])))
            existing["query_stances"] = sorted(set(existing.get("query_stances", []) + [item.get("query_stance", "neutral")]))
            existing["queries"] = sorted(set(existing["queries"] + [item["query"]]))
            existing["source_origins"] = sorted(set(existing.get("source_origins", []) + item.get("source_origins", [])))
            existing["discovery_backends"] = sorted(set(existing.get("discovery_backends", []) + item.get("discovery_backends", [])))
            continue
        item["query_stances"] = [item.pop("query_stance", "neutral")]
        item["queries"] = [item.pop("query")]
        deduped[identity] = item

    records = list(deduped.values())
    primary_types = {"official", "regulatory", "research"}
    for item in records:
        item["domain"], item["source_type"], item["source_family"] = domain_type(item["url"], item["platform"])
        item["is_primary"] = item["source_type"] in primary_types
        item["read_status"] = "structured_platform_result" if item["platform"] else "search_result_only"
        item["content_excerpt"] = ""
        item["read_error"] = ""

    collection = CONFIG.get("collection", {})
    max_reads = int(collection["max_deep_reads"])
    timeout = int(collection.get("deep_read_timeout_seconds", 20))
    max_chars = int(collection.get("deep_read_max_chars", 12000))
    priorities = {"official": 0, "regulatory": 0, "research": 1, "media": 2, "web": 3, "community": 4}
    readable = [item for item in records if item["url"]]
    readable.sort(key=lambda item: (
        priorities.get(item["source_type"], 9),
        0 if "direct" in item.get("source_origins", []) else 1,
        0 if item["question_ids"] else 1,
    ))
    selected = []
    selected_ids = set()

    def select_first(predicate) -> None:
        if len(selected) >= max_reads:
            return
        candidate = next((item for item in readable if predicate(item) and id(item) not in selected_ids), None)
        if candidate:
            selected.append(candidate)
            selected_ids.add(id(candidate))

    configured_questions = []
    for index, question in enumerate(CONFIG.get("research_questions", []), start=1):
        configured_questions.append(str(question.get("id", f"RQ{index}")) if isinstance(question, dict) else f"RQ{index}")
    mode = str(CONFIG["research_mode"]).lower()
    minimum_search_reads = {"flash": 1, "standard": 4, "deep": 10}[mode]
    search_readable = [item for item in readable if "search" in item.get("source_origins", [])]
    for question_id in configured_questions:
        select_first(
            lambda item, qid=question_id:
            "search" in item.get("source_origins", []) and qid in item["question_ids"]
        )
        if len([item for item in selected if "search" in item.get("source_origins", [])]) >= minimum_search_reads:
            break
    for item in search_readable:
        if len(selected) >= max_reads:
            break
        if len([entry for entry in selected if "search" in entry.get("source_origins", [])]) >= minimum_search_reads:
            break
        if id(item) not in selected_ids:
            selected.append(item)
            selected_ids.add(id(item))
    for question_id in configured_questions:
        select_first(lambda item, qid=question_id: qid in item["question_ids"])
    module_targets = {
        "trend_inference": 3,
        "geographic_sequencing": 3,
        "market_concentration": 2,
        "real_case_studies": 5 if mode == "deep" else 3,
        "benchmark_ranges": 2,
        "stress_test": 1,
    }
    for module_id in CONFIG.get("research_design", {}).get("active_modules", []):
        module_id = str(module_id)
        already_selected = sum(module_id in item.get("module_ids", []) for item in selected)
        for _ in range(max(0, module_targets.get(module_id, 1) - already_selected)):
            select_first(lambda item, mid=module_id: mid in item.get("module_ids", []))
    for hypothesis in CONFIG.get("user_hypotheses", []):
        if not isinstance(hypothesis, dict) or not hypothesis.get("must_test", True):
            continue
        hypothesis_id = str(hypothesis.get("id", ""))
        for stance in ("support", "disconfirm"):
            select_first(
                lambda item, hid=hypothesis_id, target_stance=stance:
                hid in item.get("hypothesis_ids", []) and target_stance in item.get("query_stances", [])
            )
    for trend in CONFIG.get("research_design", {}).get("candidate_trends", []):
        if not isinstance(trend, dict):
            continue
        trend_id = str(trend.get("id", ""))
        for stance in ("support", "disconfirm"):
            select_first(
                lambda item, tid=trend_id, target_stance=stance:
                tid in item.get("trend_ids", []) and target_stance in item.get("query_stances", [])
            )
    for item in readable:
        if len(selected) >= max_reads:
            break
        if id(item) not in selected_ids:
            selected.append(item)
            selected_ids.add(id(item))
    for item in selected:
        status, content = fetch_reader(item["url"], timeout, max_chars)
        item["read_status"] = status
        if status == "deep_read":
            item["content_excerpt"] = content
        else:
            item["read_error"] = content

    for index, item in enumerate(records, start=1):
        digest = hashlib.sha1((item["url"] or item["title"]).encode("utf-8")).hexdigest()[:10]
        item["evidence_id"] = f"EV-{index:04d}-{digest}"
        if item["read_status"] == "deep_read":
            item["evidence_status"] = "verified_source_body"
            item["evidence_strength"] = "high" if item["is_primary"] else "medium"
        elif item["read_status"] == "structured_platform_result":
            item["evidence_status"] = "structured_lead"
            item["evidence_strength"] = "medium"
        else:
            item["evidence_status"] = "lead_only"
            item["evidence_strength"] = "low"

    ledger = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "target": CONFIG.get("target", {}),
        "summary": {
            "raw_candidates": raw_candidate_count,
            "relevant_candidates": len(candidates),
            "rejected_low_relevance": len(rejected_candidates),
            "candidates": len(candidates), "deduplicated": len(records),
            "direct_candidates": sum("direct" in item.get("source_origins", []) for item in records),
            "search_candidates": sum("search" in item.get("source_origins", []) for item in records),
            "community_candidates": sum("community" in item.get("source_origins", []) for item in records),
            "deep_read": sum(item["read_status"] == "deep_read" for item in records),
            "search_deep_read": sum(
                item["read_status"] == "deep_read" and "search" in item.get("source_origins", [])
                for item in records
            ),
            "deep_read_failed": sum(item["read_status"] == "deep_read_failed" for item in records),
            "lead_only": sum(item["evidence_status"] == "lead_only" for item in records),
        },
        "rejected_candidates": rejected_candidates,
        "evidence": records,
    }
    output = RAW_DIR / "evidence_ledger.json"
    output.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"原始候选 {raw_candidate_count} 条，相关候选 {len(candidates)} 条，"
        f"低相关淘汰 {len(rejected_candidates)} 条，去重后 {len(records)} 条，"
        f"原文深读 {ledger['summary']['deep_read']} 条"
    )
    return 0


def main() -> int:
    with pipeline_stage_lock(AGENT_DIR, "enrich_evidence"):
        return _main()


if __name__ == "__main__":
    raise SystemExit(main())
