# Industry Report Agent

面向管理层战略决策的证据治理型行业研究 Agent。它将模糊课题拆解为研究问题，执行公开资料检索与私有资料检索，建立证据账本和关键 Claim 状态，并输出市场测算、商业模式、竞争控制点、首发下注卡和 90 天验证计划。

## 同事最快使用方式

### 1. 安装插件

```bash
codex plugin marketplace add l0810lin-ship-it/industry-report-agent --ref main
codex plugin add industry-report-agent@industry-report-agent-marketplace
```

安装后新开一个 Codex 任务，使插件生效。

### 2. 准备自己的资料文件夹

第一次运行私有资料处理时，插件会自动创建：

```text
~/Documents/Industry Report Knowledge
```

把允许用于研究的资料拖入即可：

```text
Industry Report Knowledge/
├── 历史行业报告.pdf
├── 用户访谈.docx
├── 问卷结果.xlsx
└── 竞品分析.md
```

支持 `.pdf`、`.docx`、`.xlsx`、`.csv`、`.md` 和 `.txt`。资料只需放一次；不同课题会按各自研究问题检索相关片段。

### 3. 调用 Agent

在 Codex 中选择 **Industry Report Agent**，或直接说：

> 使用 Industry Report Agent 分析百度是否应进入本地生活 AI。Deep 模式，Markdown 格式。

Agent会先处理个人知识文件夹，再完成公开来源研究。私有资料生成 `PRI-*` 证据，公开资料生成 `EV-*` 证据，两者不会混淆。

## 使用其他资料目录

无需修改插件。设置一次环境变量：

```bash
export INDUSTRY_REPORT_KNOWLEDGE_DIR="$HOME/my-research-docs"
```

多个目录可使用系统路径分隔符连接。也可以在单次运行的 `config.json` 中填写：

```json
{
  "knowledge": {
    "paths": ["~/team-research", "~/project-docs"]
  }
}
```

优先级为：环境变量 → `knowledge.paths` → 旧版 `knowledge.directory` → 默认 Documents 文件夹。

## 工作流

```text
课题输入
→ Flash / Standard / Deep 与格式选择
→ 研究问题和检索计划
→ 本地私有资料解析与 BM25 检索
→ 公开网络证据采集和原文深读
→ PRI / EV 双证据账本
→ Claim 交叉验证与反证
→ Top-down / Bottom-up 市场测算
→ 自适应商业模型和单位经济
→ 首发赛道、产品形态与 90 天决策门
→ Markdown / Word / PowerPoint
```

## 私有资料边界

- 原始文件、解析结果和索引保留在使用者本机，不进入本仓库。
- 本插件不包含遥测，不统计研究课题、文件名、调用次数或报告内容。
- 检索命中的必要片段会进入当前使用模型的上下文；敏感资料是否接入由使用者自行判断。
- 私有材料默认只作为 `user_provided_private` 证据，不能单独满足公开来源质量闸门。
- 问卷、访谈和内部报告必须保留样本、方法、时间与外推限制。

## 运行产物

每个研究课题创建独立运行目录，核心产物包括：

```text
output/
├── research_plan_report.json
├── knowledge/
│   ├── parsed_documents.json
│   ├── private_evidence_ledger.json
│   └── knowledge_report.json
├── raw/
│   ├── evidence_ledger.json
│   └── quality_report.json
├── research_results_quality_report.json
└── deliverable_quality_report.json
```

## 本地开发与验证

```bash
python3 -m unittest discover \
  -s plugins/industry-report-agent/tests -v

python3 /path/to/plugin-creator/scripts/validate_plugin.py \
  plugins/industry-report-agent
```

## 依赖说明

- 正常 Codex Agent 流程不需要 Anthropic API Key。
- 公开网络采集使用 Agent Reach 及其可用后端；缺少某一搜索后端时按现有回退链处理。
- PDF 本地解析优先使用 `pdftotext`，其次尝试 PyMuPDF、pypdf 或 macOS文本提取；无法解析的文件会明确记录为失败，不会伪装成已读取。

## 当前定位

这是个人与小团队可用的本地资料版本，不需要 MCP、向量数据库、云知识库或服务器。企业网盘、权限继承和审计系统属于后续可选扩展，不是安装前置条件。
