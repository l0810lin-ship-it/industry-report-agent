#!/usr/bin/env python3
"""Apply configurable evidence-quality gates and emit machine/human reports."""

from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from pipeline_lock import pipeline_stage_lock


AGENT_DIR = Path(os.environ.get("AGENT_DIR", Path(__file__).resolve().parent.parent))
RAW_DIR = AGENT_DIR / "output" / "raw"
CONFIG = json.loads((AGENT_DIR / "config.json").read_text(encoding="utf-8"))

MODE_GATES = {
    "flash": {
        "min_total_evidence": 6,
        "min_deep_read_evidence": 4,
        "min_primary_domains": 1,
        "min_distinct_domains": 3,
        "max_single_domain_share": 0.6,
        "max_age_days": 1095,
        "max_stale_share": 0.6,
        "min_evidence_per_question": 2,
        "min_deep_read_per_critical_question": 1,
        "min_domains_per_critical_question": 2,
        "min_items_per_selected_platform": 2,
    },
    "standard": {
        "min_total_evidence": 15,
        "min_deep_read_evidence": 5,
        "min_search_discovered_evidence": 5,
        "min_search_deep_read_evidence": 3,
        "min_primary_domains": 2,
        "min_distinct_domains": 4,
        "max_single_domain_share": 0.5,
        "max_age_days": 1095,
        "max_stale_share": 0.5,
        "min_evidence_per_question": 2,
        "min_deep_read_per_critical_question": 1,
        "min_domains_per_critical_question": 2,
        "min_items_per_selected_platform": 3,
    },
    "deep": {
        "min_total_evidence": 40,
        "min_deep_read_evidence": 12,
        "min_search_discovered_evidence": 15,
        "min_search_deep_read_evidence": 8,
        "min_primary_domains": 3,
        "min_distinct_domains": 8,
        "max_single_domain_share": 0.4,
        "max_age_days": 1095,
        "max_stale_share": 0.4,
        "min_evidence_per_question": 3,
        "min_deep_read_per_critical_question": 2,
        "min_domains_per_critical_question": 2,
        "min_items_per_selected_platform": 5,
    },
}


def research_questions() -> list[dict]:
    result = []
    for index, item in enumerate(CONFIG.get("research_questions", []), start=1):
        if isinstance(item, str):
            result.append({"id": f"RQ{index}", "question": item, "critical": True})
        else:
            result.append({"id": str(item.get("id", f"RQ{index}")), "question": item.get("question", ""), "critical": bool(item.get("critical", True))})
    return result


def coverage_for(items: list[dict]) -> dict:
    return {
        "evidence": len(items),
        "deep_read": sum(item.get("read_status") == "deep_read" for item in items),
        "distinct_domains": len({
            item.get("source_family", item.get("domain"))
            for item in items if item.get("source_family", item.get("domain"))
        }),
    }


def parse_date(value: str) -> datetime | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            return datetime.strptime(value[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            return None


def _main() -> int:
    ledger = json.loads((RAW_DIR / "evidence_ledger.json").read_text(encoding="utf-8"))
    evidence = ledger.get("evidence", [])
    mode = str(CONFIG["research_mode"]).lower()
    if mode not in MODE_GATES:
        raise ValueError("research_mode must be flash, standard, or deep")
    gates = {**MODE_GATES[mode], **CONFIG.get("quality_gates", {})}
    questions = research_questions()
    domains = [item.get("source_family", item.get("domain")) for item in evidence if item.get("source_family", item.get("domain"))]
    domain_counts = Counter(domains)
    deep_read = [item for item in evidence if item.get("read_status") == "deep_read"]
    search_discovered = [item for item in evidence if "search" in item.get("source_origins", [])]
    search_deep_read = [item for item in search_discovered if item.get("read_status") == "deep_read"]
    primary = [item for item in deep_read if item.get("is_primary")]
    primary_domains = {item.get("source_family", item.get("domain")) for item in primary if item.get("source_family", item.get("domain"))}
    max_domain_share = max(domain_counts.values(), default=0) / max(len(domains), 1)
    now = datetime.now(timezone.utc)
    known_dates = [parsed for item in evidence if (parsed := parse_date(item.get("published_at", "")))]
    max_age_days = int(gates.get("max_age_days", 1095))
    stale = [date for date in known_dates if (now - date.astimezone(timezone.utc)).days > max_age_days]
    stale_share = len(stale) / max(len(known_dates), 1)
    competitor_coverage = {
        competitor: sum(item.get("stage") == "competitor" and item.get("entity") == competitor for item in evidence)
        for competitor in CONFIG.get("competitors", [])
    }
    platform_counts = {
        platform: sum(item.get("platform") == platform for item in evidence)
        for platform in [entry.get("platform", "") for entry in CONFIG.get("platform_queries", []) if entry.get("platform")]
    }
    question_coverage = {}
    for question in questions:
        matching = [item for item in evidence if question["id"] in item.get("question_ids", [])]
        question_coverage[question["id"]] = {
            "question": question["question"], "critical": question["critical"],
            **coverage_for(matching),
        }
    active_modules = [str(item) for item in CONFIG.get("research_design", {}).get("active_modules", [])]
    module_coverage = {
        module: coverage_for([item for item in evidence if module in item.get("module_ids", [])])
        for module in active_modules
    }
    hypothesis_coverage = {}
    for index, hypothesis in enumerate(CONFIG.get("user_hypotheses", []), start=1):
        if not isinstance(hypothesis, dict) or not hypothesis.get("must_test", True):
            continue
        hypothesis_id = str(hypothesis.get("id", f"H{index}"))
        hypothesis_coverage[hypothesis_id] = {
            stance: coverage_for([
                item for item in evidence
                if hypothesis_id in item.get("hypothesis_ids", []) and stance in item.get("query_stances", [])
            ])
            for stance in ("support", "disconfirm")
        }
    trend_coverage = {}
    for index, trend in enumerate(CONFIG.get("research_design", {}).get("candidate_trends", []), start=1):
        if not isinstance(trend, dict):
            continue
        trend_id = str(trend.get("id", f"T{index}"))
        trend_coverage[trend_id] = {
            stance: coverage_for([
                item for item in evidence
                if trend_id in item.get("trend_ids", []) and stance in item.get("query_stances", [])
            ])
            for stance in ("support", "disconfirm")
        }

    metrics = {
        "total_evidence": len(evidence),
        "deep_read_evidence": len(deep_read),
        "search_discovered_evidence": len(search_discovered),
        "search_deep_read_evidence": len(search_deep_read),
        "deep_read_failures": sum(item.get("read_status") == "deep_read_failed" for item in evidence),
        "primary_deep_read_evidence": len(primary),
        "primary_domains": len(primary_domains),
        "distinct_domains": len(domain_counts),
        "max_single_domain_share": round(max_domain_share, 4),
        "known_date_evidence": len(known_dates),
        "stale_share": round(stale_share, 4),
        "competitor_coverage": competitor_coverage,
        "platform_counts": platform_counts,
        "question_coverage": question_coverage,
        "module_coverage": module_coverage,
        "hypothesis_search_coverage": hypothesis_coverage,
        "trend_search_coverage": trend_coverage,
    }
    checks = []

    def add(name: str, passed: bool, actual: object, required: object, remediation: str, severity: str = "fail") -> None:
        checks.append({"name": name, "passed": bool(passed), "severity": severity, "actual": actual, "required": required, "remediation": remediation})

    min_total = int(gates.get("min_total_evidence", 10))
    min_deep = int(gates.get("min_deep_read_evidence", 5))
    min_search_discovered = int(gates.get("min_search_discovered_evidence", 0))
    min_search_deep = int(gates.get("min_search_deep_read_evidence", 0))
    min_primary_domains = int(gates.get("min_primary_domains", 2))
    min_domains = int(gates.get("min_distinct_domains", 4))
    max_domain = float(gates.get("max_single_domain_share", 0.5))
    max_stale = float(gates.get("max_stale_share", 0.5))
    min_per_question = int(gates.get("min_evidence_per_question", 2))
    min_domains_critical = int(gates.get("min_domains_per_critical_question", 2))
    min_deep_critical = int(gates.get("min_deep_read_per_critical_question", 1))

    add("total_evidence", len(evidence) >= min_total, len(evidence), f">={min_total}", "扩充与研究问题直接相关的查询，而不是增加无关平台。")
    add("deep_read_evidence", len(deep_read) >= min_deep, len(deep_read), f">={min_deep}", "打开原始 URL；对失败页面改用官方文件、Jina 或动态浏览器。")
    discovery_configured = bool(CONFIG.get("research_keywords") or CONFIG.get("focus_queries") or CONFIG.get("competitor_keywords"))
    if discovery_configured and min_search_discovered:
        add(
            "search_discovered_evidence",
            len(search_discovered) >= min_search_discovered,
            len(search_discovered), f">={min_search_discovered}",
            "保留 Exa/Google/Bing/DuckDuckGo 发现池；权威直达来源只能提高优先级，不能替代外部发现。",
        )
        add(
            "search_deep_read_evidence",
            len(search_deep_read) >= min_search_deep,
            len(search_deep_read), f">={min_search_deep}",
            "从搜索发现池中深读独立来源，避免只深读预先指定的官网清单。",
        )
    add("primary_domains", len(primary_domains) >= min_primary_domains, len(primary_domains), f">={min_primary_domains}", "补充官网、监管、研究机构或一手文件，并在 source_rules 标注域名。")
    add("distinct_domains", len(domain_counts) >= min_domains, len(domain_counts), f">={min_domains}", "补充独立来源，避免转载链重复计数。")
    add("domain_concentration", max_domain_share <= max_domain, metrics["max_single_domain_share"], f"<={max_domain}", "降低单一域名占比，增加独立来源。")
    if known_dates:
        add("freshness", stale_share <= max_stale, metrics["stale_share"], f"<={max_stale}", "缩小时间范围并补充近期来源。")
    else:
        add("freshness_metadata", False, 0, ">=1 dated source", "补充带发布日期的一手来源。", "warn")

    for question in questions:
        coverage = question_coverage[question["id"]]
        add(
            f"question:{question['id']}:evidence",
            coverage["evidence"] >= min_per_question,
            coverage["evidence"], f">={min_per_question}",
            f"为 {question['id']} 增加带 question_ids 映射的查询。",
        )
        if question["critical"]:
            add(
                f"question:{question['id']}:deep_read",
                coverage["deep_read"] >= min_deep_critical,
                coverage["deep_read"], f">={min_deep_critical}",
                f"为关键问题 {question['id']} 深读至少一个原始来源。",
            )
            add(
                f"question:{question['id']}:cross_source",
                coverage["distinct_domains"] >= min_domains_critical,
                coverage["distinct_domains"], f">={min_domains_critical}",
                f"为关键问题 {question['id']} 增加独立来源交叉验证。",
            )

    for module, coverage in module_coverage.items():
        add(
            f"module:{module}:evidence",
            coverage["evidence"] >= 2,
            coverage["evidence"], ">=2",
            f"为动态模块 {module} 增加带 module_ids 映射的查询。",
        )
        add(
            f"module:{module}:deep_read",
            coverage["deep_read"] >= 1,
            coverage["deep_read"], ">=1",
            f"为动态模块 {module} 深读至少一个原始来源。",
        )

    for hypothesis_id, stances in hypothesis_coverage.items():
        for stance, coverage in stances.items():
            add(
                f"hypothesis:{hypothesis_id}:{stance}_search",
                coverage["deep_read"] >= 1,
                coverage["deep_read"], ">=1 deep-read result",
                f"为 {hypothesis_id} 补充 {stance} 方向查询并深读原始来源；用户表述本身不算证据。",
            )

    for trend_id, stances in trend_coverage.items():
        for stance, coverage in stances.items():
            add(
                f"trend:{trend_id}:{stance}_search",
                coverage["deep_read"] >= 1,
                coverage["deep_read"], ">=1 deep-read result",
                f"为候选趋势 {trend_id} 补充 {stance} 方向查询；不得只搜支持样本。",
            )

    if competitor_coverage:
        min_competitors = int(gates.get("min_competitors_with_evidence", len(competitor_coverage)))
        covered = sum(count > 0 for count in competitor_coverage.values())
        add("competitor_coverage", covered >= min_competitors, covered, f">={min_competitors}", "为缺失竞品增加专属查询或删除不属于研究范围的竞品。")
    if platform_counts:
        min_platform_items = int(gates.get("min_items_per_selected_platform", 3))
        weak = {platform: count for platform, count in platform_counts.items() if count < min_platform_items}
        add("selected_platform_coverage", not weak, weak or platform_counts, f">={min_platform_items} each", "调整所选平台查询；不要用无关平台凑数量。")

    failures = [check for check in checks if not check["passed"] and check["severity"] == "fail"]
    warnings = [check for check in checks if not check["passed"] and check["severity"] == "warn"]
    report = {
        "generated_at": now.isoformat(),
        "research_mode": mode,
        "applied_gates": gates,
        "status": "pass" if not failures else "fail",
        "metrics": metrics,
        "checks": checks,
        "failures": failures,
        "warnings": warnings,
    }
    (RAW_DIR / "quality_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [f"# Evidence Quality Report", "", f"Status: **{report['status'].upper()}**", "", "## Metrics", ""]
    for key, value in metrics.items():
        lines.append(f"- {key}: `{json.dumps(value, ensure_ascii=False)}`")
    lines.extend(["", "## Checks", ""])
    for check in checks:
        marker = "PASS" if check["passed"] else check["severity"].upper()
        lines.append(f"- **{marker}** `{check['name']}`: actual `{json.dumps(check['actual'], ensure_ascii=False)}`, required `{check['required']}`")
        if not check["passed"]:
            lines.append(f"  - {check['remediation']}")
    (RAW_DIR / "quality_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"质量闸门: {report['status'].upper()}，失败 {len(failures)} 项，警告 {len(warnings)} 项")
    return 0 if not failures else 3


def main() -> int:
    with pipeline_stage_lock(AGENT_DIR, "validate_evidence"):
        return _main()


if __name__ == "__main__":
    raise SystemExit(main())
