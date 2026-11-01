# 1.4 调用关联与重试

状态：已通过（教师协助修改）。

[阶段文档](README.md) · [总计划](../../plan.md)

建议用时：15—20 分钟。目标：记录一次 SQL 查询超时后重试成功的轨迹。

## 知识点

一次逻辑查询可能执行多次：第一次超时，第二次成功。每次实际执行都有独立 Span；共享 trace_id、父 Span 和本项目定义的 operation_id。attempt 区分第几次尝试。

Trace/Span 的基本概念参考 [OpenTelemetry](https://opentelemetry.io/docs/specs/otel/trace/api/)；`operation_id`、`attempt`、`outcome` 及其取值是本课的项目约定，不是通用标准字段。

## 实践任务

参考第一课 `fixtures/traces/basic.json`，创建 `fixtures/traces/retry.json`，保存一个 JSON 数组，包含：

1. 一条 Agent 根 Span。
2. 一条 SQL 子 Span：第一次尝试超时。
3. 一条 SQL 子 Span：第二次尝试成功。

每条记录保留第一课的七个字段。两条 SQL 的 `attributes` 均包含 `simulated: true`、相同的字符串 `operation_id`、从 1 开始的整数 `attempt`，以及 `outcome`；第一次 outcome 写 `timeout`，第二次写 `success`。这些字段放在 attributes 内，沿用当前 Schema。

## 验收标准

1. JSON 数组有三条记录；每条分别通过 `schemas/span.schema.json`。
2. 三条属于同一 Trace，各自有不同 span_id；两次 SQL 的 parent_span_id 都指向根 Span。
3. 两次 SQL 使用相同非空 operation_id，attempt 分别为 1、2，outcome 分别为 timeout、success。
4. 在本课的同步示例中，两次尝试按时间先后排列，根 Span 覆盖它们的时间范围；保留第一次失败记录。

## 面试考点与踩坑

- span_id 区分每次执行；operation_id 在本项目中关联同一逻辑操作的多次尝试。
- 不要用第二次结果覆盖第一次失败，否则无法计算失败率和重试成本。
- 真实系统不能对所有操作盲目重试，尤其要考虑有副作用操作的幂等性；本课使用只读 SQL。

## 提交与评审记录

- 2026-10-31 首次评审：三条记录均通过单条 Span Schema；trace_id、父节点、operation_id、attempt 和 outcome 符合要求。
- 两条 SQL 使用相同的 span_id；每次执行必须使用不同且有效的 span_id。
- 两次 SQL 的开始和结束时间全部相同，无法从时间看出先后。本课同步模拟要求两次调用先后可辨；可调整为第一次结束早于第二次开始，根 Span 覆盖全部时间。这是本练习约定，真实系统的时间戳精度可能导致相等，不能仅凭此断定运行错误。
- 等待学员修正；未修改学员文件。通过后再进入 1.5。
- 2026-10-31：应学员要求，教师修改第二次调用的 span_id 和模拟时间。重新检查三条记录均通过 Schema，Trace 与父子关系、重试信息、时间先后及父时间覆盖均符合本课要求。
- 验收结论：通过（教师协助修改）；学员独立修正能力尚未验证。1.5 尚未开课。
