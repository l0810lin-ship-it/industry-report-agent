from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts" / "project-template" / "scripts"
sys.path.insert(0, str(SCRIPTS))


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


enrich = load_module("enrich_evidence", "enrich_evidence.py")
collector = load_module("collect_reach", "collect_reach.py")
deliverable = load_module("validate_deliverable", "validate_deliverable.py")
knowledge = load_module("process_knowledge", "process_knowledge.py")
plan = load_module("validate_research_plan", "validate_research_plan.py")


class EvidencePoolRegressionTests(unittest.TestCase):
    def test_direct_sources_do_not_suppress_search_candidates(self):
        direct = {
            "backend": "Direct authoritative URL",
            "query": "official filing",
            "question_ids": ["RQ1"],
            "raw_evidence": "Title: Official filing\nURL: https://example.com/filing\nHighlights: primary",
        }
        discovered = {
            "backend": "Bing HTML fallback",
            "query": "market competitors",
            "question_ids": ["RQ1"],
            "raw_evidence": "Title: Competitor analysis\nURL: https://research.example.org/analysis\nHighlights: discovered",
        }
        candidates = []
        enrich.add_exa_candidates(candidates, direct, "industry")
        enrich.add_exa_candidates(candidates, discovered, "industry")

        self.assertEqual(2, len(candidates))
        self.assertEqual(["direct"], candidates[0]["source_origins"])
        self.assertEqual(["search"], candidates[1]["source_origins"])

    def test_adaptive_discovery_expands_until_novelty_saturates(self):
        calls = []

        def fake_search(spec, limit):
            calls.append(limit)
            available = min(limit, 11)
            blocks = [
                f"Title: Result {index}\nURL: https://example.com/{index}\nHighlights: topic"
                for index in range(available)
            ]
            return {**spec, "backend": "fake", "raw_evidence": "\n\n".join(blocks)}, None

        result, error = collector.adaptive_discovery_search(
            {"query": "topic"}, 5, 20, 5, 2, search_fn=fake_search
        )
        self.assertIsNone(error)
        self.assertEqual([5, 10, 15], calls)
        self.assertEqual(11, result["returned_unique_urls"])
        self.assertEqual("novelty_saturated", result["discovery_stop_reason"])

    def test_relevance_filter_rejects_unrelated_search_noise(self):
        original_config = enrich.CONFIG
        enrich.CONFIG = {
            "target": {"company": "百度", "industry": "本地生活AI"},
            "competitors": ["美团"],
        }
        try:
            relevant = {
                "source_origins": ["search"], "entity": "美团",
                "query": "美团 本地生活 AI 商户",
                "title": "美团发布本地生活商户AI经营工具", "discovery_excerpt": "商户经营与交易",
                "url": "https://example.com/meituan-ai",
            }
            noise = {
                "source_origins": ["search"], "entity": "",
                "query": "百度 本地生活 AI 商户",
                "title": "Outlook personal email", "discovery_excerpt": "Calendar and mail",
                "url": "https://example.com/outlook",
            }
            self.assertEqual("relevant", enrich.assess_relevance(relevant)[0])
            self.assertEqual("rejected_low_relevance", enrich.assess_relevance(noise)[0])
        finally:
            enrich.CONFIG = original_config


class DeliverableSubstanceRegressionTests(unittest.TestCase):
    @staticmethod
    def dense_components():
        filler = "有边界的证据分析与决策含义。" * 220
        evidence = " EV-0001-abcdef1234 "
        return {
            "executive_summary": (
                "核心结论与推荐。首发下注卡：目标赛道与首发产品/产品楔子；目标用户、核心任务、产品入口与产品形态。"
                "为什么是现在：市场拐点。Right to Win 独特资产。"
                "最强反方证据与最大风险。需要管理层批准预算。" + evidence + filler
            ),
            "chapter_01": (
                "自上而下 Top-down；自下而上 Bottom-up；TAM、SAM、SOM。"
                "下行、基准、上行情景。差异率与口径差异解释。" + evidence + filler
            ),
            "chapter_02": (
                "收入引擎与商业模式；最小经济单元；收入公式。"
                "输入证据状态 observed / sourced benchmark / assumption / unavailable。"
                "贡献利润与盈亏平衡。下行、基准、上行情景。" + evidence + filler
            ),
            "chapter_03": (
                "竞争系统包括竞品、替代方案与潜在进入者。关键控制点覆盖数据、分发和客户关系。"
                "护城河、网络效应、切换成本与可守住的优势。" + evidence + filler
            ),
            "chapter_04": (
                "Right to Win 来自独特资产。战略选项一与选项二。"
                "Build、Buy、Partner 组合。机会成本、主要风险、可逆性与不做什么。" + evidence + filler
            ),
            "chapter_05": (
                "单一推荐与一句话推荐。首发下注卡：目标赛道、首发品类/产品楔子、目标用户、"
                "核心触发场景与任务、产品入口/载体、产品形态、端到端用户路径、供给获取方式、"
                "交易与履约边界、商业模式/付费方、首发城市/区域、主要竞品/替代方案、"
                "Right to Win、90天证伪指标、明确不做。0–3 月、3–6 月、6–12 月路线。"
                "Owner、协同、资源与决策门。领先指标、结果指标、战略指标。"
                "Continue、Pivot、Kill。风险与管理层批准。" + evidence + filler
            ),
        }

    def test_dense_deep_report_passes_substance_gate(self):
        components = self.dense_components()
        report = "\n".join(components.values())
        result = deliverable.analyze_report_substance(report, "deep", [], components, {})
        self.assertEqual([], result["failures"])

    def test_thin_deep_report_is_rejected(self):
        components = self.dense_components()
        components["chapter_04"] = "战略选项。"
        report = "简短报告" * 1000
        result = deliverable.analyze_report_substance(report, "deep", [], components, {})
        self.assertTrue(any(item.startswith("depth:report_chars") for item in result["failures"]))
        self.assertTrue(any(item.startswith("depth:chapter_04_chars") for item in result["failures"]))
        self.assertTrue(any(item.startswith("section_evidence:chapter_04") for item in result["failures"]))

    def test_unresolved_launch_choice_requires_conditional_recommendation(self):
        components = self.dense_components()
        components["chapter_05"] += "首发城市：TBD—证据不足。"
        report = "\n".join(components.values())
        result = deliverable.analyze_report_substance(report, "deep", [], components, {})
        self.assertIn(
            "launch_bet:unresolved_field_requires_conditional_recommendation",
            result["failures"],
        )


class LocalKnowledgeRegressionTests(unittest.TestCase):
    def test_shared_library_retrieves_relevant_private_evidence(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            library = root / "industry-report-knowledge"
            run_dir = root / "industry-report-runs" / "sample"
            library.mkdir(parents=True)
            run_dir.mkdir(parents=True)
            (library / "本地生活调研.md").write_text(
                "# 用户决策\n百度用户在装修等高决策本地服务中会反复搜索价格、资质和案例。",
                encoding="utf-8",
            )
            (library / "漫剧资料.md").write_text(
                "# 海外内容\nAI漫剧在海外市场依赖翻译和投流。",
                encoding="utf-8",
            )
            config = {
                "target": {"company": "百度", "industry": "本地生活AI"},
                "research_questions": [{"id": "RQ1", "question": "百度应优先进入哪个本地生活服务赛道"}],
                "knowledge": {"directory": str(library), "top_k_per_question": 1},
            }
            (run_dir / "config.json").write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")

            original_values = (knowledge.AGENT_DIR, knowledge.OUTPUT_DIR, knowledge.CONFIG_FILE)
            knowledge.AGENT_DIR = run_dir
            knowledge.OUTPUT_DIR = run_dir / "output" / "knowledge"
            knowledge.CONFIG_FILE = run_dir / "config.json"
            try:
                self.assertEqual(0, knowledge.main())
                ledger = json.loads((knowledge.OUTPUT_DIR / "private_evidence_ledger.json").read_text(encoding="utf-8"))
                self.assertEqual(1, len(ledger))
                self.assertEqual("本地生活调研.md", ledger[0]["file_name"])
                self.assertEqual("PRI-0001", ledger[0]["evidence_id"])
            finally:
                knowledge.AGENT_DIR, knowledge.OUTPUT_DIR, knowledge.CONFIG_FILE = original_values


class PlanClassificationMemoryRegressionTests(unittest.TestCase):
    @staticmethod
    def valid_config() -> dict:
        return {
            "research_mode": "standard",
            "intake": {
                "mode_selection": {"status": "selected", "source": "user_selected"},
                "format_selection": {"status": "selected", "source": "user_selected"},
            },
            "output": {"formats": ["md"]},
            "target": {"company": "百度", "industry": "本地生活AI", "region": "中国", "year": "2026"},
            "classification": {
                "decision_type": "enter_market",
                "user_role": "strategy_team",
                "time_horizon": "near_term_90_days",
                "geographic_scope": {"regions": ["中国"], "cross_border": False},
                "deliverable_intent": "management_report",
                "primary_question_types": [
                    "market_size",
                    "competition",
                    "business_model",
                    "right_to_win",
                    "validation_plan",
                ],
                "routing_rationale": "进入决策需要市场规模、竞争、商业模式、胜率和验证门。",
                "required_gates": ["plan", "evidence", "results", "deliverable"],
            },
            "research_questions": [
                {
                    "id": "RQ1",
                    "question": "百度是否应进入本地生活AI",
                    "question_types": [
                        "market_size",
                        "competition",
                        "business_model",
                        "right_to_win",
                        "validation_plan",
                    ],
                }
            ],
            "research_keywords": [{"query": "百度 本地生活 AI", "question_ids": ["RQ1"]}],
            "focus_queries": [],
            "competitor_keywords": {},
            "platform_queries": [],
            "user_hypotheses": [],
            "research_design": {"active_modules": [], "module_rationale": {}, "candidate_trends": []},
            "collection": {
                "search_results_per_query": 5,
                "adaptive_discovery": {"enabled": True, "expansion_step": 5, "min_new_urls_to_continue": 2},
                "max_deep_reads": 12,
            },
            "memory_policy": {
                "fresh_run_required": True,
                "allowed_memory_classes": ["operational", "user_preference", "source_cache", "run_context", "evaluation_learning"],
                "blocked_memory_classes": ["conclusion"],
                "source_cache_requires_revalidation": True,
                "prior_reports_as_private_sources_only": True,
                "memory_use_log": [],
            },
        }

    def run_plan_gate(self, config: dict) -> tuple[int, dict]:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            (run_dir / "config.json").write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
            original_values = (plan.AGENT_DIR, plan.CONFIG_FILE, plan.OUTPUT_FILE)
            plan.AGENT_DIR = run_dir
            plan.CONFIG_FILE = run_dir / "config.json"
            plan.OUTPUT_FILE = run_dir / "output" / "research_plan_report.json"
            try:
                code = plan.main()
                report = json.loads(plan.OUTPUT_FILE.read_text(encoding="utf-8"))
                return code, report
            finally:
                plan.AGENT_DIR, plan.CONFIG_FILE, plan.OUTPUT_FILE = original_values

    def test_plan_gate_requires_classification_and_memory_policy(self):
        config = self.valid_config()
        code, report = self.run_plan_gate(config)
        self.assertEqual(0, code)
        self.assertEqual("pass", report["status"])
        self.assertEqual("enter_market", report["classification"]["decision_type"])
        self.assertIn("conclusion", report["memory_policy"]["blocked_memory_classes"])

    def test_plan_gate_rejects_conclusion_memory_reuse(self):
        config = self.valid_config()
        config["memory_policy"]["allowed_memory_classes"].append("conclusion")
        code, report = self.run_plan_gate(config)
        self.assertEqual(3, code)
        self.assertEqual("fail", report["status"])
        self.assertTrue(any(item["check"] == "memory_policy:allowed_conclusion_memory" for item in report["failures"]))


if __name__ == "__main__":
    unittest.main()
