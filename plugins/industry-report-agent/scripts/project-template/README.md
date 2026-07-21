# 通用 AI 战略研究 Agent 工作流

这是 `industry_report` 自定义 Agent 的单次运行模板。每个题目都先配置范围和研究模式，再决定来源；模板不预设公司、行业、竞品或社区平台。

每次运行必须先完成两层治理：

- `classification`：决策类型、问题类型、地理范围、交付意图和必需质量门。
- `memory_policy`：允许复用的记忆类别、被阻断的旧结论记忆、来源缓存重验规则。

这些字段会被 `plan` 闸门检查。它们防止 Agent 把模糊问题当成普通资料汇总，也防止把旧报告结论当成新证据。

## 三种研究模式

Flash、Standard、Deep 的基础时间、范围、交付物和格式制作耗时只在 `mode_profiles.json` 中定义。开工前必须让用户选择模式和格式，不设置静默默认值。

平台数量是上限而不是配额。只选择能回答当前研究问题的平台。

## 决策结构

Standard/Deep 报告回答五个管理问题：

1. 市场是否值得进入，Top-down 与 Bottom-up 的规模测算是否互相支持，为什么是现在？
2. 谁为什么问题付费，收入引擎、最小经济单元和贡献利润是否成立？
3. 谁控制数据、分发、技术、交付与客户关系？
4. 目标公司凭什么赢，应 Build、Buy 还是 Partner？
5. 管理层应批准哪一个下注，如何 Continue、Pivot 或 Kill？

产品玩法与原型不是固定章节，只在用户明确要求时进入附录。

## 配置

在 `config.json` 中设置：

- `research_mode`：`flash`、`standard` 或 `deep`
- `target`：公司/主题、行业、年份和地区
- `classification`：先判断 `decision_type`、`deliverable_intent` 和 `primary_question_types`，再决定研究模块与质量门
- `research_questions`：稳定 ID、`critical` 标记和 `question_types`
- `user_hypotheses`：只记录用户主动提供、会改变决策且需要验证的线索；可以为空
- `research_design.active_modules`：按问题启用趋势推断、集中度、区域顺序、真实案例、基准区间或压力测试
- `research_design.candidate_trends`：可为空；填写时只能记录 `status: unverified` 的候选模式，不能预设结论；Agent 也必须从多主体时间线中主动发现并核验候选趋势
- `research_design.case_studies`：启用真实案例模块时设置数量和选择标准
- `research_keywords`、`focus_queries`、`competitor_keywords`
- `competitors`：只保留能改变决策的对象
- `platform_queries`：可以为空
- `source_rules`：官网、监管、研究和媒体域名
- `collection.max_deep_reads`：与模式上限一致
- `collection.search_results_per_query`：每条查询的首轮批次，不是最终候选数
- `collection.adaptive_discovery`：按新增 URL 饱和度扩展；模式中的单查询上限只是防止无限抓取的安全边界
- `quality_gates`：默认按模式自动选择；这里只写必要的更严格覆盖值
- `economics.business_models`：已知时填写主/次收入引擎；留空则由 Agent 根据证据分类
- `economics.primary_unit`：已知时填写用户、订单、席位、项目、标题、API 调用等最小经济单元
- `economics.market_sizing`：Standard/Deep 固定要求 `top_down` + `bottom_up`
- `output.formats`：从 `md`、`docx`、`pptx` 中选择一个或多个；不得静默默认
- `knowledge`：可选的共享本地私有资料检索。优先读取 `INDUSTRY_REPORT_KNOWLEDGE_DIR`，其次读取 `knowledge.paths`，否则首次运行自动创建 `~/Documents/Industry Report Knowledge`。资料只需放一次；每次运行按当前研究问题检索相关片段。私有证据使用 `PRI-*`，不并入公开证据账本，也不能替代公开来源质量闸门
- `memory_policy`：默认要求 fresh run，允许复用工具经验、用户偏好、来源缓存线索、当前 run 上下文和评测经验；禁止自动复用旧结论、旧市场规模、旧排名和旧推荐

所有查询都用 `question_ids` 映射到研究问题；动态模块使用 `module_ids`，候选趋势使用 `trend_ids`，用户线索测试使用 `hypothesis_ids` 和 `stance`。跨境课题自动启用 `trend_inference` + `geographic_sequencing`，但不得预置任何地区顺序；路线只能作为 `unverified` 候选，经主体时间线、反例和 `n/N` 样本核验后再分类。

## 运行

```bash
./run.sh plan
./run.sh estimate
./run.sh knowledge
./run.sh collect
./run.sh status
./run.sh results-qa
./run.sh qa /绝对路径/报告.md
```

`estimate` 生成 `output/estimate.json`，包含模式、预计完成区间、完成窗口、置信度、阶段拆分、范围是否超限和推荐模式。它是开工前预测，不是实际工时。

`knowledge` 递归解析配置的共享资料库内 `.txt/.md/.csv/.docx/.xlsx/.pdf`，按当前课题研究问题执行本地 BM25 检索，并只把本次命中的片段写入当前运行的 `output/knowledge/private_evidence_ledger.json`。没有文件时正常生成空账本；不需要数据库、Embedding API 或云端知识库。公开报告引用私有资料前必须遵守资料库根目录 `manifest.json` 的引用与公开权限。

默认采集链为 `collect_reach.py → enrich_evidence.py → validate_evidence.py`，产出来源健康、发现结果、证据账本、错误记录和质量报告。只有 `quality_report.status == pass` 才能正式成稿。

候选证据没有固定数量目标。每条查询从首轮批次开始，在仍产生足够新增 URL 时继续扩展；随后按课题、查询和实体相关性过滤，保留所有相关候选并记录低相关淘汰原因。研究问题仍有缺口时新增针对性查询，搜索结果趋同后停止。

`plan` 会在采集前检查动态模块、趋势反向查询和用户线索验证平衡。成稿前填写 `output/analyzed/research_design_results.json`，再运行 `results-qa` 与 `qa`。只有研究结论闸门和交付闸门都为 pass 才能交付；它们会检查趋势样本/反例、Claim 级交叉验证、真实案例、双路径市场测算、自适应商业模型和所选格式文件。Word/PPT 仍需各自 Skill 完成逐页/逐张视觉与可编辑性验收。

Flash 由正常 Codex Agent 流程填写 `templates/decision_brief.md`。Standard/Deep 生成管理层摘要和五章。Markdown 是分析源；选择 Word 时调用 `documents:documents`，选择 PowerPoint 时调用 `knowledge-cat-ppt-skill` + `presentations:Presentations`，并完成逐页/逐张渲染验收。正常插件流程不需要 Anthropic API Key；`run.sh analyze` / `all` 是保留的独立终端路径，`legacy-collect` 仅用于 fallback。
