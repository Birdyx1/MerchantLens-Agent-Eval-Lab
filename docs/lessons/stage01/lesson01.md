# 1.1 理解 Trace 与 Span

状态：已通过，修订文件与概念回答已复核。

[阶段文档](README.md) · [总计划](../../plan.md)

建议用时：10—15 分钟。目标：用两条模拟 Span 表达一次请求及其工具调用。

## 知识点与来源

Trace 表示一次操作的执行链路；Span 表示链路中的一次操作，例如 Agent 请求、模型调用或 SQL 调用。同一 Trace 的 Span 共享 trace_id，分别有自己的 span_id，通过父 Span 表达层级。

本课示例：Agent 请求为根 Span，其内部的 SQL 查询为子 Span。父子结构表达调用归属，不等于所有操作必须串行。

- 标准依据：[OpenTelemetry Tracing API](https://opentelemetry.io/docs/specs/otel/trace/api/)。TraceId 为 16 字节，SpanId 为 8 字节，全零 ID 无效。
- 框架对照：[LangSmith 可观测性概念](https://docs.langchain.com/langsmith/observability-concepts)。一次工作称 run，可对应 Span；相关 runs 组成 Trace。
- 下方是项目练习使用的本地 JSON 表示，不是 OTLP JSON；字段命名、时间字符串和根节点 null 表示法是项目约定。

## 实践任务

创建 fixtures/traces/basic.json，写一个 JSON 数组，包含根操作 agent.request 和子操作 sql.query 两条模拟 Span。只手写记录，不运行模型或工具。

| 字段 | 类型 | 本课约定 |
|---|---|---|
| trace_id | string | 32 位小写十六进制，非全零；两条相同 |
| span_id | string | 16 位小写十六进制，非全零；两条不同 |
| parent_span_id | string 或 null | 根为 null；SQL 指向根 span_id |
| name | string | 分别为 agent.request 和 sql.query |
| start_time | string | 带 Z 后缀的 UTC 时间 |
| end_time | string | 带 Z 后缀的 UTC 时间，不早于开始 |
| attributes | object | 两条均有 simulated: true；工具名和查询语句可选，本课不作通过条件 |

本课限定一次同步查询，子操作时间范围落在根操作内。不保存密钥或真实个人信息。结果、错误、成本及证据字段后续逐步补齐。

提交时另用一句话解释：为什么工具调用不能和 Agent 请求共用 span_id？

## 验收标准

1. 文件为合法 JSON 数组，恰有两条记录，七个字段完整且类型正确。
2. trace_id 一致，span_id 各自唯一，长度与非全零要求满足。
3. 根节点无父节点，SQL 正确引用根节点。
4. 时间符合本课同步调用范围，模拟标记明确，能解释两个 ID 的职责。

## 面试考点与踩坑

- trace_id 关联整条链路，span_id 定位一次操作。
- 工具调用是子 Span；Span Event 是操作中的时间点记录，不要混用。
- 自定义 JSON 必须说明标准映射，不能称为 OTLP。
- 本课七字段只练层级，不构成完整生产 Trace 协议。

## 提交与评审记录

- 本课替换原六字段 JSONL 练习；旧练习无需补做，也未标记为通过。
- 2026-10-31 首次提交：fixtures/traces/basic.json，已检查实际文件；已通过课时仍为 0。
- 已满足：JSON 可解析；两条记录字段及类型正确；根 parent 为 null；子 parent 指向根 span_id；各自起止时间有序；模拟标记明确。
- 必须修改 1：第 14 行 trace_id 与第 3 行不同，同一链路须共享 trace_id。仅 parent_span_id 匹配不足以形成有效的同 Trace 父子关系。
- 必须修改 2：第 15 行 span_id 只有 15 位，应为 16 位非全零十六进制，并保持与根 ID 不同。
- 必须修改 3：根 end_time 为 08:00:01Z，子 end_time 为 08:00:02Z，不符合本课同步调用的包含关系。根操作需要覆盖子操作结束时刻；这不是所有异步追踪场景的普遍时间限制。
- 待补充：一句话解释为什么两个操作不能共用 span_id。
- 教学口径对齐：以聊天中的任务为准，工具名和查询语句是可选扩展，不因先前文档额外要求而阻断验收。
- 修改方向已给出；未代改学员文件。修订提交并通过后才进入 1.2。

### 2026-10-31 修订复核

- trace_id 已统一，子 span_id 已修为 16 位非全零十六进制；同步时间包含关系已满足。JSON、字段、ID、父子引用、UTC 时间与模拟标记检查均通过。
- 学员回答：“两个操作不是同一原子操作。”已理解不同操作需分别标识。术语纠正：Span 不要求原子性，可以包含子 Span；更准确的表述是两个独立记录的操作需要不同 span_id，共享 trace_id 并用父 ID 关联。
- 子操作开始和结束时间相同，符合本课“不早于开始”的条件，不阻断验收；真实埋点应记录实际测量时间。
- 验收结论：1.1 已通过。未代改学员文件。下一课 1.2 尚未开课。
