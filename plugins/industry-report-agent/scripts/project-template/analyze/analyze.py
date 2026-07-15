#!/usr/bin/env python3
"""
分析脚本：读取采集数据 → 调用 Claude → 生成各章节分析
用法: python analyze/analyze.py [--chapter 1-5] [--all]
"""

import json
import os
import sys
import argparse
from pathlib import Path
from datetime import datetime

# ── 路径设置 ──────────────────────────────────────────
AGENT_DIR = Path(os.environ.get("AGENT_DIR", Path(__file__).parent.parent))
OUTPUT_RAW = AGENT_DIR / "output" / "raw"
OUTPUT_ANALYZED = AGENT_DIR / "output" / "analyzed"
PROMPTS_DIR = AGENT_DIR / "prompts"
TEMPLATES_DIR = AGENT_DIR / "templates"
CONFIG_FILE = AGENT_DIR / "config.json"

OUTPUT_ANALYZED.mkdir(parents=True, exist_ok=True)


def load_config():
    with open(CONFIG_FILE) as f:
        return json.load(f)


def load_raw_data():
    """加载所有原始采集数据"""
    data = {}
    for file in OUTPUT_RAW.glob("*.json"):
        with open(file) as f:
            data[file.stem] = json.load(f)
    return data


def load_prompt(chapter_num: int) -> str:
    prompt_file = PROMPTS_DIR / f"ch0{chapter_num}_{'industry' if chapter_num==1 else 'ai_model' if chapter_num==2 else 'competitor' if chapter_num==3 else 'user_insight' if chapter_num==4 else 'strategy'}.md"
    if not prompt_file.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_file}")
    return prompt_file.read_text()


def load_executive_prompt() -> str:
    prompt_file = PROMPTS_DIR / "executive_summary.md"
    if not prompt_file.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_file}")
    return prompt_file.read_text()


def load_analyzed_chapters():
    """加载已分析的章节（用于第5章综合分析）"""
    chapters = {}
    for i in range(1, 6):
        f = OUTPUT_ANALYZED / f"ch0{i}_analysis.md"
        if f.exists():
            chapters[i] = f.read_text()
    return chapters


def validate_raw_data(raw_data: dict) -> list[str]:
    """对采集结果做基础质量校验，避免空数据也进入分析阶段。"""
    issues = []

    quality = raw_data.get("quality_report", {})
    if quality:
        if quality.get("status") != "pass":
            issues.append(f"evidence quality gate 未通过：{len(quality.get('failures', []))} 项失败")
        return issues

    industry = raw_data.get("industry_data", {})
    industry_search_results = industry.get("search_results", [])
    industry_focus_results = industry.get("focus_results", [])
    discovery_queries = len(industry_search_results) + sum(
        len(group.get("results", [])) for group in industry_focus_results
    )
    if discovery_queries < 2:
        issues.append(f"industry_data 有效发现查询过少：{discovery_queries} 个（至少 2 个）")

    competitors = raw_data.get("competitor_data", {}).get("competitors", {})
    populated_competitors = sum(
        1 for item in competitors.values()
        if len(item.get("queries", [])) >= 1 or len(item.get("news", [])) >= 2
    )
    if populated_competitors < 2:
        issues.append(f"competitor_data 有效竞品过少：{populated_competitors} 个（至少 2 个竞品各有 2 条资讯）")

    social = raw_data.get("social_data", {})
    platforms = social.get("platforms", {})
    social_total = 0
    for query_results in platforms.values():
        for query_result in query_results:
            items = query_result.get("items", [])
            social_total += len(items) if isinstance(items, list) else 1
    if platforms and social_total < 8:
        issues.append(f"social_data 已选平台结果过少：{social_total} 条（至少 8 条）")

    return issues


def call_claude(system_prompt: str, user_message: str, model: str = "claude-opus-4-8") -> str:
    """调用 Claude API"""
    try:
        import anthropic
        client = anthropic.Anthropic()
        message = client.messages.create(
            model=model,
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}]
        )
        return message.content[0].text
    except ImportError:
        print("⚠️  anthropic 包未安装，请运行: pip install anthropic")
        print("📋 或者将以下 prompt 手动粘贴到 Claude：\n")
        print("=" * 60)
        print(f"SYSTEM:\n{system_prompt}\n\nUSER:\n{user_message}")
        print("=" * 60)
        return None
    except Exception as e:
        print(f"❌ Claude API 调用失败: {e}")
        print("💡 请检查 ANTHROPIC_API_KEY 环境变量是否已设置")
        return None


def build_chapter_prompt(chapter_num: int, config: dict, raw_data: dict, analyzed_chapters: dict) -> tuple[str, str]:
    """构建章节分析的 system prompt 和 user message"""

    prompt_instructions = load_prompt(chapter_num)

    system = f"""你是一位服务互联网大厂管理层的战略分析师，负责把研究证据转化为可批准、可证伪的战略决策。
你的分析风格：
- 先回答管理问题，再给事实和逻辑链条
- 区分事实、来源陈述、推断与建议
- 重要结论附 evidence_id 与 URL，不捏造精确数字
- 主动呈现反方证据、机会成本、资源要求和停止条件

目标公司：{config['target']['company']}
目标行业：{config['target']['industry']}
研究年份：{config['target']['year']}
研究地区：{config['target']['region']}
研究模式：{config['research_mode']}
主要竞品：{', '.join(config['competitors'])}
研究设计配置：{json.dumps(config.get('research_design', {}), ensure_ascii=False)}
用户待验证线索：{json.dumps(config.get('user_hypotheses', []), ensure_ascii=False)}
商业测算配置：{json.dumps(config.get('economics', {}), ensure_ascii=False)}"""

    # 构建数据上下文
    data_context = f"\n\n## 原始采集数据摘要\n"

    if "evidence_ledger" in raw_data:
        evidence = raw_data["evidence_ledger"].get("evidence", [])
        data_context += "\n### 已标准化证据账本（优先使用）\n"
        data_context += json.dumps(evidence[:60], ensure_ascii=False)[:30000] + "\n"

    if chapter_num in [1, 2, 4] and "industry_data" in raw_data:
        d = raw_data["industry_data"]
        search_results = d.get("search_results", [])
        for result in search_results:
            data_context += f"\n### 搜索「{result.get('query', '')}」结果\n"
            data_context += result.get("raw_evidence", "")[:3000] + "\n"
        for group in d.get("focus_results", []):
            data_context += f"\n### 专题「{group.get('label', '')}」\n"
            for result in group.get("results", []):
                data_context += result.get("raw_evidence", "")[:2000] + "\n"

    if chapter_num in [3, 4] and "competitor_data" in raw_data:
        d = raw_data["competitor_data"]
        for comp, comp_data in d.get("competitors", {}).items():
            queries = comp_data.get("queries", [])
            news = comp_data.get("news", [])[:5]
            if queries or news:
                data_context += f"\n### {comp} 相关资讯\n"
                for result in queries:
                    data_context += result.get("raw_evidence", "")[:2500] + "\n"
                for n in news:
                    data_context += f"- {n.get('title','')}\n"

    if chapter_num in [2, 4] and "social_data" in raw_data:
        d = raw_data["social_data"]
        for platform, query_results in d.get("platforms", {}).items():
            data_context += f"\n### {platform} 用户内容\n"
            for result in query_results:
                data_context += f"查询：{result.get('query', '')}\n"
                data_context += json.dumps(result.get("items", []), ensure_ascii=False)[:4000] + "\n"

    if chapter_num in [4, 5]:
        prior_limit = 3 if chapter_num == 4 else 4
        data_context += f"\n### 前{prior_limit}章分析结果\n"
        for ch_num, content in analyzed_chapters.items():
            if ch_num <= prior_limit:
                data_context += f"\n#### 第{ch_num}章摘要（前1000字）\n{content[:1000]}...\n"

    user_message = f"""{data_context}

---

## 分析任务

{prompt_instructions}

请严格按照上述格式输出分析内容。数据不足的地方诚实说明，不要捏造数字。"""

    return system, user_message


def analyze_chapter(chapter_num: int, config: dict, raw_data: dict, analyzed_chapters: dict, model: str) -> bool:
    """分析单个章节"""
    chapter_names = {
        1: "市场吸引力与进入时点",
        2: "客户问题与商业价值池",
        3: "竞争系统与关键控制点",
        4: "Right to Win 与战略选项",
        5: "推荐下注与执行路线"
    }

    print(f"\n{'='*50}")
    print(f"📊 分析第 {chapter_num} 章：{chapter_names.get(chapter_num, '')}")
    print(f"{'='*50}")

    system_prompt, user_message = build_chapter_prompt(chapter_num, config, raw_data, analyzed_chapters)

    result = call_claude(system_prompt, user_message, model)

    if result:
        output_file = OUTPUT_ANALYZED / f"ch0{chapter_num}_analysis.md"
        header = f"# 第{chapter_num}章分析：{chapter_names.get(chapter_num, '')}\n\n> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n---\n\n"
        output_file.write_text(header + result)
        print(f"✅ 已保存至 {output_file}")
        return True
    return False


def analyze_executive_summary(config: dict, analyzed_chapters: dict, model: str) -> bool:
    """基于已完成的五章生成管理层摘要。"""
    if len(analyzed_chapters) < 5:
        print("⚠️  五章尚未完成，跳过管理层摘要")
        return False
    system = "你是互联网公司战略负责人。请把完整报告压缩成管理层可以直接决策的一页摘要。不得引入正文中没有的新事实。"
    chapters = "\n\n".join(f"## 第{number}章\n{content}" for number, content in sorted(analyzed_chapters.items()))
    user_message = f"{load_executive_prompt()}\n\n---\n\n{chapters}"
    result = call_claude(system, user_message, model)
    if not result:
        return False
    output_file = OUTPUT_ANALYZED / "executive_summary.md"
    output_file.write_text(result)
    print(f"✅ 管理层摘要已保存至 {output_file}")
    return True


def generate_final_report(config: dict, analyzed_chapters: dict):
    """合并所有章节生成最终报告"""
    template_file = TEMPLATES_DIR / "report_structure.md"
    if not template_file.exists():
        print("⚠️  模板文件不存在，跳过报告合并")
        return

    template = template_file.read_text()

    # 替换模板变量
    replacements = {
        "[COMPANY]": config["target"]["company"],
        "[INDUSTRY]": config["target"]["industry"],
        "[YEAR]": config["target"]["year"],
        "[RESEARCH_MODE]": str(config["research_mode"]).title(),
        "[TIMESTAMP]": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "[COLLECT_DATE]": datetime.now().strftime("%Y-%m-%d"),
    }

    chapter_content_keys = {
        1: "[CH01_CONTENT]",
        2: "[CH02_CONTENT]",
        3: "[CH03_CONTENT]",
        4: "[CH04_CONTENT]",
        5: "[CH05_CONTENT]",
    }

    report = template
    for key, val in replacements.items():
        report = report.replace(key, val)

    executive_file = OUTPUT_ANALYZED / "executive_summary.md"
    executive_content = executive_file.read_text() if executive_file.exists() else "*管理层摘要尚未生成。*"
    report = report.replace("[EXECUTIVE_SUMMARY]", executive_content)

    appendix_file = OUTPUT_ANALYZED / "appendix.md"
    appendix_content = appendix_file.read_text() if appendix_file.exists() else "未启用。仅在用户明确要求产品概念、原型或其他专题附录时生成。"
    report = report.replace("[APPENDIX_CONTENT]", appendix_content)

    for ch_num, placeholder in chapter_content_keys.items():
        content = analyzed_chapters.get(ch_num, f"*第{ch_num}章尚未生成，请运行 --chapter {ch_num}*")
        # 去掉章节文件的 header 部分
        if "---\n\n" in content:
            content = content.split("---\n\n", 1)[1]
        report = report.replace(placeholder, content)

    output_file = AGENT_DIR / "output" / f"report_{datetime.now().strftime('%Y%m%d_%H%M')}.md"
    output_file.write_text(report)
    print(f"\n🎉 最终报告已生成：{output_file}")
    return output_file


def main():
    parser = argparse.ArgumentParser(description="行业研究报告分析脚本")
    parser.add_argument("--chapter", type=int, choices=[1,2,3,4,5], help="分析指定章节")
    parser.add_argument("--all", action="store_true", help="分析所有章节并生成报告")
    parser.add_argument("--report", action="store_true", help="仅合并已有章节生成最终报告")
    args = parser.parse_args()

    config = load_config()
    model = config.get("claude_model", "claude-opus-4-8")

    if config["research_mode"] == "flash" and (args.all or args.report):
        print("❌ Flash 模式交付 1–2 页 decision brief，不使用五章报告合并路径。请由正常 Agent 流程生成 decision_brief_*.md。")
        sys.exit(2)

    print(f"🎯 目标：{config['target']['company']} × {config['target']['industry']} {config['target']['year']}")
    print(f"🤖 使用模型：{model}")

    raw_data = load_raw_data()
    if raw_data:
        print(f"📂 已加载原始数据：{', '.join(raw_data.keys())}")
    else:
        print("⚠️  output/raw/ 目录下没有数据文件，请先运行数据采集脚本")
        if not args.report:
            sys.exit(1)

    if not args.report:
        quality_issues = validate_raw_data(raw_data)
        if quality_issues:
            print("❌ 采集数据质量不足，已停止分析：")
            for issue in quality_issues:
                print(f"  - {issue}")
            print("💡 请先补跑采集，或修正 selector / 登录状态后再分析")
            sys.exit(1)

    analyzed_chapters = load_analyzed_chapters()

    if args.report:
        generate_final_report(config, analyzed_chapters)
        return

    chapters_to_run = [1, 2, 3, 4, 5] if args.all else [args.chapter] if args.chapter else []

    if not chapters_to_run:
        parser.print_help()
        return

    for ch in chapters_to_run:
        success = analyze_chapter(ch, config, raw_data, analyzed_chapters, model)
        if success:
            analyzed_chapters = load_analyzed_chapters()  # 刷新，供后续章节使用

    if args.all:
        analyze_executive_summary(config, analyzed_chapters, model)
        generate_final_report(config, analyzed_chapters)


if __name__ == "__main__":
    main()
