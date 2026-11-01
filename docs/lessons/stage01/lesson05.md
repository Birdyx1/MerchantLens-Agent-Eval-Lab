# 1.5 跨 Span 语义校验

状态：已通过（教师协助修改，独立掌握尚未验证）。

[阶段文档](README.md) · [总计划](../../plan.md)

建议用时：约 60—75 分钟，包含讲解、编写和评审。

## 知识点

JSON Schema 可以检查单条 Span 的字段和类型，但每条记录分别合法，不代表它们组合起来就是一条合法的 Trace。例如，两条 Span 各自的 ID 格式都正确，但 span_id 相同，依然无法区分两次操作。

本课只检查两条跨记录规则：同一 Trace 中各 Span 的 trace_id 一致，span_id 不重复。这是 Trace/Span 语义在本项目中的一个简化检查；参考 [OpenTelemetry Tracing API](https://opentelemetry.io/docs/specs/otel/trace/api/)。

## 实践任务

创建 `src/merchant_agent/tracing/validator.py`，自行实现：

```python
def validate_trace(spans: list[dict]) -> list[str]:
    ...
```

输入约定：非空列表；每条 Span 已通过单条 Schema 校验。函数不修改输入。

返回规则：

- 全部 trace_id 一致、span_id 无重复：返回空列表 `[]`。
- trace_id 不一致：返回错误码 `mixed_trace_id`。
- 存在重复 span_id：返回错误码 `duplicate_span_id`。
- 两种错误同时存在时两个错误码都返回，顺序先 `mixed_trace_id`、后 `duplicate_span_id`；同一种错误只出现一次。

提示：可以先逐条取出 ID，再思考 Python 的 `set` 能否帮助判断是否存在不同值或重复值。不要修改已有的 `fixtures/traces/retry.json`。

## 验收标准

1. 用 `retry.json` 中的三条记录调用函数，返回 `[]`。
2. 用一份临时副本制造重复 span_id，返回 `["duplicate_span_id"]`。
3. 再用另一份副本制造不同 trace_id，返回 `["mixed_trace_id"]`。
4. 两种问题同时存在时按约定顺序返回两个错误码，且输入数据未被修改。

## 面试考点与踩坑

- Schema 校验单条结构；跨记录检查验证记录之间的关系。
- 不要发现第一处错误就直接返回，否则会漏报另一类错误。
- 本课假设输入非空且单条结构已验证；结果为 `[]` 只说明这两项通过，不代表整个 Trace 合法。父子引用、重试及时间等规则留待后续扩展。

## 提交与评审记录

- 2026-11-01 首次评审：学员使用 set 收集 ID 的方向正确，函数不修改输入；5 种场景实测结果均与预期不符。
- 空 trace_id_set 在第一条记录到来时自然不包含当前 ID，导致正常数据也错误报告 mixed_trace_id；多个不同 ID 还会重复报告。
- 多次 span_id 重复时会重复追加同一个错误码；循环内按遇到顺序追加也不能保证两个错误码的固定顺序。
- 修改提示：先遍历收集两个集合，结束后按固定顺序比较 trace_id 集合大小与 span_id 集合和原列表长度，每类错误最多追加一次。未代改学员函数，等待重新提交。
- 2026-11-01：应学员要求由教师修改函数；正常、重复 ID、不同 Trace、两种错误同时出现和多次重复共五种情况通过验证，且输入保持不变。课时验收通过，独立实现能力尚未验证。
