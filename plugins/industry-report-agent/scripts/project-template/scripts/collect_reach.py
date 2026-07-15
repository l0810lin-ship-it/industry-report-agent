#!/usr/bin/env python3
"""Collect topic-specific discovery results through Agent Reach backends."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import base64
import urllib.parse
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

from intake_contract import load_mode_profiles
from pipeline_lock import pipeline_stage_lock


AGENT_DIR = Path(os.environ.get("AGENT_DIR", Path(__file__).resolve().parent.parent))
CONFIG_FILE = AGENT_DIR / "config.json"
OUTPUT_DIR = AGENT_DIR / "output" / "raw"
PLACEHOLDERS = {"", "<required>", "待配置", "required"}


def question_ids(config: dict) -> list[str]:
    ids = []
    for index, item in enumerate(config.get("research_questions", []), start=1):
        ids.append(str(item.get("id", f"RQ{index}")) if isinstance(item, dict) else f"RQ{index}")
    return ids


def listify(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def query_spec(value: object, inherited: dict | None = None) -> dict:
    inherited = inherited or {}
    base = {
        "question_ids": listify(inherited.get("question_ids", [])),
        "hypothesis_ids": listify(inherited.get("hypothesis_ids", [])),
        "trend_ids": listify(inherited.get("trend_ids", [])),
        "module_ids": listify(inherited.get("module_ids", [])),
        "stance": str(inherited.get("stance", "neutral")).lower(),
    }
    if isinstance(value, str):
        return {"query": value, **base}
    if isinstance(value, dict):
        query = str(value.get("query", "")).strip()
        return {
            "query": query,
            "question_ids": listify(value.get("question_ids", value.get("questions", base["question_ids"]))),
            "hypothesis_ids": listify(value.get("hypothesis_ids", base["hypothesis_ids"])),
            "trend_ids": listify(value.get("trend_ids", base["trend_ids"])),
            "module_ids": listify(value.get("module_ids", base["module_ids"])),
            "stance": str(value.get("stance", base["stance"])).lower(),
        }
    return {"query": "", **base}


def load_config() -> dict:
    config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    target = config.get("target", {})
    missing = [
        key
        for key in ("company", "industry", "year", "region")
        if str(target.get(key, "")).strip().lower() in PLACEHOLDERS
    ]
    if missing:
        raise ValueError(f"config.json 未完成：target.{', target.'.join(missing)}")
    if not config.get("research_questions"):
        raise ValueError("config.json 至少需要一个 research_question")
    if not config.get("research_keywords") and not config.get("focus_queries"):
        raise ValueError("config.json 至少需要 research_keywords 或 focus_queries")
    known_questions = set(question_ids(config))
    referenced_questions = set()
    query_groups = list(config.get("research_keywords", []))
    query_groups.extend(config.get("direct_sources", []))
    for group in config.get("focus_queries", []):
        if isinstance(group, dict):
            query_groups.extend(group.get("queries", []))
    for entries in config.get("competitor_keywords", {}).values():
        query_groups.extend(entries)
    for source in config.get("platform_queries", []):
        query_groups.extend(source.get("queries", []))
    for entry in query_groups:
        if isinstance(entry, dict):
            refs = entry.get("question_ids", entry.get("questions", []))
            referenced_questions.update([refs] if isinstance(refs, str) else refs)
    unknown = sorted(referenced_questions - known_questions)
    if unknown:
        raise ValueError(f"查询引用了不存在的 research question: {', '.join(unknown)}")
    return config


def run_json(command: list[str], timeout: int = 120) -> tuple[object | None, str | None]:
    try:
        completed = subprocess.run(command, check=False, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, str(exc)
    if completed.returncode != 0:
        return None, (completed.stderr or completed.stdout).strip()
    try:
        return json.loads(completed.stdout), None
    except json.JSONDecodeError as exc:
        return None, f"JSON 解析失败: {exc}: {completed.stdout[:300]}"


def _duckduckgo_result_url(href: str) -> str:
    if href.startswith("//"):
        href = f"https:{href}"
    parsed = urllib.parse.urlsplit(href)
    redirected = urllib.parse.parse_qs(parsed.query).get("uddg", [])
    return redirected[0] if redirected else href


class DuckDuckGoHTMLParser(HTMLParser):
    """Parse the public DuckDuckGo HTML result page without extra packages."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.results: dict[str, dict[str, str]] = {}
        self.capture = ""
        self.current_url = ""
        self.fragments: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        attributes = {key: value or "" for key, value in attrs}
        classes = set(attributes.get("class", "").split())
        if "result__a" in classes:
            self.capture = "title"
        elif "result__snippet" in classes:
            self.capture = "snippet"
        else:
            return
        self.current_url = _duckduckgo_result_url(attributes.get("href", ""))
        self.fragments = []

    def handle_data(self, data: str) -> None:
        if self.capture:
            self.fragments.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or not self.capture:
            return
        value = " ".join("".join(self.fragments).split())
        if self.current_url.startswith(("http://", "https://")):
            record = self.results.setdefault(
                self.current_url,
                {"title": "", "url": self.current_url, "summary": ""},
            )
            record[self.capture] = value
        self.capture = ""
        self.current_url = ""
        self.fragments = []


def duckduckgo_search(spec: dict, limit: int) -> tuple[dict | None, str | None]:
    query = urllib.parse.quote_plus(spec["query"])
    try:
        completed = subprocess.run(
            [
                "curl", "--doh-url", "https://cloudflare-dns.com/dns-query",
                "-4", "--http1.1", "-L", "--connect-timeout", "8", "--max-time", "30", "-sS",
                "-A", "Mozilla/5.0",
                f"https://html.duckduckgo.com/html/?q={query}",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=35,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, str(exc)
    if completed.returncode != 0:
        return None, (completed.stderr or completed.stdout).strip()
    page = completed.stdout
    if "challenge-form" in page or "Unfortunately, bots use DuckDuckGo too" in page:
        return None, "DuckDuckGo anti-bot challenge requires a human browser session"
    parser = DuckDuckGoHTMLParser()
    parser.feed(page)
    records = [record for record in parser.results.values() if record.get("title")][:limit]
    if not records:
        return None, "DuckDuckGo HTML returned no parseable results"
    blocks = []
    for record in records:
        blocks.append(
            "\n".join(
                [
                    f"Title: {record['title']}",
                    f"URL: {record['url']}",
                    "Published: ",
                    "Author: ",
                    f"Highlights: {record.get('summary', '')}",
                ]
            )
        )
    return {**spec, "backend": "DuckDuckGo HTML fallback", "raw_evidence": "\n\n".join(blocks)}, None


def _bing_result_url(href: str) -> str:
    """Decode Bing's u=a1<base64> redirect when present."""
    parsed = urllib.parse.urlsplit(href)
    encoded = urllib.parse.parse_qs(parsed.query).get("u", [""])[0]
    if encoded.startswith("a1"):
        payload = encoded[2:]
        try:
            payload += "=" * (-len(payload) % 4)
            decoded = base64.urlsafe_b64decode(payload).decode("utf-8")
            if decoded.startswith(("http://", "https://")):
                return decoded
        except (ValueError, UnicodeDecodeError):
            pass
    return href


class BingHTMLParser(HTMLParser):
    """Parse organic Bing results from li.b_algo without third-party packages."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_result = False
        self.in_h2 = False
        self.capture = ""
        self.fragments: list[str] = []
        self.current = {"title": "", "url": "", "summary": ""}
        self.results: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key: value or "" for key, value in attrs}
        if tag == "li" and "b_algo" in set(attributes.get("class", "").split()):
            self.in_result = True
            self.current = {"title": "", "url": "", "summary": ""}
            return
        if not self.in_result:
            return
        if tag == "h2":
            self.in_h2 = True
            return
        if self.in_h2 and tag == "a":
            self.capture = "title"
            self.fragments = []
            self.current["url"] = _bing_result_url(attributes.get("href", ""))
        elif tag == "p" and not self.current["summary"]:
            self.capture = "summary"
            self.fragments = []

    def handle_data(self, data: str) -> None:
        if self.capture:
            self.fragments.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self.capture == "title":
            self.current["title"] = " ".join("".join(self.fragments).split())
            self.capture = ""
            self.fragments = []
        elif tag == "p" and self.capture == "summary":
            self.current["summary"] = " ".join("".join(self.fragments).split())
            self.capture = ""
            self.fragments = []
        elif tag == "h2":
            self.in_h2 = False
        elif tag == "li" and self.in_result:
            if self.current["title"] and self.current["url"].startswith(("http://", "https://")):
                self.results.append(dict(self.current))
            self.in_result = False
            self.capture = ""
            self.fragments = []


def bing_search(spec: dict, limit: int) -> tuple[dict | None, str | None]:
    try:
        completed = subprocess.run(
            [
                "curl", "-G", "-L", "--max-time", "30", "-sS",
                "-A", "Mozilla/5.0", "--data-urlencode", f"q={spec['query']}",
                "--data-urlencode", "mkt=en-US", "--data-urlencode", "setlang=en-US",
                "--data-urlencode", "cc=US",
                "https://www.bing.com/search",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=35,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, str(exc)
    if completed.returncode != 0:
        return None, (completed.stderr or completed.stdout).strip()
    parser = BingHTMLParser()
    parser.feed(completed.stdout)
    records = parser.results[:limit]
    if not records:
        return None, "Bing HTML returned no parseable organic results"
    blocks = []
    for record in records:
        blocks.append(
            "\n".join(
                [
                    f"Title: {record['title']}",
                    f"URL: {record['url']}",
                    "Published: ",
                    "Author: ",
                    f"Highlights: {record.get('summary', '')}",
                ]
            )
        )
    return {**spec, "backend": "Bing HTML fallback", "raw_evidence": "\n\n".join(blocks)}, None


def opencli_google_search(spec: dict, limit: int) -> tuple[dict | None, str | None]:
    if not shutil.which("opencli"):
        return None, "opencli is not installed"
    data, error = run_json(
        [
            "opencli", "google", "search", spec["query"],
            "--limit", str(limit), "--lang", "zh", "-f", "json",
            "--window", "background", "--site-session", "ephemeral",
            "--keep-tab", "false",
        ],
        timeout=60,
    )
    if error:
        return None, error
    records = [item for item in data if isinstance(item, dict) and item.get("url")][:limit]
    if not records:
        return None, "OpenCLI Google returned no parseable results"
    blocks = []
    for record in records:
        blocks.append(
            "\n".join(
                [
                    f"Title: {record.get('title', '')}",
                    f"URL: {record.get('url', '')}",
                    "Published: ",
                    "Author: ",
                    f"Highlights: {record.get('snippet', '')}",
                ]
            )
        )
    return {**spec, "backend": "OpenCLI Google fallback", "raw_evidence": "\n\n".join(blocks)}, None


def exa_search(spec: dict, limit: int) -> tuple[dict | None, str | None]:
    payload = json.dumps({"query": spec["query"], "numResults": limit}, ensure_ascii=False)
    data, error = run_json(
        ["mcporter", "call", "exa.web_search_exa", "--args", payload, "--output", "json"]
    )
    if error:
        opencli_fallback, opencli_error = opencli_google_search(spec, limit)
        if opencli_fallback:
            opencli_fallback["backend_warning"] = f"Exa unavailable: {error[:500]}"
            return opencli_fallback, None
        bing_fallback, bing_error = bing_search(spec, limit)
        if bing_fallback:
            bing_fallback["backend_warning"] = (
                f"Exa unavailable: {error[:300]}; OpenCLI Google unavailable: {opencli_error}"
            )
            return bing_fallback, None
        fallback, fallback_error = duckduckgo_search(spec, limit)
        if fallback:
            fallback["backend_warning"] = f"Exa unavailable: {error[:500]}"
            return fallback, None
        return None, (
            f"Exa failed: {error}; OpenCLI Google fallback failed: {opencli_error}; "
            f"Bing fallback failed: {bing_error}; DuckDuckGo fallback failed: {fallback_error}"
        )
    text_blocks = [item.get("text", "") for item in data.get("content", []) if item.get("type") == "text"]
    return {**spec, "backend": "Exa via mcporter", "raw_evidence": "\n".join(text_blocks)}, None


def result_urls(result: dict | None) -> set[str]:
    if not result:
        return set()
    return {
        match.group(1).strip()
        for match in re.finditer(r"(?m)^URL:\s*(https?://\S+)\s*$", result.get("raw_evidence", ""))
    }


def adaptive_discovery_search(
    spec: dict,
    initial_limit: int,
    max_limit: int,
    expansion_step: int,
    min_new_urls: int,
    search_fn=exa_search,
) -> tuple[dict | None, str | None]:
    """Expand a ranked query while each larger batch still adds novel URLs."""
    limit = max(1, min(initial_limit, max_limit))
    seen_urls: set[str] = set()
    trace = []
    best_result = None
    stop_reason = "safety_ceiling_reached"

    while True:
        result, error = search_fn(spec, limit)
        if not result:
            if best_result:
                stop_reason = "expansion_failed"
                best_result["expansion_warning"] = str(error or "unknown expansion failure")[:500]
                break
            return None, error

        urls = result_urls(result)
        new_urls = urls - seen_urls
        trace.append({
            "requested_limit": limit,
            "returned_unique_urls": len(urls),
            "new_unique_urls": len(new_urls),
            "backend": result.get("backend", "unknown"),
        })
        best_result = result

        if seen_urls and len(new_urls) < min_new_urls:
            stop_reason = "novelty_saturated"
            break
        seen_urls.update(urls)
        if len(urls) < limit:
            stop_reason = "backend_exhausted"
            break
        if limit >= max_limit:
            stop_reason = "safety_ceiling_reached"
            break
        limit = min(max_limit, limit + max(1, expansion_step))

    best_result["discovery_trace"] = trace
    best_result["discovery_stop_reason"] = stop_reason
    best_result["returned_unique_urls"] = len(result_urls(best_result))
    return best_result, None


def platform_search(platform: str, spec: dict, limit: int) -> tuple[dict | None, str | None]:
    data, error = run_json(
        ["opencli", platform, "search", spec["query"], "--limit", str(limit), "-f", "json"]
    )
    if error:
        return None, error
    return {**spec, "items": data}, None


def _main() -> int:
    config = load_config()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat()
    discovery_limit = int(config.get("collection", {}).get("search_results_per_query", 5))
    adaptive = config.get("collection", {}).get("adaptive_discovery", {})
    adaptive_enabled = bool(adaptive.get("enabled", True))
    mode_profile = load_mode_profiles()[str(config["research_mode"]).lower()]
    discovery_ceiling = int(mode_profile["caps"]["candidate_results_per_query"])
    if not adaptive_enabled:
        discovery_ceiling = min(discovery_ceiling, discovery_limit)
    expansion_step = int(adaptive.get("expansion_step", 5))
    min_new_urls = int(adaptive.get("min_new_urls_to_continue", 2))
    platform_limit = int(config.get("collection", {}).get("platform_results_per_query", 10))
    errors: list[dict] = []

    if shutil.which("agent-reach"):
        health, error = run_json(["agent-reach", "doctor", "--json"])
        if health is not None:
            (OUTPUT_DIR / "source_health.json").write_text(
                json.dumps(health, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        elif error:
            errors.append({"stage": "health", "error": error})

    direct_results = []
    for source in config.get("direct_sources", []):
        if not isinstance(source, dict):
            errors.append({"stage": "direct_source", "error": "direct source must be an object"})
            continue
        spec = query_spec(source)
        title = str(source.get("title", "")).strip()
        url = str(source.get("url", "")).strip()
        if not title or not url.startswith(("http://", "https://")):
            errors.append({
                "stage": "direct_source", "title": title, "url": url,
                "error": "title and an HTTP(S) URL are required",
            })
            continue
        direct_results.append({
            **spec,
            "backend": "Direct authoritative URL",
            "direct_stage": str(source.get("stage", "industry")),
            "direct_entity": str(source.get("entity", "")),
            "raw_evidence": "\n".join([
                f"Title: {title}",
                f"URL: {url}",
                f"Published: {source.get('published_at', '')}",
                f"Author: {source.get('author', '')}",
                f"Highlights: {source.get('summary', '')}",
            ]),
        })

    industry_results = []
    for value in config.get("research_keywords", []):
        spec = query_spec(value)
        if not spec["query"]:
            continue
        result, error = adaptive_discovery_search(
            spec, discovery_limit, discovery_ceiling, expansion_step, min_new_urls
        )
        if result:
            industry_results.append(result)
        else:
            errors.append({"stage": "industry", "query": spec["query"], "error": error})

    focus_results = []
    for entry in config.get("focus_queries", []):
        if isinstance(entry, str):
            group = {"label": entry, "question_ids": [], "queries": [entry]}
        else:
            group = entry
        inherited = {
            "question_ids": group.get("question_ids", group.get("questions", [])),
            "hypothesis_ids": group.get("hypothesis_ids", []),
            "trend_ids": group.get("trend_ids", []),
            "module_ids": group.get("module_ids", []),
            "stance": group.get("stance", "neutral"),
        }
        collected = []
        for value in group.get("queries", []):
            spec = query_spec(value, inherited)
            if not spec["query"]:
                continue
            result, error = adaptive_discovery_search(
                spec, discovery_limit, discovery_ceiling, expansion_step, min_new_urls
            )
            if result:
                collected.append(result)
            else:
                errors.append({"stage": "focus", "query": spec["query"], "error": error})
        focus_results.append({"label": group.get("label", "focus"), **inherited, "results": collected})

    competitor_results = {}
    for competitor in config.get("competitors", []):
        values = config.get("competitor_keywords", {}).get(competitor, [])
        if not values:
            values = [{"query": f"{competitor} {config['target']['industry']}", "question_ids": []}]
        collected = []
        for value in values:
            spec = query_spec(value)
            result, error = adaptive_discovery_search(
                spec, discovery_limit, discovery_ceiling, expansion_step, min_new_urls
            )
            if result:
                collected.append(result)
            else:
                errors.append({"stage": "competitor", "competitor": competitor, "query": spec["query"], "error": error})
        competitor_results[competitor] = {"queries": collected}

    platform_results = {}
    for source in config.get("platform_queries", []):
        platform = source.get("platform", "").strip()
        inherited = {
            "question_ids": source.get("question_ids", source.get("questions", [])),
            "hypothesis_ids": source.get("hypothesis_ids", []),
            "trend_ids": source.get("trend_ids", []),
            "module_ids": source.get("module_ids", []),
            "stance": source.get("stance", "neutral"),
        }
        if not platform:
            continue
        collected = []
        for value in source.get("queries", []):
            spec = query_spec(value, inherited)
            result, error = platform_search(platform, spec, int(source.get("limit", platform_limit)))
            if result:
                collected.append(result)
            else:
                errors.append({"stage": "platform", "platform": platform, "query": spec["query"], "error": error})
        platform_results[platform] = collected

    target = config["target"]
    payloads = {
        "industry_data.json": {
            "timestamp": timestamp, "target": target, "backend": "Exa via mcporter",
            "direct_results": direct_results,
            "search_results": industry_results, "focus_results": focus_results,
        },
        "competitor_data.json": {
            "timestamp": timestamp, "target": target, "backend": "Exa via mcporter",
            "competitors": competitor_results,
        },
        "social_data.json": {
            "timestamp": timestamp, "target": target, "backend": "OpenCLI", "platforms": platform_results,
        },
        "collection_errors.json": {"timestamp": timestamp, "errors": errors},
    }
    for name, data in payloads.items():
        (OUTPUT_DIR / name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"权威直达/行业/焦点查询: {len(direct_results)} / {len(industry_results)} / {len(focus_results)}")
    print(f"竞品: {len(competitor_results)}")
    print(f"平台: {', '.join(platform_results) if platform_results else '未配置'}")
    fallback_count = sum(
        result.get("backend") in {"OpenCLI Google fallback", "Bing HTML fallback", "DuckDuckGo HTML fallback"}
        for result in industry_results
    ) + sum(
        result.get("backend") in {"OpenCLI Google fallback", "Bing HTML fallback", "DuckDuckGo HTML fallback"}
        for group in focus_results
        for result in group.get("results", [])
    ) + sum(
        result.get("backend") in {"OpenCLI Google fallback", "Bing HTML fallback", "DuckDuckGo HTML fallback"}
        for payload in competitor_results.values()
        for result in payload.get("queries", [])
    )
    print(f"后备搜索命中: {fallback_count}")
    all_discovery_results = industry_results + [
        result for group in focus_results for result in group.get("results", [])
    ] + [
        result for payload in competitor_results.values() for result in payload.get("queries", [])
    ]
    stop_reasons = {}
    for result in all_discovery_results:
        reason = result.get("discovery_stop_reason", "single_batch")
        stop_reasons[reason] = stop_reasons.get(reason, 0) + 1
    print(f"自适应发现停止原因: {json.dumps(stop_reasons, ensure_ascii=False)}")
    print(f"错误: {len(errors)}（详见 output/raw/collection_errors.json）")
    return 0 if not errors else 2


def main() -> int:
    with pipeline_stage_lock(AGENT_DIR, "collect_reach"):
        return _main()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        raise SystemExit(1)
