# 1.2 Span 的 JSON Schema

状态：已通过（教师协助完成，独立掌握尚未验证）。

[阶段文档](README.md) · [总计划](../../plan.md)

建议用时：15—25 分钟。目标：定义上一课单条 Span 的结构约束。

## 知识点

JSON Schema 用于描述 JSON 数据的结构约束。`properties` 定义字段规则，`required` 指定必填字段，`additionalProperties` 可以禁止未声明字段。仅在 `properties` 中列出字段，并不会自动使它必填。[JSON Schema 官方文档](https://json-schema.org/understanding-json-schema/reference/object)

本课沿用项目自定义的 Span JSON 表示；Schema 是项目契约，不是 OpenTelemetry 或 OTLP 官方 Schema。

## 实践任务

创建 `schemas/span.schema.json`，使用 JSON Schema Draft 2020-12，校验**单个 Span 对象**，字段沿用 `fixtures/traces/basic.json`：

- 七个字段全部必填，不允许未声明的顶层字段。
- `trace_id`：32 位小写十六进制且非全零；`span_id`：16 位小写十六进制且非全零。
- `parent_span_id`：允许 null 或符合 `span_id` 规则的字符串。
- `name`、`start_time`、`end_time` 为字符串；`attributes` 为对象，内容暂不限制。

上一课的文件是数组；本课的 Schema 作用于数组中的每个元素。无需修改该文件，也无需编写校验器。

## 验收标准

1. Schema 本身是合法的 Draft 2020-12 JSON Schema；上一课两条 Span 分别能通过。
2. 单条 Span 缺少必填字段、顶层多出未声明字段、ID 长度错误、包含非小写十六进制字符或 ID 全零时均不通过。
3. 父 ID 为 null 或合法非零 ID 时可通过；`name`、时间字段或 `attributes` 类型不符合要求时不通过。
4. 本课只验证时间字段类型，不判断时间内容或先后顺序；不要求 Schema 检查跨 Span 的 ID 一致性或父子引用。

## 面试考点与踩坑

- `properties` 和 `required` 的职责不同。
- `pattern` 默认匹配字符串的任意位置，要留意边界和长度。[官方字符串文档](https://json-schema.org/understanding-json-schema/reference/string)
- 单对象结构校验无法直接证明多个 Span 属于同一条 Trace；跨记录关系留待后续语义校验。

## 提交与评审记录

- 2026-10-31 阶段性提交：`schemas/span/schema.json`。JSON 可解析，已声明字段类型、必填项和顶层额外字段限制。
- 仍需补充 `attributes` 定义与必填项；`parent_span_id` 需允许 null；两个 ID 及非空父 ID 需限定格式并排除全零。
- 课时指定文件为 `schemas/span.schema.json`，当前提交使用了不同路径；需改为指定路径。
- `date-time-offset` 不属于本课要求的格式约束；本课只检查时间字段的字符串类型，建议移除该 format。
- 未代改学员 Schema；等待修订，通过后进入下一课。
- 2026-10-31 应学员要求，教师将文件移动至指定路径并完成 Schema：使用 `$defs` 复用 ID 规则，`anyOf` 表达可空父 ID，补充长度、字符和非全零约束，移除非本课要求的 format 及 JSON 尾逗号。
- 使用 Python jsonschema 的 Draft202012Validator 验证：Schema 自身合法，第一课两条记录和非空父 ID 通过，15 个缺字段、多余字段、错误类型及无效 ID 样本被拒绝。此结果验证文件行为，不能证明学员已独立掌握。
- 文件满足本课验收标准，按学员“下一步”请求推进；本课由教师协助实现，不能作为学员独立实现或独立掌握的证据。后续可复习 `required`、`properties`、`$ref` 和 `anyOf`。
