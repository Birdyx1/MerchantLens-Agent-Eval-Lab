# Agent 与评测体系总计划

更新时间：2026-11-01（Asia/Shanghai）

今日安排：[2026-11-01 四小时学习计划](lessons/stage01/2026-11-01-plan.md)。

## 当前进度

- 当前进度：阶段 1 的基础课时和复盘已完成；阶段 2 的 2.3b 在教师协助修复导入后通过，2.3c 尚未开课。当前工具环境无法访问 Docker 守护进程，2.3b 仅构造参数；2.3c 再进行真实执行验证。初始化数据库失败清理和并发保护尚未实现。1.6 仅完成轨迹读取；证据核验、工具快照回放及父子和重试语义校验将在 7.4 前补齐。
- 已验收课时：12（1.2、1.4、1.5、1.7、2.1、2.3a、2.3b 有教师协助，1.3、2.2a 参考示例后手写）。
- 学员负责实现；教师负责讲解、评审、纠错与验收。

## 教学与维护规则

- 每课聚焦一个知识点、一个小产物；任务过大时继续拆课并同步目录。
- 顺序：知识点 → 任务 → 验收标准 → 学员提交 → 评审修改 → 通过。
- 通过后才进入下一课；阶段结束先复盘。
- 不提供完整实现，允许固定类型、数据结构与协议规范。
- 每次授课、评审、修改和验收后，同步更新总计划、阶段文档、课时文档。
- 状态：未开始、进行中、待评审、修改中、已通过。未经评审不得标为已通过。
- 未来课时只建立标题与占位，正式开课时再填写短讲义、任务、验收和面试考点。
- 每课明确区分：公开标准、框架约定、项目自定义设计；技术约定附原始来源，不把自定义字段称为行业统一标准。
- Trace 正式设计以 OpenTelemetry Trace/Span 语义为基础；JSON 存储格式与评测扩展明确标记为项目约定。第一课改为两条模拟 Span 的层级练习，替换旧六字段 JSONL 作业；本地 JSON 不是 OTLP JSON 或完整生产协议。

## 实习岗位对齐补充

- 阶段 5 新增 5.6：完成首版小规模评测报告，形成“任务集 → 批量执行 → 轨迹 → 规则评分 → 失败分类 → 报告”的完整成果，并提供同一任务集上两个版本或配置的初步对比。阶段 10 再完善为标准报告，不把第一份成果推迟到阶段 10。
- 阶段 6 新增 6.6：选择一个现成评测工具或公开 Benchmark，完成一次小规模运行与分析，理解任务格式、输入输出、评分逻辑和失败原因；开课时根据项目适配性与官方文档确定工具、版本及范围，不要求同时学习多个框架或跑完整榜单。
- 6.3 多裁判投票、6.4 Agent 裁判与工具核验、9.3 标注工作台保留为后续扩展，安排在阶段 10 主线验收后；主线先完成规则评分、单个 LLM 裁判、人工抽检和版本比较。
- 阶段 6 主线顺序：6.1 → 6.2 → 6.5 → 6.6；阶段 9 主线顺序：9.1 → 9.2 → 9.4 → 9.5，先用文件或简单表格维护标注与复核记录。主线课时仍逐课验收，扩展课不作为主线阶段完成的前置条件，单独保留状态与验收记录。
- 本轮只补充上述成果、外部实践和主线/扩展安排；当前课时与已验收进度保持不变，未来课时仍在正式开课时补充讲义、任务与具体验收标准。

## 项目约束

- Python、LangGraph、官方 MCP Python SDK；工具为 SQL、Python 和网页检索。
- 模型、Harness、工具、记忆解耦；Trace 使用结构化 JSON，记录显式计划、决策摘要及全部实际调用。
- Golden、Regression、Badcase、Negative 四集合物理隔离，回流不自动混入黄金集。
- 主线使用 Code 与单个 LLM 裁判，辅以人工独立标注、仲裁及定期抽样校准；多裁判与 Agent 裁判在后续扩展中完成。
- 基座、组件、端到端三层评测；结果、轨迹、成本、安全四类指标。
- 测试流量标记保留在控制面，不暴露给被测模型；预留 Holdout、禁止评测样本进入 few-shot、轮换黄金集。
- Trace → 异常识别 → 标注与复核记录 → 回流入库；报告包含版本对比、根因、Judge 一致性与退化告警。完整标注工作台在后续扩展中完成。
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

状态：进行中

- [2.1 业务数据口径](lessons/stage02/lesson01.md)：已通过（教师协助修改）。
- [2.2a 准备 SQLite 数据](lessons/stage02/lesson02.md)：已通过（分步参考示例后手写）。
- [2.2b SQL 只读查询](lessons/stage02/lesson02b.md)：已通过。
- [2.3a Python 请求校验](lessons/stage02/lesson03.md)：已通过（教师协助修改）。
- [2.3b 构造容器启动参数](lessons/stage02/lesson03b.md)：已通过（教师协助导入配置）。
- [2.3c Python 执行与隔离验证](lessons/stage02/lesson03c.md)：未开始。
- [2.4 网页检索证据](lessons/stage02/lesson04.md)：未开始。
- [2.5 官方 MCP SDK 接入](lessons/stage02/lesson05.md)：未开始。
- [2.6 工具故障与埋点](lessons/stage02/lesson06.md)：未开始。

### [阶段 3：LangGraph ReAct Agent](lessons/stage03/README.md)

状态：未开始

- [3.1 基座模型适配](lessons/stage03/lesson01.md)：未开始。
- [3.2 短期状态定义](lessons/stage03/lesson02.md)：未开始。
- [3.3 规划与路由](lessons/stage03/lesson03.md)：未开始。
- [3.4 行动与观察循环](lessons/stage03/lesson04.md)：未开始。
- [3.5 反思与有界重试](lessons/stage03/lesson05.md)：未开始。
- [3.6 记忆与检查点](lessons/stage03/lesson06.md)：未开始。
- [3.7 终止与预算](lessons/stage03/lesson07.md)：未开始。

### [阶段 4：评测资产与标注](lessons/stage04/README.md)

状态：未开始

- [4.1 Task 数据契约](lessons/stage04/lesson01.md)：未开始。
- [4.2 四集合物理隔离](lessons/stage04/lesson02.md)：未开始。
- [4.3 Rubric 编写](lessons/stage04/lesson03.md)：未开始。
- [4.4 双人独立标注](lessons/stage04/lesson04.md)：未开始。
- [4.5 标注一致性与仲裁](lessons/stage04/lesson05.md)：未开始。
- [4.6 Holdout 与污染防护](lessons/stage04/lesson06.md)：未开始。

### [阶段 5：Python 评测流水线](lessons/stage05/README.md)

状态：未开始

- [5.1 Trial 与环境重置](lessons/stage05/lesson01.md)：未开始。
- [5.2 Code Evaluator](lessons/stage05/lesson02.md)：未开始。
- [5.3 四类指标](lessons/stage05/lesson03.md)：未开始。
- [5.4 重复试验与不确定性](lessons/stage05/lesson04.md)：未开始。
- [5.5 批量执行](lessons/stage05/lesson05.md)：未开始。
- [5.6 首版小规模评测报告](lessons/stage05/lesson06.md)：未开始。

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
