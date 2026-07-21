#!/usr/bin/env python3
"""Validate inferred trends, claims and dynamic module results against the evidence ledger."""

from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime
from pathlib import Path


AGENT_DIR = Path(os.environ.get("AGENT_DIR", Path(__file__).resolve().parent.parent))
CONFIG_FILE = AGENT_DIR / "config.json"
RAW_DIR = AGENT_DIR / "output" / "raw"
ANALYZED_DIR = AGENT_DIR / "output" / "analyzed"
RESULTS_FILE = ANALYZED_DIR / "research_design_results.json"
OUTPUT_FILE = AGENT_DIR / "output" / "research_results_quality_report.json"
VALID_CLAIM_STATUS = {"supported", "mixed", "provisional", "rejected"}
VALID_HYPOTHESIS_VERDICTS = {"supported", "partially_supported", "not_supported", "inconclusive"}
VALID_TREND_CLASSES = {"supported_in_sample", "emerging_signal", "isolated_case", "mixed", "inconclusive"}
VALID_MODULE_STATUS = {"complete", "insufficient_evidence", "not_selected"}
VALID_COUNTER_STATUS = {"found", "searched_none_found", "not_applicable"}
VALID_OBSERVED_PATTERNS = {"supported_in_sample", "recurring_signal", "mixed", "insufficient_evidence"}
VALID_MEMORY_CLASSES = {
    "operational",
    "user_preference",
    "source_cache",
    "run_context",
    "evaluation_learning",
    "conclusion",
}


def listify(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def main() -> int:
    config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    ledger_path = RAW_DIR / "evidence_ledger.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8")) if ledger_path.exists() else {"evidence": []}
    results = json.loads(RESULTS_FILE.read_text(encoding="utf-8")) if RESULTS_FILE.exists() else {}
    evidence = ledger.get("evidence", [])
    evidence_by_id = {str(item.get("evidence_id")): item for item in evidence if item.get("evidence_id")}
    active_modules = [str(item) for item in config.get("research_design", {}).get("active_modules", [])]
    failures = []
    warnings = []

    def fail(check: str, detail: object) -> None:
        failures.append({"check": check, "detail": detail})

    def validate_evidence_ids(check: str, ids: object, deep_required: bool = False) -> list[dict]:
        normalized = listify(ids)
        unknown = [item for item in normalized if item not in evidence_by_id]
        if unknown:
            fail(f"{check}:unknown_evidence", unknown)
        known = [evidence_by_id[item] for item in normalized if item in evidence_by_id]
        if deep_required:
            shallow = [item.get("evidence_id") for item in known if item.get("read_status") != "deep_read"]
            if shallow:
                fail(f"{check}:deep_read_required", shallow)
        return known

    classification = config.get("classification", {}) if isinstance(config.get("classification", {}), dict) else {}
    classification_review = results.get("classification_review", {})
    if str(config["research_mode"]) != "flash":
        if not isinstance(classification_review, dict) or not classification_review:
            fail("classification_review", "missing")
        else:
            if classification_review.get("decision_type") != classification.get("decision_type"):
                fail("classification_review:decision_type", {
                    "configured": classification.get("decision_type"),
                    "reviewed": classification_review.get("decision_type"),
                })
            if classification_review.get("deliverable_intent") != classification.get("deliverable_intent"):
                fail("classification_review:deliverable_intent", {
                    "configured": classification.get("deliverable_intent"),
                    "reviewed": classification_review.get("deliverable_intent"),
                })
            if not isinstance(classification_review.get("question_type_coverage", []), list):
                fail("classification_review:question_type_coverage", "must be a list")

    memory_policy = config.get("memory_policy", {}) if isinstance(config.get("memory_policy", {}), dict) else {}
    memory_review = results.get("memory_review", {})
    if not isinstance(memory_review, dict) or not memory_review:
        fail("memory_review", "missing")
    else:
        reused_memory = set(listify(memory_review.get("reused_memory_classes", [])))
        blocked_memory = set(listify(memory_review.get("blocked_memory_classes", [])))
        invalid_memory = sorted((reused_memory | blocked_memory) - VALID_MEMORY_CLASSES)
        if invalid_memory:
            fail("memory_review:valid_classes", invalid_memory)
        if "conclusion" in reused_memory:
            fail("memory_review:conclusion_reuse", "conclusion memory cannot be reused")
        expected_blocked = set(listify(memory_policy.get("blocked_memory_classes", [])))
        missing_blocked = sorted(expected_blocked - blocked_memory)
        if missing_blocked:
            fail("memory_review:blocked_classes_disclosed", missing_blocked)
        if memory_policy.get("source_cache_requires_revalidation") is True and "source_cache" in reused_memory:
            if not memory_review.get("source_cache_revalidated"):
                fail("memory_review:source_cache_revalidated", "required when source_cache is reused")

    configured_hypotheses = {
        str(item.get("id")): item
        for item in config.get("user_hypotheses", [])
        if isinstance(item, dict) and item.get("id")
    }
    assessments = {
        str(item.get("hypothesis_id")): item
        for item in results.get("hypothesis_assessments", [])
        if isinstance(item, dict) and item.get("hypothesis_id")
    }
    for hypothesis_id, hypothesis in configured_hypotheses.items():
        if not hypothesis.get("must_test", True):
            continue
        assessment = assessments.get(hypothesis_id)
        if not assessment:
            fail(f"hypothesis:{hypothesis_id}:assessment", "missing")
            continue
        if assessment.get("verdict") not in VALID_HYPOTHESIS_VERDICTS:
            fail(f"hypothesis:{hypothesis_id}:verdict", assessment.get("verdict"))
        if not str(assessment.get("explanation", "")).strip():
            fail(f"hypothesis:{hypothesis_id}:explanation", "missing")
        if assessment.get("counter_search_status") not in VALID_COUNTER_STATUS - {"not_applicable"}:
            fail(f"hypothesis:{hypothesis_id}:counter_search", assessment.get("counter_search_status"))
        validate_evidence_ids(f"hypothesis:{hypothesis_id}:support", assessment.get("supporting_evidence_ids", []), True)
        validate_evidence_ids(f"hypothesis:{hypothesis_id}:opposition", assessment.get("opposing_evidence_ids", []), True)

    trends = [item for item in results.get("inferred_trends", []) if isinstance(item, dict)]
    if "trend_inference" in active_modules and not trends:
        fail("trend_inference:result", "at least one inferred or inconclusive trend required")
    for index, trend in enumerate(trends, start=1):
        trend_id = str(trend.get("id", f"T{index}"))
        classification = trend.get("classification")
        if classification not in VALID_TREND_CLASSES:
            fail(f"trend:{trend_id}:classification", classification)
        for field in ("pattern", "scope", "actor_population", "sample_selection_basis"):
            if not str(trend.get(field, "")).strip():
                fail(f"trend:{trend_id}:{field}", "missing")
        if trend.get("generalizability") not in {"sample_only", "representative_population"}:
            fail(f"trend:{trend_id}:generalizability", trend.get("generalizability"))
        if trend.get("generalizability") == "representative_population" and not str(trend.get("representativeness_basis", "")).strip():
            fail(f"trend:{trend_id}:representativeness_basis", "required for representative_population")
        traces = [item for item in trend.get("actor_traces", []) if isinstance(item, dict)]
        actors = [str(item.get("actor", "")).strip() for item in traces if str(item.get("actor", "")).strip()]
        if len(actors) != len(set(actors)):
            fail(f"trend:{trend_id}:unique_actors", actors)
        minimum_actors = 3 if classification == "supported_in_sample" else 2 if classification in {"emerging_signal", "mixed"} else 1
        if classification != "inconclusive" and len(actors) < minimum_actors:
            fail(f"trend:{trend_id}:actor_count", {"actual": len(actors), "required": minimum_actors})
        if classification == "inconclusive" and not str(trend.get("limitations", "")).strip():
            fail(f"trend:{trend_id}:limitations", "required for inconclusive")
        matching = 0
        non_matching = 0
        unknown = 0
        trend_source_families = set()
        for trace in traces:
            actor = str(trace.get("actor", "unknown"))
            chronology = trace.get("chronology", [])
            if not isinstance(chronology, list) or not chronology:
                fail(f"trend:{trend_id}:actor:{actor}:chronology", "missing")
            if trace.get("matches_pattern") is True:
                matching += 1
            elif trace.get("matches_pattern") is False:
                non_matching += 1
            else:
                unknown += 1
            trace_evidence = validate_evidence_ids(f"trend:{trend_id}:actor:{actor}", trace.get("evidence_ids", []), True)
            trend_source_families.update(
                item.get("source_family", item.get("domain"))
                for item in trace_evidence
                if item.get("source_family", item.get("domain"))
            )
        declared_matching = int(trend.get("matching_actor_count", matching))
        declared_non_matching = int(trend.get("non_matching_actor_count", non_matching))
        declared_unknown = int(trend.get("unknown_actor_count", unknown))
        if declared_matching != matching or declared_non_matching != non_matching or declared_unknown != unknown:
            fail(f"trend:{trend_id}:actor_denominator", {
                "declared_matching": declared_matching,
                "observed_matching": matching,
                "declared_non_matching": declared_non_matching,
                "observed_non_matching": non_matching,
                "declared_unknown": declared_unknown,
                "observed_unknown": unknown,
                "sample_total": len(traces),
            })
        if matching + non_matching + unknown != len(traces):
            fail(f"trend:{trend_id}:sample_total", {"classified": matching + non_matching + unknown, "traces": len(traces)})
        if classification == "supported_in_sample" and (matching < 3 or matching <= non_matching):
            fail(f"trend:{trend_id}:sample_support_threshold", {"matching": matching, "non_matching": non_matching, "unknown": unknown})
        if classification == "supported_in_sample" and len(trend_source_families) < 2:
            fail(f"trend:{trend_id}:source_independence", {"actual": len(trend_source_families), "required": 2})
        if not isinstance(trend.get("counterexamples", []), list):
            fail(f"trend:{trend_id}:counterexamples", "must be a list")

    claims = [item for item in results.get("critical_claims", []) if isinstance(item, dict)]
    if str(config["research_mode"]) != "flash" and not claims:
        fail("critical_claims", "at least one claim required")
    corroborated = 0
    counter_searched = 0
    unresolved = 0
    for index, claim in enumerate(claims, start=1):
        claim_id = str(claim.get("id", f"C{index}"))
        status = claim.get("status")
        if status not in VALID_CLAIM_STATUS:
            fail(f"claim:{claim_id}:status", status)
        if not str(claim.get("statement", "")).strip():
            fail(f"claim:{claim_id}:statement", "missing")
        scope = claim.get("scope")
        if not isinstance(scope, dict) or not scope:
            fail(f"claim:{claim_id}:scope", "missing")
        supporting = validate_evidence_ids(f"claim:{claim_id}:support", claim.get("supporting_evidence_ids", []), True)
        opposing = validate_evidence_ids(f"claim:{claim_id}:opposition", claim.get("opposing_evidence_ids", []), True)
        families = {item.get("source_family", item.get("domain")) for item in supporting if item.get("source_family", item.get("domain"))}
        counter_status = claim.get("counter_search_status")
        if counter_status in {"found", "searched_none_found"}:
            counter_searched += 1
        else:
            fail(f"claim:{claim_id}:counter_search", counter_status)
        if status == "supported":
            if len(families) < 2:
                fail(f"claim:{claim_id}:corroboration", {"domains": len(families), "required": 2})
            else:
                corroborated += 1
        elif status == "mixed":
            if not supporting or not opposing:
                fail(f"claim:{claim_id}:mixed_evidence", "supporting and opposing evidence required")
            unresolved += 1
        elif status == "provisional":
            if not str(claim.get("limitation", "")).strip():
                fail(f"claim:{claim_id}:limitation", "required for provisional")
            unresolved += 1
        if status == "rejected" and str(claim.get("recommendation_dependency", "")).lower() in {"true", "required", "yes"}:
            fail(f"claim:{claim_id}:rejected_dependency", "rejected claim cannot remain a recommendation premise")

    modules = results.get("modules", {}) if isinstance(results.get("modules", {}), dict) else {}
    for module in active_modules:
        payload = modules.get(module, {}) if isinstance(modules.get(module, {}), dict) else {}
        status = payload.get("status")
        if status not in VALID_MODULE_STATUS - {"not_selected"}:
            fail(f"module:{module}:status", status)
            continue
        if status == "insufficient_evidence" and not str(payload.get("limitations", "")).strip():
            fail(f"module:{module}:limitations", "required for insufficient_evidence")

    concentration = modules.get("market_concentration", {})
    if "market_concentration" in active_modules and concentration.get("status") == "complete":
        if concentration.get("classification") not in {"high", "moderate", "fragmented", "unconfirmed"}:
            fail("module:market_concentration:classification", concentration.get("classification"))
        if concentration.get("classification") != "unconfirmed" and not concentration.get("metrics"):
            fail("module:market_concentration:metrics", "CR3/CR5/HHI or a comparable proxy required")
        validate_evidence_ids("module:market_concentration", concentration.get("evidence_ids", []), True)

    geography = modules.get("geographic_sequencing", {})
    if "geographic_sequencing" in active_modules and geography.get("status") == "complete":
        if geography.get("observed_pattern") not in VALID_OBSERVED_PATTERNS:
            fail("module:geographic_sequencing:observed_pattern", geography.get("observed_pattern"))
        timeline_cases = [item for item in geography.get("timeline_cases", []) if isinstance(item, dict)]
        entities = [str(item.get("entity", "")).strip() for item in timeline_cases if str(item.get("entity", "")).strip()]
        if len(entities) < 3:
            fail("module:geographic_sequencing:timeline_cases", {"actual": len(entities), "required": 3})
        if len(entities) != len(set(entities)):
            fail("module:geographic_sequencing:unique_timeline_entities", entities)
        for index, item in enumerate(timeline_cases, start=1):
            entity = str(item.get("entity", f"case-{index}"))
            if not isinstance(item.get("chronology"), list) or not item.get("chronology"):
                fail(f"module:geographic_sequencing:timeline:{entity}", "chronology required")
            validate_evidence_ids(
                f"module:geographic_sequencing:timeline:{entity}",
                item.get("evidence_ids", []),
                True,
            )
        if len(geography.get("regions", [])) < 2:
            fail("module:geographic_sequencing:regions", ">=2 required")
        if len(geography.get("candidate_paths", [])) < 2:
            fail("module:geographic_sequencing:candidate_paths", ">=2 required")
        if not str(geography.get("why_not_largest_value_market_first", "")).strip():
            fail("module:geographic_sequencing:direct_entry_answer", "missing")
        validate_evidence_ids("module:geographic_sequencing", geography.get("evidence_ids", []), True)

    cases_payload = modules.get("real_case_studies", {})
    if "real_case_studies" in active_modules and cases_payload.get("status") == "complete":
        cases = [item for item in cases_payload.get("cases", []) if isinstance(item, dict)]
        required = int(config.get("research_design", {}).get("case_studies", {}).get("minimum", 0))
        if len(cases) < required:
            fail("module:real_case_studies:count", {"actual": len(cases), "required": required})
        case_names = [str(item.get("name", "")).strip() for item in cases if str(item.get("name", "")).strip()]
        if len(case_names) != len(set(case_names)):
            fail("module:real_case_studies:unique_cases", case_names)
        case_families = set()
        for index, case in enumerate(cases, start=1):
            case_name = str(case.get("name", f"case-{index}"))
            if case.get("real_world") is not True:
                fail(f"case:{case_name}:real_world", case.get("real_world"))
            if not str(case.get("selection_basis", "")).strip():
                fail(f"case:{case_name}:selection_basis", "missing")
            if not isinstance(case.get("analysis_dimensions"), dict) or not case.get("analysis_dimensions"):
                fail(f"case:{case_name}:analysis_dimensions", "missing")
            case_evidence = validate_evidence_ids(f"case:{case_name}", case.get("evidence_ids", []), True)
            case_families.update(
                item.get("source_family", item.get("domain"))
                for item in case_evidence
                if item.get("source_family", item.get("domain"))
            )
        if cases and len(case_families) < 2:
            fail("module:real_case_studies:source_independence", {"actual": len(case_families), "required": 2})

    benchmarks = modules.get("benchmark_ranges", {})
    if "benchmark_ranges" in active_modules and benchmarks.get("status") == "complete":
        items = [item for item in benchmarks.get("benchmarks", []) if isinstance(item, dict)]
        if not items:
            fail("module:benchmark_ranges:benchmarks", "at least one required")
        for index, item in enumerate(items, start=1):
            for field in ("metric", "value_or_range", "unit", "geography", "period", "comparison_scope"):
                if not str(item.get(field, "")).strip():
                    fail(f"benchmark:{index}:{field}", "missing")
            validate_evidence_ids(f"benchmark:{index}", item.get("evidence_ids", []), True)

    stress = modules.get("stress_test", {})
    if "stress_test" in active_modules and stress.get("status") == "complete":
        scenarios = [item for item in stress.get("scenarios", []) if isinstance(item, dict)]
        if not scenarios:
            fail("module:stress_test:scenarios", "at least one required")
        for index, item in enumerate(scenarios, start=1):
            for field in ("name", "trigger", "impact", "leading_signal", "response", "decision_gate"):
                if not str(item.get(field, "")).strip():
                    fail(f"stress:{index}:{field}", "missing")

    deep_read_count = sum(item.get("read_status") == "deep_read" for item in evidence)
    primary_count = sum(item.get("read_status") == "deep_read" and item.get("is_primary") for item in evidence)
    dated_count = sum(bool(item.get("published_at")) for item in evidence)
    report_card = {
        "deep_read_coverage": round(deep_read_count / max(len(evidence), 1), 4),
        "primary_share_of_deep_reads": round(primary_count / max(deep_read_count, 1), 4),
        "freshness_metadata_coverage": round(dated_count / max(len(evidence), 1), 4),
        "critical_claim_corroboration_rate": round(corroborated / max(len(claims), 1), 4),
        "counter_search_completion_rate": round(counter_searched / max(len(claims), 1), 4),
        "unresolved_critical_claims": unresolved,
        "critical_claim_status_counts": dict(Counter(str(item.get("status")) for item in claims)),
        "fully_supported_claim_rate": round(
            sum(item.get("status") == "supported" for item in claims) / max(len(claims), 1), 4
        ),
        "mixed_or_provisional_claim_rate": round(
            sum(item.get("status") in {"mixed", "provisional"} for item in claims) / max(len(claims), 1), 4
        ),
        "active_module_completion": {
            module: modules.get(module, {}).get("status", "missing") for module in active_modules
        },
    }
    report = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "status": "pass" if not failures else "fail",
        "active_modules": active_modules,
        "report_card": report_card,
        "failures": failures,
        "warnings": warnings,
    }
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"研究结论闸门: {report['status'].upper()}，失败 {len(failures)} 项，警告 {len(warnings)} 项")
    return 0 if not failures else 3


if __name__ == "__main__":
    raise SystemExit(main())
