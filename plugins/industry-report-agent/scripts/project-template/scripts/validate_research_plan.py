#!/usr/bin/env python3
"""Validate hypothesis balance and dynamic research-module coverage before collection."""

from __future__ import annotations

import json
import os
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

from intake_contract import load_mode_profiles, validate_intake_config


AGENT_DIR = Path(os.environ.get("AGENT_DIR", Path(__file__).resolve().parent.parent))
CONFIG_FILE = AGENT_DIR / "config.json"
OUTPUT_FILE = AGENT_DIR / "output" / "research_plan_report.json"
VALID_MODULES = {
    "trend_inference",
    "market_concentration",
    "geographic_sequencing",
    "real_case_studies",
    "benchmark_ranges",
    "stress_test",
}
VALID_STANCES = {"support", "disconfirm", "neutral"}
FORBIDDEN_PERSONAL_MVP_KEYS = {"expert_sources", "enterprise_sources", "internal_data_connectors"}
MODULE_TRIGGERS = {
    "trend_inference": r"趋势|主流路径|普遍路径|行业路径|演变|路线|先.+再|trend|trajectory|recurring pattern|common path",
    "market_concentration": r"垄断|寡头|集中度|市场份额|头部控制|monopoly|oligopol|concentration|market share|market structure",
    "geographic_sequencing": r"出海|跨境|全球市场|海外|区域顺序|国家优先|市场进入|先.+再|overseas|market entry|country priorit|geographic (entry|sequenc)|regional expansion|global expansion",
    "real_case_studies": r"案例|爆款|热门|头部作品|逐个拆解|真实样本|case stud|top product|hit title|benchmark case",
    "benchmark_ranges": r"\bCAC\b|\bARPU\b|\bLTV\b|\bROI\b|成本基准|转化率|付费率|利润率|benchmark|unit economics|payback|margin range",
    "stress_test": r"压力测试|极端情景|黑天鹅|最坏情景|stress test|black swan|worst.case",
}
MIN_MODULE_QUERIES = {
    "trend_inference": 2,
    "market_concentration": 2,
    "geographic_sequencing": 2,
    "real_case_studies": 1,
    "benchmark_ranges": 1,
    "stress_test": 1,
}


def listify(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def merge_meta(item: object, inherited: dict | None = None) -> dict:
    inherited = inherited or {}
    if isinstance(item, str):
        return {"query": item, **inherited}
    if not isinstance(item, dict):
        return {"query": "", **inherited}
    result = {**inherited, **item}
    for key in ("question_ids", "hypothesis_ids", "trend_ids", "module_ids"):
        result[key] = listify(item.get(key, inherited.get(key, [])))
    result["stance"] = str(item.get("stance", inherited.get("stance", "neutral"))).lower()
    return result


def query_entries(config: dict) -> list[dict]:
    entries = [merge_meta(item) for item in config.get("research_keywords", [])]
    for group in config.get("focus_queries", []):
        if isinstance(group, str):
            entries.append(merge_meta(group))
            continue
        inherited = {key: group.get(key, []) for key in ("question_ids", "hypothesis_ids", "trend_ids", "module_ids")}
        inherited["stance"] = group.get("stance", "neutral")
        entries.extend(merge_meta(item, inherited) for item in group.get("queries", []))
    for items in config.get("competitor_keywords", {}).values():
        entries.extend(merge_meta(item) for item in items)
    for source in config.get("platform_queries", []):
        inherited = {key: source.get(key, []) for key in ("question_ids", "hypothesis_ids", "trend_ids", "module_ids")}
        inherited["stance"] = source.get("stance", "neutral")
        entries.extend(merge_meta(item, inherited) for item in source.get("queries", []))
    return [entry for entry in entries if str(entry.get("query", "")).strip()]


def question_text(config: dict) -> str:
    target = config.get("target", {})
    values = [target.get("industry", ""), target.get("region", "")]
    for item in config.get("research_questions", []):
        values.append(item if isinstance(item, str) else item.get("question", ""))
    values.extend(item.get("statement", "") for item in config.get("user_hypotheses", []) if isinstance(item, dict))
    return "\n".join(str(item) for item in values)


def main() -> int:
    config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    mode, output_formats, intake_failures = validate_intake_config(config)
    mode_profiles = load_mode_profiles()
    design = config.get("research_design", {})
    active_modules = list(dict.fromkeys(str(item) for item in design.get("active_modules", [])))
    inferred_modules = {
        module for module, pattern in MODULE_TRIGGERS.items()
        if re.search(pattern, question_text(config), re.I | re.S)
    }
    if "geographic_sequencing" in inferred_modules or "geographic_sequencing" in active_modules:
        inferred_modules.add("trend_inference")
    if mode == "deep":
        inferred_modules.add("stress_test")
    entries = query_entries(config)
    failures = list(intake_failures)
    warnings = []

    if mode in mode_profiles:
        expected_deep_reads = mode_profiles[mode]["caps"]["deep_reads"]
        actual_deep_reads = config.get("collection", {}).get("max_deep_reads")
        if actual_deep_reads != expected_deep_reads:
            failures.append({
                "check": "mode_scope:max_deep_reads",
                "actual": actual_deep_reads,
                "required": expected_deep_reads,
                "detail": "collection.max_deep_reads 必须与所选模式合同一致",
            })
        collection = config.get("collection", {})
        initial_results = int(collection.get("search_results_per_query", 0))
        candidate_ceiling = int(mode_profiles[mode]["caps"]["candidate_results_per_query"])
        adaptive = collection.get("adaptive_discovery", {})
        if initial_results < 1 or initial_results > candidate_ceiling:
            failures.append({
                "check": "adaptive_discovery:initial_batch",
                "actual": initial_results,
                "required": f"1..{candidate_ceiling}",
            })
        if int(adaptive.get("expansion_step", 0)) < 1:
            failures.append({"check": "adaptive_discovery:expansion_step", "detail": ">=1 required"})
        if int(adaptive.get("min_new_urls_to_continue", 0)) < 1:
            failures.append({"check": "adaptive_discovery:min_new_urls_to_continue", "detail": ">=1 required"})

    invalid_modules = sorted(set(active_modules) - VALID_MODULES)
    missing_modules = sorted(inferred_modules - set(active_modules))
    if invalid_modules:
        failures.append({"check": "valid_modules", "detail": invalid_modules})
    if missing_modules:
        failures.append({"check": "required_modules_selected", "detail": missing_modules})
    forbidden = sorted(FORBIDDEN_PERSONAL_MVP_KEYS & set(config))
    if forbidden:
        failures.append({"check": "personal_mvp_boundary", "detail": forbidden})

    rationales = design.get("module_rationale", {})
    missing_rationale = [item for item in active_modules if not str(rationales.get(item, "")).strip()]
    if missing_rationale:
        failures.append({"check": "module_rationale", "detail": missing_rationale})

    module_query_counts = Counter(module for entry in entries for module in listify(entry.get("module_ids", [])))
    query_module_ids = {module for entry in entries for module in listify(entry.get("module_ids", []))}
    invalid_query_modules = sorted(query_module_ids - VALID_MODULES)
    inactive_query_modules = sorted(query_module_ids - set(active_modules))
    if invalid_query_modules:
        failures.append({"check": "query_module_ids_valid", "detail": invalid_query_modules})
    if inactive_query_modules:
        failures.append({"check": "query_modules_are_active", "detail": inactive_query_modules})
    for module in active_modules:
        required = MIN_MODULE_QUERIES[module]
        if module_query_counts[module] < required:
            failures.append({
                "check": f"module_query_coverage:{module}",
                "actual": module_query_counts[module],
                "required": required,
            })

    if "trend_inference" in active_modules:
        trend_queries = [entry for entry in entries if "trend_inference" in listify(entry.get("module_ids", []))]
        if not any(entry.get("stance") == "disconfirm" for entry in trend_queries):
            failures.append({
                "check": "trend_inference:counterexample_search",
                "detail": "at least one disconfirm/exception query required even when the pattern is discovered automatically",
            })

    invalid_stances = sorted({entry.get("stance", "neutral") for entry in entries} - VALID_STANCES)
    if invalid_stances:
        failures.append({"check": "valid_query_stances", "detail": invalid_stances})

    hypothesis_ids = []
    for index, item in enumerate(config.get("user_hypotheses", []), start=1):
        if not isinstance(item, dict):
            failures.append({"check": "hypothesis_schema", "detail": f"item {index} must be an object"})
            continue
        hypothesis_id = str(item.get("id", f"H{index}"))
        hypothesis_ids.append(hypothesis_id)
        if item.get("origin") != "user_provided_lead":
            failures.append({"check": f"hypothesis_origin:{hypothesis_id}", "detail": item.get("origin")})
        if not str(item.get("statement", "")).strip():
            failures.append({"check": f"hypothesis_statement:{hypothesis_id}", "detail": "missing"})
        if item.get("must_test", True):
            tagged = [entry for entry in entries if hypothesis_id in listify(entry.get("hypothesis_ids", []))]
            stances = {entry.get("stance", "neutral") for entry in tagged}
            if "support" not in stances or "disconfirm" not in stances:
                failures.append({"check": f"hypothesis_balance:{hypothesis_id}", "detail": sorted(stances)})
    if len(hypothesis_ids) != len(set(hypothesis_ids)):
        failures.append({"check": "unique_hypothesis_ids", "detail": hypothesis_ids})

    candidate_trends = design.get("candidate_trends", [])
    trend_ids = []
    for index, item in enumerate(candidate_trends, start=1):
        if not isinstance(item, dict):
            failures.append({"check": "trend_schema", "detail": f"item {index} must be an object"})
            continue
        trend_id = str(item.get("id", f"T{index}"))
        trend_ids.append(trend_id)
        if not str(item.get("pattern", "")).strip() or not str(item.get("scope", "")).strip():
            failures.append({"check": f"trend_definition:{trend_id}", "detail": "pattern and scope required"})
        if item.get("status") != "unverified":
            failures.append({
                "check": f"trend_preclassification:{trend_id}",
                "detail": "candidate trends must start with status=unverified",
            })
        tagged = [entry for entry in entries if trend_id in listify(entry.get("trend_ids", []))]
        if tagged:
            stances = {entry.get("stance", "neutral") for entry in tagged}
            if "support" not in stances or "disconfirm" not in stances:
                failures.append({"check": f"trend_balance:{trend_id}", "detail": sorted(stances)})
        else:
            warnings.append({"check": f"trend_targeting:{trend_id}", "detail": "no targeted query yet; an unverified candidate still needs support and disconfirming searches"})
    if len(trend_ids) != len(set(trend_ids)):
        failures.append({"check": "unique_trend_ids", "detail": trend_ids})

    query_hypothesis_ids = {item for entry in entries for item in listify(entry.get("hypothesis_ids", []))}
    query_trend_ids = {item for entry in entries for item in listify(entry.get("trend_ids", []))}
    unknown_hypotheses = sorted(query_hypothesis_ids - set(hypothesis_ids))
    unknown_trends = sorted(query_trend_ids - set(trend_ids))
    if unknown_hypotheses:
        failures.append({"check": "query_hypothesis_ids_known", "detail": unknown_hypotheses})
    if unknown_trends:
        failures.append({"check": "query_trend_ids_known", "detail": unknown_trends})

    if "real_case_studies" in active_modules:
        minimum = int(design.get("case_studies", {}).get("minimum", 0))
        required = 3 if mode == "standard" else 5 if mode == "deep" else 1
        if minimum < required:
            failures.append({"check": "real_case_minimum", "actual": minimum, "required": required})
        if not design.get("case_studies", {}).get("selection_criteria"):
            failures.append({"check": "real_case_selection_criteria", "detail": "missing"})

    report = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "status": "pass" if not failures else "fail",
        "research_mode": mode,
        "output_formats": output_formats,
        "active_modules": active_modules,
        "inferred_required_modules": sorted(inferred_modules),
        "module_query_counts": dict(module_query_counts),
        "user_hypotheses": hypothesis_ids,
        "candidate_trends": trend_ids,
        "query_count": len(entries),
        "failures": failures,
        "warnings": warnings,
    }
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"研究计划闸门: {report['status'].upper()}，失败 {len(failures)} 项，警告 {len(warnings)} 项")
    for failure in intake_failures:
        print(f"- {failure['detail']}")
    return 0 if not failures else 3


if __name__ == "__main__":
    raise SystemExit(main())
