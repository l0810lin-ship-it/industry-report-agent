#!/usr/bin/env python3
"""Validate the canonical report and requested artifact presence before handoff."""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime
from pathlib import Path

from intake_contract import validate_intake_config


AGENT_DIR = Path(os.environ.get("AGENT_DIR", Path(__file__).resolve().parent.parent))
CONFIG_FILE = AGENT_DIR / "config.json"
OUTPUT_DIR = AGENT_DIR / "output"
ANALYZED_DIR = OUTPUT_DIR / "analyzed"
QA_FILE = OUTPUT_DIR / "deliverable_quality_report.json"
PLAN_QA_FILE = OUTPUT_DIR / "research_plan_report.json"
EVIDENCE_QA_FILE = OUTPUT_DIR / "raw" / "quality_report.json"
RESEARCH_RESULTS_QA_FILE = OUTPUT_DIR / "research_results_quality_report.json"


STANDARD_REQUIREMENTS = {
    "top_down_market_sizing": r"top[\s-]?down|自上而下",
    "bottom_up_market_sizing": r"bottom[\s-]?up|自下而上",
    "tam": r"\bTAM\b",
    "sam": r"\bSAM\b",
    "som": r"\bSOM\b",
    "scenario_downside": r"下行|downside",
    "scenario_base": r"基准|base",
    "scenario_upside": r"上行|upside",
    "sizing_reconciliation": r"差异率|差异解释|reconcil|divergence",
    "business_model_classification": r"商业模式|收入引擎|revenue engine|business model",
    "atomic_economic_unit": r"最小经济单元|atomic economic unit|atomic unit",
    "revenue_equation": r"收入公式|revenue equation|revenue formula",
    "contribution_or_break_even": r"贡献利润|贡献毛利|盈亏平衡|contribution margin|break[\s-]?even",
    "input_evidence_status": r"证据状态|evidence status|sourced benchmark|observed|assumption|unavailable",
    "evidence_ids": r"\bEV-\d{4}(?:-[0-9a-f]{8,12})?\b",
    "source_urls": r"https?://",
    "claim_status_separation": r"关键结论可信度|critical claim status|fully supported.*provisional|已充分支持.*暂定",
}

FLASH_REQUIREMENTS = {
    "decision": r"决策|decision",
    "contrary_evidence": r"反方证据|contrary evidence",
    "next_gate": r"决策门|decision gate",
    "sources": r"来源|sources|https?://",
}

DYNAMIC_MODULE_REQUIREMENTS = {
    "trend_inference": {
        "industry_trend_result": r"行业趋势|共同路径|重复路径|observed pattern|industry trend|recurring pattern",
        "trend_denominator_or_counterexample": r"反例|不符合|样本分母|匹配主体|counterexample|non[\s-]?matching|denominator",
    },
    "geographic_sequencing": {
        "actor_entry_chronology": r"进入时间线|首次进入|上线时间线|entry chronology|first entry|launch chronology",
        "direct_entry_answer": r"为什么不直接|直接进入|why not.*direct|direct entry",
    },
    "market_concentration": {
        "concentration_result": r"\bCR3\b|\bCR5\b|\bHHI\b|集中度无法确认|concentration unconfirmed",
    },
    "real_case_studies": {
        "real_case_results": r"真实案例|真实样本|real[\s-]?world case|case stud",
    },
    "benchmark_ranges": {
        "benchmark_ranges": r"基准区间|可比区间|benchmark range|comparable range",
    },
    "stress_test": {
        "stress_scenario": r"压力情景|压力测试|极端情景|stress scenario|stress test",
    },
}

SECTION_FILES = {
    "executive_summary": "executive_summary.md",
    "chapter_01": "ch01_analysis.md",
    "chapter_02": "ch02_analysis.md",
    "chapter_03": "ch03_analysis.md",
    "chapter_04": "ch04_analysis.md",
    "chapter_05": "ch05_analysis.md",
}

SECTION_MARKERS = {
    "executive_summary": r"(?m)^##\s+管理层摘要\s*$",
    "chapter_01": r"(?m)^##\s+0?1\b.*$",
    "chapter_02": r"(?m)^##\s+0?2\b.*$",
    "chapter_03": r"(?m)^##\s+0?3\b.*$",
    "chapter_04": r"(?m)^##\s+0?4\b.*$",
    "chapter_05": r"(?m)^##\s+0?5\b.*$",
}

SECTION_REQUIREMENTS = {
    "executive_summary": {
        "decision": r"一句话结论|核心结论|决策|推荐",
        "launch_bet_card": r"首发下注卡",
        "target_segment_and_wedge": r"目标赛道.*首发(?:品类|产品|楔子)|首发(?:品类|产品|楔子).*目标赛道",
        "user_job_and_product": r"目标用户.*(?:核心任务|触发场景).*(?:产品入口|产品形态)|(?:产品入口|产品形态).*目标用户",
        "why_now": r"为什么是现在|进入时点|拐点|why now",
        "right_to_win": r"Right to Win|凭什么赢|获胜基础|独特资产",
        "contrary_evidence": r"反方|反对|最大风险|contrary",
        "management_ask": r"管理层.*批准|需要.*批准|待决事项|management ask",
    },
    "chapter_01": {
        "top_down": r"top[\s-]?down|自上而下",
        "bottom_up": r"bottom[\s-]?up|自下而上",
        "tam_sam_som": r"\bTAM\b.*\bSAM\b.*\bSOM\b",
        "three_scenarios": r"下行.*基准.*上行|downside.*base.*upside",
        "reconciliation": r"差异率|差异解释|口径差异|reconcil|divergence",
    },
    "chapter_02": {
        "revenue_engine": r"收入引擎|商业模式|revenue engine",
        "atomic_unit": r"最小经济单元|atomic economic unit|atomic unit",
        "equation": r"收入公式|测算公式|revenue equation|revenue formula",
        "input_status": r"证据状态|observed|sourced benchmark|assumption|unavailable",
        "contribution_or_break_even": r"贡献利润|贡献毛利|盈亏平衡|contribution margin|break[\s-]?even",
        "three_scenarios": r"下行.*基准.*上行|downside.*base.*upside",
    },
    "chapter_03": {
        "competitive_system": r"竞争系统|竞品|替代方案|潜在进入者",
        "control_points": r"控制点|数据.*分发|客户关系|关键控制",
        "defensibility": r"护城河|网络效应|切换成本|可守住|defensib",
    },
    "chapter_04": {
        "right_to_win": r"Right to Win|凭什么赢|独特资产",
        "strategic_options": r"战略选项|选项一|选项 A|option",
        "build_buy_partner": r"Build|Buy|Partner|自建|收购|合作",
        "tradeoffs": r"机会成本|权衡|可逆性|不做什么|主要风险",
    },
    "chapter_05": {
        "single_bet": r"单一推荐|推荐下注|首选下注|一句话推荐",
        "launch_bet_card": r"首发下注卡",
        "target_segment": r"目标赛道",
        "first_wedge": r"首发品类|产品楔子|首发产品",
        "target_user": r"目标用户",
        "triggering_job": r"核心触发场景|核心任务|用户任务",
        "product_surface": r"产品入口|产品载体",
        "product_form": r"产品形态",
        "user_journey": r"端到端用户路径|用户路径",
        "supply_model": r"供给获取方式|供给方式",
        "transaction_boundary": r"交易与履约边界|交易/履约边界|履约边界",
        "payer_revenue_model": r"商业模式/付费方|付费方.*商业模式|商业模式.*付费方",
        "pilot_geography": r"首发城市|首发区域|试点城市|试点区域",
        "primary_alternative": r"主要竞品|替代方案",
        "falsification_metric": r"90\s*天证伪指标|证伪指标",
        "explicit_non_goals": r"明确不做",
        "roadmap": r"0[–—-]3.*3[–—-]6.*6[–—-]12|未来 90 天|未来90天|90 天",
        "owners_resources": r"Owner|责任人|协同.*资源|资源.*决策门",
        "metrics": r"领先指标|结果指标|战略指标|关键指标",
        "continue_pivot_kill": r"Continue.*Pivot.*Kill|继续.*调整.*停止",
        "risk_and_approval": r"风险.*管理层|管理层.*批准|待决事项",
    },
}

DEPTH_FLOORS = {
    "standard": {"report": 8000, "executive_summary": 500, "chapter": 1000, "evidence_ids_per_chapter": 1},
    "deep": {"report": 18000, "executive_summary": 800, "chapter": 1800, "evidence_ids_per_chapter": 1},
}


def validate_patterns(content: str, requirements: dict[str, str]) -> list[str]:
    return [name for name, pattern in requirements.items() if not re.search(pattern, content, re.I | re.S)]


def non_whitespace_chars(content: str) -> int:
    return len(re.sub(r"\s+", "", content))


def split_report_sections(content: str) -> dict[str, str]:
    starts = []
    for name, marker in SECTION_MARKERS.items():
        match = re.search(marker, content, re.I)
        if match:
            starts.append((match.start(), name))
    starts.sort()
    sections = {}
    for index, (start, name) in enumerate(starts):
        end = starts[index + 1][0] if index + 1 < len(starts) else len(content)
        sections[name] = content[start:end]
    return sections


def load_report_components(content: str, analyzed_dir: Path = ANALYZED_DIR) -> dict[str, str]:
    components = split_report_sections(content)
    for name, filename in SECTION_FILES.items():
        path = analyzed_dir / filename
        if path.exists():
            components[name] = path.read_text(encoding="utf-8")
    return components


def analyze_report_substance(
    content: str,
    mode: str,
    active_modules: list[str],
    components: dict[str, str],
    research_results: dict | None = None,
) -> dict:
    if mode == "flash":
        return {"metrics": {"report_non_whitespace_chars": non_whitespace_chars(content)}, "failures": []}

    floors = DEPTH_FLOORS[mode]
    failures = []
    section_metrics = {}
    report_chars = non_whitespace_chars(content)
    if report_chars < floors["report"]:
        failures.append(f"depth:report_chars:{report_chars}<{floors['report']}")

    for section, requirements in SECTION_REQUIREMENTS.items():
        section_content = components.get(section, "")
        char_count = non_whitespace_chars(section_content)
        evidence_ids = len(set(re.findall(r"\bEV-\d{4}(?:-[0-9a-f]{8,12})?\b", section_content, re.I)))
        section_metrics[section] = {"non_whitespace_chars": char_count, "unique_evidence_ids": evidence_ids}
        minimum_chars = floors["executive_summary"] if section == "executive_summary" else floors["chapter"]
        if char_count < minimum_chars:
            failures.append(f"depth:{section}_chars:{char_count}<{minimum_chars}")
        for item in validate_patterns(section_content, requirements):
            failures.append(f"section_contract:{section}:{item}")
        if section.startswith("chapter_") and evidence_ids < floors["evidence_ids_per_chapter"]:
            failures.append(
                f"section_evidence:{section}:{evidence_ids}<{floors['evidence_ids_per_chapter']}"
            )

    launch_sections = "\n".join(
        [components.get("executive_summary", ""), components.get("chapter_05", "")]
    )
    unresolved_launch_choice = bool(re.search(r"TBD|证据不足|尚未确定|待确定", launch_sections, re.I))
    conditional_recommendation = bool(re.search(r"条件性推荐|conditional recommendation", launch_sections, re.I))
    if unresolved_launch_choice and not conditional_recommendation:
        failures.append("launch_bet:unresolved_field_requires_conditional_recommendation")

    unresolved_placeholders = sorted(set(re.findall(r"\[[A-Z][A-Z0-9_]{2,}\]", content)))
    failures.extend(f"placeholder_unresolved:{item}" for item in unresolved_placeholders)

    if "real_case_studies" in active_modules and research_results:
        cases_payload = research_results.get("modules", {}).get("real_case_studies", {})
        if cases_payload.get("status") == "complete":
            case_names = [
                str(item.get("name", "")).strip()
                for item in cases_payload.get("cases", [])
                if isinstance(item, dict) and str(item.get("name", "")).strip()
            ]
            missing_cases = [name for name in case_names if name.lower() not in content.lower()]
            failures.extend(f"case_missing_from_report:{name}" for name in missing_cases)

    return {
        "metrics": {"report_non_whitespace_chars": report_chars, "sections": section_metrics},
        "failures": failures,
    }


def latest_artifact(suffix: str) -> Path | None:
    matches = sorted(OUTPUT_DIR.glob(f"*.{suffix}"), key=lambda item: item.stat().st_mtime, reverse=True)
    return matches[0] if matches else None


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate report economics, sizing and requested output formats")
    parser.add_argument("--report", required=True, help="Path to the canonical Markdown report or decision brief")
    args = parser.parse_args()

    config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    mode, formats, intake_failures = validate_intake_config(config)
    if intake_failures:
        print(json.dumps({"status": "fail", "failures": intake_failures}, ensure_ascii=False, indent=2))
        return 3
    report_path = Path(args.report).expanduser().resolve()
    content = report_path.read_text(encoding="utf-8") if report_path.exists() else ""
    requirements = FLASH_REQUIREMENTS if mode == "flash" else STANDARD_REQUIREMENTS
    missing_contract_items = validate_patterns(content, requirements)
    active_modules = [str(item) for item in config.get("research_design", {}).get("active_modules", [])]
    for module in active_modules:
        module_requirements = DYNAMIC_MODULE_REQUIREMENTS.get(module, {})
        missing_contract_items.extend(
            f"{module}:{item}" for item in validate_patterns(content, module_requirements)
        )
    research_results_file = ANALYZED_DIR / "research_design_results.json"
    research_results = (
        json.loads(research_results_file.read_text(encoding="utf-8"))
        if research_results_file.exists() else {}
    )
    substance = analyze_report_substance(
        content,
        mode,
        active_modules,
        load_report_components(content),
        research_results,
    )

    artifacts = {"canonical_md": str(report_path) if report_path.exists() else None}
    missing_artifacts = []
    for suffix in formats:
        if suffix == "md":
            artifact = report_path if report_path.suffix.lower() == ".md" and report_path.exists() else None
        else:
            artifact = latest_artifact(suffix)
        artifacts[suffix] = str(artifact) if artifact else None
        if artifact is None:
            missing_artifacts.append(suffix)

    failures = []
    gate_files = {
        "research_plan": PLAN_QA_FILE,
        "evidence": EVIDENCE_QA_FILE,
        "research_results": RESEARCH_RESULTS_QA_FILE,
    }
    gate_statuses = {}
    for gate_name, gate_file in gate_files.items():
        if not gate_file.exists():
            gate_statuses[gate_name] = "missing"
            failures.append(f"{gate_name}_quality_report_missing")
            continue
        gate_status = str(json.loads(gate_file.read_text(encoding="utf-8")).get("status", "missing"))
        gate_statuses[gate_name] = gate_status
        if gate_status != "pass":
            failures.append(f"{gate_name}_quality_gate_failed")
    if not report_path.exists():
        failures.append("canonical_report_missing")
    failures.extend(f"contract_missing:{item}" for item in missing_contract_items)
    failures.extend(substance["failures"])
    failures.extend(f"artifact_missing:{item}" for item in missing_artifacts)

    result = {
        "validated_at": datetime.now().astimezone().isoformat(),
        "status": "pass" if not failures else "fail",
        "research_mode": mode,
        "active_modules": active_modules,
        "selected_formats": formats,
        "canonical_report": str(report_path),
        "artifacts": artifacts,
        "missing_contract_items": missing_contract_items,
        "missing_artifacts": missing_artifacts,
        "substance_metrics": substance["metrics"],
        "substance_failures": substance["failures"],
        "research_results_quality_report": str(RESEARCH_RESULTS_QA_FILE) if RESEARCH_RESULTS_QA_FILE.exists() else None,
        "gate_statuses": gate_statuses,
        "failures": failures,
        "note": "DOCX/PPTX presence is checked here; page/slide rendering and editability still require their format-specific skills.",
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    QA_FILE.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "pass" else 3


if __name__ == "__main__":
    raise SystemExit(main())
