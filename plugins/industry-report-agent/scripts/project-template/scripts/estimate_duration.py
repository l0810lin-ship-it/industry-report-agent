#!/usr/bin/env python3
"""Estimate the completion window for one configured industry-report topic."""

from __future__ import annotations

import json
import math
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

from intake_contract import load_mode_profiles, validate_intake_config


AGENT_DIR = Path(os.environ.get("AGENT_DIR", Path(__file__).resolve().parent.parent))
CONFIG_FILE = AGENT_DIR / "config.json"
OUTPUT_FILE = AGENT_DIR / "output" / "estimate.json"
PLACEHOLDERS = {"", "<required>", "待配置", "required"}

MODE_PROFILES = load_mode_profiles()


def round_up_five(value: float) -> int:
    return max(5, int(math.ceil(value / 5.0) * 5))


def format_minutes(minutes: int) -> str:
    if minutes < 60:
        return f"{minutes} 分钟"
    hours, remainder = divmod(minutes, 60)
    return f"{hours} 小时" if remainder == 0 else f"{hours} 小时 {remainder} 分钟"


def count_queries(config: dict) -> tuple[int, int, int, int]:
    research = len(config.get("research_keywords", []))
    focus = sum(len(group.get("queries", [])) if isinstance(group, dict) else 1 for group in config.get("focus_queries", []))
    competitor = sum(len(items) for items in config.get("competitor_keywords", {}).values())
    platform = sum(len(source.get("queries", [])) for source in config.get("platform_queries", []))
    return research, focus, competitor, platform


def query_mapping_stats(config: dict) -> tuple[int, int]:
    mapped = 0
    total = 0
    values = list(config.get("research_keywords", []))
    for group in config.get("focus_queries", []):
        if isinstance(group, dict):
            inherited = group.get("question_ids", group.get("questions", []))
            for item in group.get("queries", []):
                values.append(item if isinstance(item, dict) else {"query": item, "question_ids": inherited})
        else:
            values.append(group)
    for items in config.get("competitor_keywords", {}).values():
        values.extend(items)
    for source in config.get("platform_queries", []):
        inherited = source.get("question_ids", source.get("questions", []))
        for item in source.get("queries", []):
            values.append(item if isinstance(item, dict) else {"query": item, "question_ids": inherited})
    for item in values:
        total += 1
        if isinstance(item, dict) and item.get("question_ids", item.get("questions", [])):
            mapped += 1
    return mapped, total


def scope_excess(actual: dict, caps: dict) -> dict:
    return {key: actual[key] - caps[key] for key in caps if actual[key] > caps[key]}


def recommend_mode(mode: str, actual: dict) -> str:
    order = ["flash", "standard", "deep"]
    start = order.index(mode)
    for candidate in order[start:]:
        if not scope_excess(actual, MODE_PROFILES[candidate]["caps"]):
            return candidate
    return "deep"


def main() -> int:
    config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    mode, output_formats, intake_failures = validate_intake_config(config)
    if intake_failures:
        print("❌ 尚未完成开工前选择，不能估时：", file=sys.stderr)
        for failure in intake_failures:
            print(f"- {failure['detail']}", file=sys.stderr)
        return 3
    profile = MODE_PROFILES[mode]

    target = config.get("target", {})
    missing = [
        key for key in ("company", "industry", "year", "region")
        if str(target.get(key, "")).strip().lower() in PLACEHOLDERS
    ]
    if missing:
        print(f"❌ 无法估时，配置未完成：target.{', target.'.join(missing)}", file=sys.stderr)
        return 1

    questions = config.get("research_questions", [])
    user_hypotheses = [item for item in config.get("user_hypotheses", []) if isinstance(item, dict) and item.get("must_test", True)]
    active_modules = [str(item) for item in config.get("research_design", {}).get("active_modules", [])]
    candidate_trends = [item for item in config.get("research_design", {}).get("candidate_trends", []) if isinstance(item, dict)]
    critical_questions = sum(bool(item.get("critical", True)) if isinstance(item, dict) else True for item in questions)
    competitors = len(config.get("competitors", []))
    platform_sources = len(config.get("platform_queries", []))
    research_queries, focus_queries, competitor_queries, platform_queries = count_queries(config)
    web_queries = research_queries + focus_queries + competitor_queries
    total_queries = web_queries + platform_queries
    collection = config.get("collection", {})
    search_limit = int(collection.get("search_results_per_query", 5))
    adaptive_enabled = bool(collection.get("adaptive_discovery", {}).get("enabled", True))
    search_ceiling = int(profile["caps"]["candidate_results_per_query"])
    if not adaptive_enabled:
        search_ceiling = min(search_ceiling, search_limit)
    platform_limit = int(collection.get("platform_results_per_query", 10))
    direct_sources = len(config.get("direct_sources", []))
    candidate_floor = direct_sources + web_queries * search_limit + platform_queries * platform_limit
    candidate_ceiling = direct_sources + web_queries * search_ceiling + platform_queries * platform_limit
    deep_reads = min(int(collection["max_deep_reads"]), candidate_ceiling)
    mapped_queries, mapping_total = query_mapping_stats(config)
    mapping_ratio = mapped_queries / max(mapping_total, 1)
    official_domains = len(config.get("source_rules", {}).get("official_domains", []))

    actual_scope = {
        "questions": len(questions),
        "competitors": competitors,
        "queries": total_queries,
        "candidate_results_per_query": search_ceiling,
        "platform_sources": platform_sources,
        "deep_reads": deep_reads,
    }
    excess = scope_excess(actual_scope, profile["caps"])
    recommended_mode = recommend_mode(mode, actual_scope)

    risks = []
    confidence_penalties = 0
    extra_min = 0
    extra_max = 0
    if mapping_ratio < 0.8:
        risks.append("部分查询尚未映射到研究问题，需先修正配置")
        extra_min += 5
        extra_max += 15
        confidence_penalties += 2
    if official_domains < 2:
        risks.append("一手来源域名配置不足，质量闸门可能要求补充来源")
        extra_min += 5
        extra_max += 15
        confidence_penalties += 1
    if platform_sources:
        risks.append("所选社区平台可能受登录态、限流或页面变化影响")
        confidence_penalties += min(platform_sources, 2)
    if user_hypotheses:
        risks.append("用户提供的判断只作为待证伪假设，支持与反证检索都可能增加返工")
    if "trend_inference" in active_modules:
        risks.append("行业趋势需要跨主体时间线与反例样本，不能由单一案例直接推出")
    if excess:
        details = "、".join(f"{key} 超出 {value}" for key, value in excess.items())
        risks.append(f"当前范围超出 {profile['label']} 契约（{details}）")
        extra_min += 10 + 5 * len(excess)
        extra_max += 25 + 10 * len(excess)
        confidence_penalties += 2
    if not risks:
        risks.append("若关键来源不可访问或首轮质量闸门失败，完成时间将接近区间上限")

    format_overhead = {
        item: {
            "min_minutes": profile["format_overhead_minutes"][item][0],
            "max_minutes": profile["format_overhead_minutes"][item][1],
        }
        for item in output_formats
    }
    format_extra_min = sum(item["min_minutes"] for item in format_overhead.values())
    format_extra_max = sum(item["max_minutes"] for item in format_overhead.values())
    if "docx" in output_formats:
        risks.append("Word 交付包含分页、表格和逐页渲染验收")
    if "pptx" in output_formats:
        risks.append("PPT 交付包含叙事重构、可编辑图表和逐张渲染验收")

    base_min, base_max = profile["base_minutes"]
    research_min = round_up_five(base_min + extra_min)
    research_max = round_up_five(base_max + extra_max)
    min_minutes = round_up_five(research_min + format_extra_min)
    max_minutes = round_up_five(research_max + format_extra_max)
    confidence = "high" if confidence_penalties == 0 else "medium" if confidence_penalties <= 2 else "low"

    started = datetime.now().astimezone()
    earliest = started + timedelta(minutes=min_minutes)
    latest = started + timedelta(minutes=max_minutes)
    phase_estimates = {
        name: {"min_minutes": values[0], "max_minutes": values[1]}
        for name, values in profile["phases"].items()
    }
    phase_estimates["selected_format_rendering_and_qa"] = {
        "min_minutes": format_extra_min,
        "max_minutes": format_extra_max,
    }
    estimate = {
        "estimated_at": started.isoformat(),
        "target": target,
        "research_mode": mode,
        "mode_label": profile["label"],
        "deliverable": profile["deliverable"],
        "output_formats": output_formats,
        "format_overhead": format_overhead,
        "format_overhead_total": {"min_minutes": format_extra_min, "max_minutes": format_extra_max},
        "confidence": confidence,
        "research_base_minutes": {"min": research_min, "max": research_max},
        "research_base_duration_text": f"{format_minutes(research_min)}–{format_minutes(research_max)}",
        "estimated_minutes": {"min": min_minutes, "max": max_minutes},
        "estimated_duration_text": f"{format_minutes(min_minutes)}–{format_minutes(max_minutes)}",
        "estimated_completion_window": {"earliest": earliest.isoformat(), "latest": latest.isoformat()},
        "scope_contract": profile["caps"],
        "report_scope": {
            "deliverable": profile["deliverable"],
            "configured": actual_scope,
            "mode_caps": profile["caps"],
            "candidate_discovery": {
                "method": "adaptive_novelty_saturation",
                "initial_batch_per_query": search_limit,
                "safety_ceiling_per_query": search_ceiling,
                "pre_relevance_candidate_range": {"min": candidate_floor, "max": candidate_ceiling},
                "note": "这是运行安全范围，不是证据数量目标；最终候选数由相关性、去重和新增信息饱和决定。",
            },
        },
        "scope_exceeded": bool(excess),
        "scope_excess": excess,
        "recommended_mode": recommended_mode,
        "complexity": {
            "research_questions": len(questions),
            "critical_questions": critical_questions,
            "competitors": competitors,
            "web_queries": web_queries,
            "platform_sources": platform_sources,
            "platform_queries": platform_queries,
            "planned_deep_reads": deep_reads,
            "query_mapping_ratio": round(mapping_ratio, 3),
            "user_hypotheses": len(user_hypotheses),
            "candidate_trends": len(candidate_trends),
            "active_research_modules": active_modules,
        },
        "phase_estimates": phase_estimates,
        "risks": risks,
        "note": "该区间是开工前预测，不等同于实际工时；来源访问失败和质量闸门返工会使结果接近上限。",
    }
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(estimate, ensure_ascii=False, indent=2), encoding="utf-8")

    overhead_text = "；".join(
        f"{item}: {format_minutes(values['min_minutes'])}–{format_minutes(values['max_minutes'])}"
        for item, values in format_overhead.items()
    )
    print(f"研究模式：{profile['label']}")
    print(f"交付格式：{', '.join(output_formats)}")
    print(
        f"报告范围：{profile['deliverable']}；{len(questions)} 个研究问题、{competitors} 个竞品、"
        f"{total_queries} 条查询；候选来源按相关性与新增信息自适应扩展，最多深读 {deep_reads} 条原文"
    )
    print(f"研究与成稿基础时间：{estimate['research_base_duration_text']}")
    print(f"格式制作额外耗时：{overhead_text}")
    if len(output_formats) > 1:
        print(f"格式制作合计额外耗时：{format_minutes(format_extra_min)}–{format_minutes(format_extra_max)}")
    print(f"预计完成总时间：{estimate['estimated_duration_text']}")
    print(f"预计完成窗口：{earliest.strftime('%Y-%m-%d %H:%M')} 至 {latest.strftime('%Y-%m-%d %H:%M')}")
    print(f"置信度：{confidence}")
    if excess:
        print(f"⚠️ 当前范围超出 {profile['label']}；建议切换到 {MODE_PROFILES[recommended_mode]['label']}")
    print("主要风险：" + "；".join(risks))
    print(f"估算已保存：{OUTPUT_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
