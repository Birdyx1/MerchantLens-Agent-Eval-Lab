# Agent 与评测体系总计划

更新时间：2026-11-02（Asia/Shanghai）

今日安排：[2026-11-01 四小时学习计划](lessons/stage01/2026-11-01-plan.md)。

## 当前进度

- 当前进度：阶段 1、阶段 2 与阶段 3 在项目范围内已完成并复盘；阶段 4 的 4.1～4.3 已通过，4.4～4.6 的流程代码通过，真实双人标注、实际仲裁和 Holdout 预留样本待补；正式四集合及 Holdout 仍为空。阶段 5 的 5.1～5.5 基础代码、5.6 本地真实 MCP/LangGraph 接线及双批次报告生成器通过；正式 DeepSeek 双版本报告仍待真实标注样本、入库和运行。阶段 3 的 DeepSeek 真实模型与 MCP SQL 端到端烟雾测试已通过。
- 已验收课时：62（4.4～4.6 仅流程代码通过，真实样本及端到端接线未完成，暂不计入；各课的独立完成情况以对应课时文档为准）。
- 自 2.6b 起，按学员新要求由教师实现代码并验证，学员重点理解架构设计；每课仍保留文档、验收记录与独立完成情况。
- 阶段 3 曾短暂改为学员手写参考代码；3.1 后学员再次要求由教师实现，自己理解架构。后续按最新要求执行，保留 3.1 的学员初稿和教师收尾记录。
- 教师新增代码的注释和文档字符串使用中文；接口名与协议字段保留原有英文。
- 测试统一使用 pytest；`pyproject.toml` 的 dev 依赖与 `uv.lock` 已同步，完整测试命令为 `.venv/bin/python -m pytest -q`。

## 教学与维护规则

- 每课聚焦一个知识点、一个小产物；任务过大时继续拆课并同步目录。
- 当前顺序：方法论与架构边界 → 教师实现 → 测试及真实 Trace 证据 → 逐段代码讲解与面试归因 → 学员理解与提问 → 下一课。早期学员编写的课时保留原评审记录。
- 阶段 4～10 的每一课先说明：评测对象和失败风险、样本来源与隔离、真值或 Rubric、裁判选择、指标与门禁、偏差和污染风险、Trace 证据及验收方式；再实现代码。明确标注哪些属于四家实践来源，哪些属于本项目工程取舍。
- 代码讲解要沿一条具体样本或 Trace 说明数据如何进入流水线、在哪一步评分、失败如何归因；解释接口边界和不确定性，不只介绍函数做了什么。
- 通过后才进入下一课；阶段结束先复盘。
- 按学员最新要求，教师可提供并提交完整实现；明确标记教师代写，不将其计入学员独立完成。
- 每次授课、评审、修改和验收后，同步更新总计划、阶段文档、课时文档。
- 状态：未开始、进行中、待评审、修改中、已通过。未经评审不得标为已通过。
- 未来课时只建立标题与占位，正式开课时再填写短讲义、任务、验收和面试考点。
- 每课明确区分：公开标准、框架约定、项目自定义设计；技术约定附原始来源，不把自定义字段称为行业统一标准。
- Trace 正式设计以 OpenTelemetry Trace/Span 语义为基础；JSON 存储格式与评测扩展明确标记为项目约定。第一课改为两条模拟 Span 的层级练习，替换旧六字段 JSONL 作业；本地 JSON 不是 OTLP JSON 或完整生产协议。

## 实习岗位对齐补充

- 阶段 5 新增 5.6：完成首版小规模评测报告，形成“任务集 → 批量执行 → 轨迹 → 规则评分 → 失败分类 → 报告”的完整成果，并提供同一任务集上两个版本或配置的初步对比。阶段 10 再完善为标准报告，不把第一份成果推迟到阶段 10。
- 阶段 6 新增 6.6：选择一个现成评测工具或公开 Benchmark，完成一次小规模运行与分析，理解任务格式、输入输出、评分逻辑和失败原因；开课时根据项目适配性与官方文档确定工具、版本及范围，不要求同时学习多个框架或跑完整榜单。
- 6.3 多裁判投票、6.4 Agent 裁判与工具核验、9.3 标注工作台安排在阶段 10 首版主线验收后继续完成；它们是项目整体交付要求，不能作为可省略的展示项。首版主线先完成规则评分、单个 LLM 裁判、人工抽检和版本比较。
- 阶段 6 首版顺序：6.1 → 6.2 → 6.5 → 6.6；阶段 9 首版顺序：9.1 → 9.2 → 9.4 → 9.5，先用文件或简单表格维护标注与复核记录。6.3、6.4、9.3 随后逐课实施并验收，全部完成后才标记项目整体完成。

## 项目约束

- Python、LangGraph、官方 MCP Python SDK；工具为 SQL、Python 和网页检索。
- 模型、Harness、工具、记忆解耦；Trace 使用结构化 JSON，记录显式计划、决策摘要及全部实际调用。
- Golden、Regression、Badcase、Negative 四集合物理隔离，回流不自动混入黄金集。
- 裁判体系包含 Code、LLM 与 Agent 三类，辅以人工独立标注、仲裁和定期抽样校准；先形成首版 Code 与单个 LLM 裁判，再完成多裁判和 Agent 裁判。
- 基座、组件、端到端三层评测；结果、轨迹、成本、安全四类指标。
- 测试流量标记保留在控制面，不暴露给被测模型；预留 Holdout、禁止评测样本进入 few-shot、轮换黄金集。
- Trace → 异常识别 → 标注与复核记录 → 回流入库；报告包含版本对比、根因、Judge 一致性与退化告警。完整标注工作台在后续课时完成。
- 发版前必跑回归，安全违规一票否决；关键证据缺失不能自动通过。
- 合成、故障注入和试用回流必须如实标记，简历只使用有实验证据的结论。

## 阶段与课时

### [阶段 1：Trace 与工程基础](lessons/stage01/README.md)

状态：基础课时与复盘已完成，后续能力待补齐。

- [1.1 理解 Trace 与 Span](lessons/stage01/lesson01.md)：已通过。
- [1.2 Span 的 JSON Schema](lessons/stage01/lesson02.md)：已通过（教师协助）。
- [1.3 Trace 追加写入](lessons/stage01/lesson03.md)：已通过（参考示例后手写）。
- [1.4 调用关联与重试](lessons/stage01/lesson04.md)：已通过（教师协助修改）。
- [1.5 跨事件语义校验](lessons/stage01/lesson05.md)：已通过（教师协助修改）。
- [1.6 证据与回放](lessons/stage01/lesson06.md)：已通过（轨迹读取）。
- [1.7 运行版本清单](lessons/stage01/lesson07.md)：已通过（教师协助修改）。

### [阶段 2：业务工具与 MCP](lessons/stage02/README.md)

状态：项目范围内完成；[阶段复盘](lessons/stage02/review.md) 已完成。

- [2.1 业务数据口径](lessons/stage02/lesson01.md)：已通过（教师协助修改）。
- [2.2a 准备 SQLite 数据](lessons/stage02/lesson02.md)：已通过（分步参考示例后手写）。
- [2.2b SQL 只读查询](lessons/stage02/lesson02b.md)：已通过。
- [2.3a Python 请求校验](lessons/stage02/lesson03.md)：已通过（教师协助修改）。
- [2.3b 构造容器启动参数](lessons/stage02/lesson03b.md)：已通过（教师协助导入配置）。
- [2.3c Python 执行结果契约](lessons/stage02/lesson03c.md)：已通过。
- [2.3d 验证容器运行环境](lessons/stage02/lesson03d.md)：已通过（学员提交终端输出）。
- [2.3e 执行前检查镜像](lessons/stage02/lesson03e.md)：已通过。
- [2.3f 限制输出内容](lessons/stage02/lesson03f.md)：已通过。
- [2.3g 容器清理](lessons/stage02/lesson03g.md)：已通过。
- [2.3h Python 执行器与隔离验证](lessons/stage02/lesson03h.md)：项目范围内完成（教师代写）；[2.3h3](lessons/stage02/lesson03h3.md) 复盘按学员要求跳过。
- [2.4 网页检索证据](lessons/stage02/lesson04.md)：已通过；[2.4a](lessons/stage02/lesson04a.md)～[2.4g](lessons/stage02/lesson04g.md) 均已验收。
- [2.5 官方 MCP SDK 接入](lessons/stage02/lesson05.md)：已通过；[2.5a](lessons/stage02/lesson05a.md)～[2.5h 三工具 stdio 配置](lessons/stage02/lesson05h.md) 均已验收，部分教师代写。
- [2.6 工具故障与埋点](lessons/stage02/lesson06.md)：已通过；[2.6a](lessons/stage02/lesson06a.md)～[2.6h](lessons/stage02/lesson06h.md) 已通过（教师实现）。真实 stdio 三工具实调用与阶段复盘已完成。

### [阶段 3：LangGraph ReAct Agent](lessons/stage03/README.md)

状态：已完成并[复盘](lessons/stage03/review.md)。

- [3.1 基座模型适配](lessons/stage03/lesson01.md)：已通过（学员初稿，教师收尾实现）。
- [3.2 短期状态定义](lessons/stage03/lesson02.md)：已通过（教师实现）。
- [3.3 规划与路由](lessons/stage03/lesson03.md)：已通过；[3.3a](lessons/stage03/lesson03a.md)、[3.3b](lessons/stage03/lesson03b.md) 已通过（教师实现）。
- [3.4 行动与观察循环](lessons/stage03/lesson04.md)：已通过；[3.4a](lessons/stage03/lesson04a.md)、[3.4b](lessons/stage03/lesson04b.md) 已通过（教师实现）。
- [3.5 反思与有界重试](lessons/stage03/lesson05.md)：已通过；[3.5a](lessons/stage03/lesson05a.md)～[3.5c](lessons/stage03/lesson05c.md) 已通过（教师实现）。
- [3.6 记忆与检查点](lessons/stage03/lesson06.md)：已通过；[3.6a](lessons/stage03/lesson06a.md)、[3.6b](lessons/stage03/lesson06b.md) 已通过（教师实现）。
- [3.7 终止与预算](lessons/stage03/lesson07.md)：已通过；[3.7a](lessons/stage03/lesson07a.md)、[3.7b](lessons/stage03/lesson07b.md) 已通过（教师实现）。
- [3.8 根 Trace 的终止记录](lessons/stage03/lesson08.md)：已通过（教师实现）。
- [3.9 模型规划 Span](lessons/stage03/lesson09.md)：已通过（教师实现）。
- [3.10 真实模型适配器](lessons/stage03/lesson10.md)：已通过（教师实现；DeepSeek 真实联网验收）。
- [3.11 Agent 端到端轨迹验收](lessons/stage03/lesson11.md)：已通过（教师实现）。

### [阶段 4：评测资产与标注](lessons/stage04/README.md)

状态：进行中。

- [4.1 Task 数据契约](lessons/stage04/lesson01.md)：已通过（教师实现）。
- [4.2 四集合物理隔离](lessons/stage04/lesson02.md)：已通过（教师实现）。
- [4.3 Rubric 编写](lessons/stage04/lesson03.md)：已通过（教师实现）。
- [4.4 双人独立标注](lessons/stage04/lesson04.md)：流程代码已通过（教师实现），真实人工双标待补。
- [4.5 标注一致性与仲裁](lessons/stage04/lesson05.md)：流程代码已通过（教师实现），真实人工结果待补。
- [4.6 Holdout 与污染防护](lessons/stage04/lesson06.md)：流程代码已通过（教师实现），真实预留样本与运行器接线待补。

### [阶段 5：Python 评测流水线](lessons/stage05/README.md)

状态：未开始

- [5.1 Trial 与环境重置](lessons/stage05/lesson01.md)：基础契约已通过（教师实现），真实运行器接线待补。
- [5.2 Code Evaluator](lessons/stage05/lesson02.md)：规则评分代码已通过（教师实现），真实 Trial 接线待补。
- [5.3 四类指标](lessons/stage05/lesson03.md)：指标代码已通过（教师实现），真实批量样本待补。
- [5.4 重复试验与不确定性](lessons/stage05/lesson04.md)：统计代码已通过（教师实现），真实重复运行待补。
- [5.5 批量执行](lessons/stage05/lesson05.md)：编排代码已通过（教师实现），真实批量运行待补。
- [5.6 首版小规模评测报告](lessons/stage05/lesson06.md)：报告代码和本地链路通过（教师实现）；正式双版本报告待真实样本。

### [阶段 6：裁判与校准](lessons/stage06/README.md)

状态：未开始

- [6.1 LLM 固定 Rubric 裁判](lessons/stage06/lesson01.md)：未开始。
- [6.2 成对比较](lessons/stage06/lesson02.md)：未开始。
- [6.3 多裁判投票](lessons/stage06/lesson03.md)：未开始；后续扩展。
- [6.4 Agent 裁判与工具核验](lessons/stage06/lesson04.md)：未开始；后续扩展。
- [6.5 人工抽样校准](lessons/stage06/lesson05.md)：未开始。
- [6.6 现成评测工具或 Benchmark 实践](lessons/stage06/lesson06.md)：未开始。

### [阶段 7：分层评测与归因](lessons/stage07/README.md)

状态：未开始

- [7.1 基座能力准入](lessons/stage07/lesson01.md)：未开始。
- [7.2 规划与路由组件评测](lessons/stage07/lesson02.md)：未开始。
- [7.3 反思与记忆组件评测](lessons/stage07/lesson03.md)：未开始。
- [7.4 端到端轨迹评测](lessons/stage07/lesson04.md)：未开始。
- [7.5 Model × Harness 实验](lessons/stage07/lesson05.md)：未开始。

### [阶段 8：对抗与发布门禁](lessons/stage08/README.md)

状态：未开始

- [8.1 歧义与脏输入](lessons/stage08/lesson01.md)：未开始。
- [8.2 提示注入](lessons/stage08/lesson02.md)：未开始。
- [8.3 越权与危险动作](lessons/stage08/lesson03.md)：未开始。
- [8.4 安全一票否决](lessons/stage08/lesson04.md)：未开始。
- [8.5 回归与退化告警](lessons/stage08/lesson05.md)：未开始。

### [阶段 9：数据飞轮](lessons/stage09/README.md)

状态：未开始

- [9.1 异常识别](lessons/stage09/lesson01.md)：未开始。
- [9.2 脱敏去重与来源](lessons/stage09/lesson02.md)：未开始。
- [9.3 标注工作台](lessons/stage09/lesson03.md)：未开始；后续扩展。
- [9.4 Badcase 入库](lessons/stage09/lesson04.md)：未开始。
- [9.5 修复回测与派生回归](lessons/stage09/lesson05.md)：未开始。

### [阶段 10：报告与面试验收](lessons/stage10/README.md)

状态：未开始

- [10.1 标准评测报告](lessons/stage10/lesson01.md)：未开始。
- [10.2 实验复现](lessons/stage10/lesson02.md)：未开始。
- [10.3 阶段总复盘](lessons/stage10/lesson03.md)：未开始。
- [10.4 面试与简历证据](lessons/stage10/lesson04.md)：未开始。

## 方法来源

- [美团白皮书](https://tech.meituan.com/2026/09/10/Agent-Evaluation-White-Paper-01.html)
- [AgentLoop 实践](https://developer.aliyun.com/article/1758156)
- [PawBench 官方仓库](https://github.com/agentscope-ai/PawBench)
- [字节 Data Agent 三层评测](https://www.cnblogs.com/bytedata/p/19399354)
- [Anthropic Agent Evals](https://www.anthropic.com/research/demystifying-evals-for-ai-agents)

采用上述方法论；课时拆分、字段和验收约定为本项目设计。
