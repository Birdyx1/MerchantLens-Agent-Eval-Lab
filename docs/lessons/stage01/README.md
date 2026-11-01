# 阶段 1：Trace 与工程基础

状态：已完成基础课时与复盘；后续能力待补齐。

[总计划](../../plan.md)

[2026-11-01 四小时学习计划](2026-11-01-plan.md)

## 课时

| 课时 | 状态 |
|---|---|
| [1.1 理解 Trace 与 Span](lesson01.md) | 已通过 |
| [1.2 Span 的 JSON Schema](lesson02.md) | 已通过（教师协助） |
| [1.3 Trace 追加写入](lesson03.md) | 已通过（参考示例后手写） |
| [1.4 调用关联与重试](lesson04.md) | 已通过（教师协助修改） |
| [1.5 跨事件语义校验](lesson05.md) | 已通过（教师协助修改） |
| [1.6 证据与回放](lesson06.md) | 已通过（轨迹读取） |
| [1.7 运行版本清单](lesson07.md) | 已通过（教师协助修改） |

## 阶段复盘

状态：已完成；两个问题均已回答，第 ② 题在教师解释后回答正确。

- 已有：模拟 Span、单条 Span JSON Schema、单进程 JSONL 写入和读取、仅检查 trace_id 与 span_id 的跨记录函数、模拟版本清单。
- 学习记录：1.2、1.4、1.5、1.7 有教师协助；1.3 参考示例后手写；1.6 由学员完成并通过验证。
- 尚未实现：父子和重试语义检查、证据关联和核验、工具快照回放、生产级 Trace 采集。这些将在 7.4 端到端轨迹评测前补齐；不能将 JSONL 读取视为完整回放。
- 复盘问题：① 重试前后两个 Span 的 trace_id、span_id 和 operation_id 应如何关联？② 为什么逐条通过 Schema 后，仍需要跨记录校验？
- 学员已正确回答第 ① 题：trace_id 相同、span_id 不同、operation_id 相同；第 ② 题等待回答。
- 学员对第 ② 题提出“校验内容”；教师进一步解释单条结构与多条记录关系的区别，等待学员确认理解。
- 学员在解释后正确回答：两条 Span 的 span_id 相同，即使分别通过 Schema，也不能通过本项目的跨记录去重检查。

## 来源与设计边界

Trace/Span 概念以 [OpenTelemetry](https://opentelemetry.io/docs/specs/otel/trace/api/) 为依据，结合 [LangSmith](https://docs.langchain.com/langsmith/observability-concepts) 理解 Agent 运行层级。第一课改为两条模拟 Span 的父子关系练习，替换旧六字段作业。JSON 表示为项目约定，不能称为 OTLP 或工业统一格式。

## 最新评审

2026-11-01：1.7 清单由教师协助修改并验证，学员在提示后正确回答比较 Harness 时应固定模型。已通过 7 课，阶段复盘尚未进行。
