#!/bin/bash
# ============================================================
# 行业研究 Agent 工作流 - 主运行脚本
# 用法:
#   ./run.sh collect   # 采集、原文深读、证据质量验收
#   ./run.sh legacy-collect # 运行旧版 ego-browser 采集器
#   ./run.sh analyze   # 运行 Claude 分析（Standard/Deep：摘要+5章）
#   ./run.sh report    # 合并已有章节生成最终报告
#   ./run.sh all       # 全流程一键运行
#   ./run.sh status    # 查看当前进度
#   ./run.sh plan      # 校验假设、趋势和动态研究模块计划
#   ./run.sh estimate  # 开工前估算本课题完成时间
#   ./run.sh knowledge # 解析并检索共享本地私有资料库
#   ./run.sh results-qa # 校验结构化趋势、关键结论与模块结果
#   ./run.sh qa <md>   # 运行结论与最终交付双重闸门
# ============================================================

set -e
export AGENT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_FILE="$AGENT_DIR/config.json"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${BLUE}[行业Agent]${NC} $1"; }
ok()  { echo -e "${GREEN}✅${NC} $1"; }
warn(){ echo -e "${YELLOW}⚠️ ${NC} $1"; }
err() { echo -e "${RED}❌${NC} $1"; }

# 读取配置
COMPANY=$(python3 -c "import json; c=json.load(open('$CONFIG_FILE')); print(c['target']['company'])")
INDUSTRY=$(python3 -c "import json; c=json.load(open('$CONFIG_FILE')); print(c['target']['industry'])")
YEAR=$(python3 -c "import json; c=json.load(open('$CONFIG_FILE')); print(c['target']['year'])")

print_header() {
  echo ""
  echo "═══════════════════════════════════════════════"
  echo "  🔬 行业研究 Agent"
  echo "  目标: ${COMPANY} × ${INDUSTRY} ${YEAR}"
  echo "═══════════════════════════════════════════════"
  echo ""
}

validate_plan() {
  AGENT_DIR="$AGENT_DIR" python3 "$AGENT_DIR/scripts/validate_research_plan.py"
}

run_knowledge() {
  enabled=$(python3 -c "import json; print(str(json.load(open('$CONFIG_FILE')).get('knowledge', {}).get('enabled', True)).lower())")
  if [ "$enabled" != "true" ]; then
    warn "私有资料检索已在 config.json 中关闭"
    return 0
  fi
  log "解析共享本地资料库并为当前课题生成 PRI 证据账本..."
  set +e
  AGENT_DIR="$AGENT_DIR" python3 "$AGENT_DIR/scripts/process_knowledge.py"
  knowledge_status=$?
  set -e
  if [ "$knowledge_status" -eq 0 ]; then
    ok "私有资料账本已生成"
  elif [ "$knowledge_status" -eq 2 ]; then
    warn "部分私有资料无法解析；详见 output/knowledge/knowledge_report.json"
  else
    err "私有资料处理失败"
    return "$knowledge_status"
  fi
  return 0
}

# ── 检查依赖 ──────────────────────────────────────────
check_deps() {
  log "检查依赖..."

  if ! command -v agent-reach &>/dev/null; then
    err "agent-reach 未安装"
    exit 1
  fi

  if ! command -v mcporter &>/dev/null; then
    err "mcporter 未安装，无法调用 Exa"
    exit 1
  fi

  platform_count=$(python3 -c "import json; print(len(json.load(open('$CONFIG_FILE')).get('platform_queries', [])))")
  if [ "$platform_count" -gt 0 ] && ! command -v opencli &>/dev/null; then
    err "opencli 未安装，无法采集 config 中选择的社区平台"
    exit 1
  fi

  if ! command -v python3 &>/dev/null; then
    err "python3 未找到"
    exit 1
  fi

  ok "依赖检查完成"
}

# ── Step 1: 数据采集 ───────────────────────────────────
run_collect() {
  mkdir -p "$AGENT_DIR/output"
  collect_lock="$AGENT_DIR/output/.collect.lock"
  if ! mkdir "$collect_lock" 2>/dev/null; then
    lock_pid="$(cat "$collect_lock/pid" 2>/dev/null || true)"
    if [ -n "$lock_pid" ] && kill -0 "$lock_pid" 2>/dev/null; then
      err "采集已在运行（PID $lock_pid）；请等待现有进程完成，不要重复启动"
      return 75
    fi
    warn "发现无活动进程的旧采集锁，正在清理后继续"
    rm -rf "$collect_lock"
    mkdir "$collect_lock"
  fi
  echo "$$" > "$collect_lock/pid"
  cleanup_collect_lock() {
    rm -rf "$collect_lock"
  }
  trap cleanup_collect_lock EXIT INT TERM

  validate_plan
  check_deps
  run_knowledge
  log "开始按 config 动态路由数据源..."
  echo ""

  mkdir -p "$AGENT_DIR/output/raw"

  log "行业/竞品优先使用 Exa；故障时依次切换 OpenCLI Google、Bing HTML，最后降级 DuckDuckGo HTML"
  set +e
  INDUSTRY_REPORT_PIPELINE_ACTIVE=1 AGENT_DIR="$AGENT_DIR" python3 "$AGENT_DIR/scripts/collect_reach.py"
  collect_status=$?
  set -e
  if [ "$collect_status" -eq 0 ]; then
    ok "Agent Reach 发现阶段完成"
  elif [ "$collect_status" -eq 2 ]; then
    warn "采集部分成功；请检查 output/raw/collection_errors.json"
  else
    err "采集失败"
    exit "$collect_status"
  fi

  log "标准化、去重并深读原始来源..."
  INDUSTRY_REPORT_PIPELINE_ACTIVE=1 AGENT_DIR="$AGENT_DIR" python3 "$AGENT_DIR/scripts/enrich_evidence.py"
  ok "证据账本已生成"

  log "执行证据质量闸门..."
  set +e
  INDUSTRY_REPORT_PIPELINE_ACTIVE=1 AGENT_DIR="$AGENT_DIR" python3 "$AGENT_DIR/scripts/validate_evidence.py"
  quality_status=$?
  set -e
  if [ "$quality_status" -eq 0 ]; then
    ok "证据质量闸门通过"
  else
    warn "证据质量闸门未通过；不得进入正式成稿"
  fi

  echo ""
  log "采集完成，数据保存至 output/raw/"
  ls -la "$AGENT_DIR/output/raw/"
  echo ""
  log "采集后数据状态检查..."
  show_status
  cleanup_collect_lock
  trap - EXIT INT TERM
  return "$quality_status"
}

validate_results() {
  AGENT_DIR="$AGENT_DIR" python3 "$AGENT_DIR/scripts/validate_research_results.py"
}

run_results_qa() {
  validate_plan
  validate_results
}

run_handoff_qa() {
  report_path="${1:-}"
  if [ -z "$report_path" ]; then
    err "用法: ./run.sh qa /绝对路径/报告.md"
    exit 1
  fi
  run_results_qa
  AGENT_DIR="$AGENT_DIR" python3 "$AGENT_DIR/scripts/validate_deliverable.py" --report "$report_path"
}

run_legacy_collect() {
  validate_plan
  if ! command -v ego-browser &>/dev/null; then
    err "legacy-collect 需要 ego-browser"
    exit 1
  fi
  warn "正在运行旧版固定网页采集器；它只应作为故障排查用 fallback"
  AGENT_DIR="$AGENT_DIR" ego-browser nodejs < "$AGENT_DIR/scripts/collect_industry.js"
  AGENT_DIR="$AGENT_DIR" ego-browser nodejs < "$AGENT_DIR/scripts/scan_competitors.js"
  AGENT_DIR="$AGENT_DIR" ego-browser nodejs < "$AGENT_DIR/scripts/collect_social.js"
}

# ── Step 2: Claude 分析 ────────────────────────────────
run_analyze() {
  validate_plan
  log "开始 Claude 分析（管理层摘要 + 5 章）..."

  if ! python3 -c "import anthropic" &>/dev/null 2>&1; then
    err "独立 analyze 路径需要 anthropic 包；正常 Agent 流程不需要"
    exit 1
  fi

  if [ -z "$ANTHROPIC_API_KEY" ]; then
    err "需要设置 ANTHROPIC_API_KEY"
    echo "  export ANTHROPIC_API_KEY=your_api_key_here"
    exit 1
  fi

  AGENT_DIR="$AGENT_DIR" python3 "$AGENT_DIR/analyze/analyze.py" --all
  ok "管理层摘要与 5 章分析全部完成"
}

# ── Step 3: 生成报告 ───────────────────────────────────
run_report() {
  validate_plan
  if [ ! -f "$AGENT_DIR/output/raw/quality_report.json" ] || \
     [ "$(python3 -c "import json; print(json.load(open('$AGENT_DIR/output/raw/quality_report.json'))['status'])")" != "pass" ]; then
    err "证据质量闸门未通过，拒绝生成正式报告"
    exit 3
  fi
  if [ ! -f "$AGENT_DIR/output/analyzed/executive_summary.md" ]; then
    err "缺少管理层摘要 output/analyzed/executive_summary.md，拒绝生成正式报告"
    exit 3
  fi
  if [ ! -f "$AGENT_DIR/output/analyzed/research_design_results.json" ]; then
    err "缺少研究设计结果 output/analyzed/research_design_results.json，拒绝生成正式报告"
    exit 3
  fi
  validate_results
  log "合并章节，生成最终报告..."
  AGENT_DIR="$AGENT_DIR" python3 "$AGENT_DIR/analyze/analyze.py" --report

  REPORT_FILE=$(ls -t "$AGENT_DIR/output/report_"*.md 2>/dev/null | head -1)
  if [ -n "$REPORT_FILE" ]; then
    ok "报告已生成: $REPORT_FILE"
    echo ""
    echo "  字数统计: $(wc -w < "$REPORT_FILE") 词"
    echo "  章节数量: $(grep -c '^## ' "$REPORT_FILE") 章"
  fi
}

# ── 状态查看 ──────────────────────────────────────────
show_status() {
  echo ""
  log "当前进度："
  echo ""

  # 原始数据
  echo "📂 原始数据 (output/raw/):"
  for f in industry_data competitor_data social_data evidence_ledger quality_report; do
    file="$AGENT_DIR/output/raw/${f}.json"
    if [ -f "$file" ]; then
      size=$(wc -c < "$file")
      mtime=$(stat -f "%Sm" -t "%Y-%m-%d %H:%M" "$file" 2>/dev/null || date -r "$file" "+%Y-%m-%d %H:%M" 2>/dev/null || echo "unknown")
      ok "  ${f}.json (${size} bytes, ${mtime})"
    else
      warn "  ${f}.json 未采集"
    fi
  done

  if [ -f "$AGENT_DIR/output/raw/quality_report.json" ]; then
    quality=$(python3 -c "import json; print(json.load(open('$AGENT_DIR/output/raw/quality_report.json'))['status'].upper())")
    if [ "$quality" = "PASS" ]; then
      ok "  证据质量闸门: PASS"
    else
      warn "  证据质量闸门: $quality"
    fi
  fi

  if [ -f "$AGENT_DIR/output/knowledge/knowledge_report.json" ]; then
    knowledge_summary=$(python3 -c "import json; r=json.load(open('$AGENT_DIR/output/knowledge/knowledge_report.json')); print(f\"{r['documents_parsed']} docs / {r['private_evidence_items']} PRI items / {r['status'].upper()}\")")
    ok "  私有资料: $knowledge_summary"
  else
    warn "  私有资料 未处理（共享资料库可为空）"
  fi

  if [ -f "$AGENT_DIR/output/research_plan_report.json" ]; then
    plan_quality=$(python3 -c "import json; print(json.load(open('$AGENT_DIR/output/research_plan_report.json'))['status'].upper())")
    if [ "$plan_quality" = "PASS" ]; then
      ok "  研究计划闸门: PASS"
    else
      warn "  研究计划闸门: $plan_quality"
    fi
  else
    warn "  研究计划闸门 未运行"
  fi

  if [ -f "$AGENT_DIR/output/research_results_quality_report.json" ]; then
    result_quality=$(python3 -c "import json; print(json.load(open('$AGENT_DIR/output/research_results_quality_report.json'))['status'].upper())")
    if [ "$result_quality" = "PASS" ]; then
      ok "  研究结论闸门: PASS"
    else
      warn "  研究结论闸门: $result_quality"
    fi
  else
    warn "  研究结论闸门 未运行"
  fi

  echo ""

  # 分析结果
  echo "📊 章节分析 (output/analyzed/):"
  if [ -f "$AGENT_DIR/output/analyzed/executive_summary.md" ]; then
    ok "  管理层摘要"
  else
    warn "  管理层摘要 未生成"
  fi
  for i in 1 2 3 4 5; do
    file="$AGENT_DIR/output/analyzed/ch0${i}_analysis.md"
    if [ -f "$file" ]; then
      words=$(wc -w < "$file")
      ok "  第${i}章 (${words} 词)"
    else
      warn "  第${i}章 未分析"
    fi
  done

  echo ""

  # 最终报告
  REPORT_FILE=$(ls -t "$AGENT_DIR/output/report_"*.md 2>/dev/null | head -1)
  echo "📄 最终报告:"
  if [ -n "$REPORT_FILE" ]; then
    ok "  $(basename $REPORT_FILE)"
  else
    warn "  未生成"
  fi

  echo ""
}

# ── 主入口 ────────────────────────────────────────────
print_header

case "${1:-help}" in
  plan)
    validate_plan
    ;;
  estimate)
    validate_plan
    AGENT_DIR="$AGENT_DIR" python3 "$AGENT_DIR/scripts/estimate_duration.py"
    ;;
  knowledge)
    validate_plan
    run_knowledge
    ;;
  collect)
    run_collect
    ;;
  legacy-collect)
    run_legacy_collect
    ;;
  analyze)
    run_analyze
    ;;
  report)
    run_report
    ;;
  all)
    run_collect
    echo ""
    run_analyze
    echo ""
    run_report
    echo ""
    ok "🎉 全流程完成！"
    show_status
    ;;
  status)
    show_status
    ;;
  results-qa)
    run_results_qa
    ;;
  qa)
    run_handoff_qa "${2:-}"
    ;;
  help|*)
    echo "用法:"
    echo "  ./run.sh collect   # Agent Reach 配置驱动采集"
    echo "  ./run.sh legacy-collect # 旧版 ego-browser fallback"
    echo "  ./run.sh analyze   # Standard/Deep 摘要+5章（需要 ANTHROPIC_API_KEY）"
    echo "  ./run.sh report    # 合并生成最终报告"
    echo "  ./run.sh all       # 全流程一键运行"
    echo "  ./run.sh status    # 查看当前进度"
    echo "  ./run.sh plan      # 校验假设、趋势与动态研究模块"
    echo "  ./run.sh estimate  # 根据当前课题配置预测完成时间"
    echo "  ./run.sh knowledge # 从共享本地资料库生成当前课题的 PRI 证据账本"
    echo "  ./run.sh results-qa # 校验趋势、关键结论与模块结果"
    echo "  ./run.sh qa <report.md> # 运行结论与最终交付双重闸门"
    echo ""
    echo "配置文件: config.json"
    echo "  - 修改 target.company 换目标公司"
    echo "  - 修改 target.industry 换行业"
    echo "  - 修改 competitors 换竞品列表"
    ;;
esac
