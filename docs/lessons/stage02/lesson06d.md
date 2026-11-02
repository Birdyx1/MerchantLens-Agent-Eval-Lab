# 2.6d MCP SQL 调用埋点

状态：已通过（教师实现）。

[2.6 总览](lesson06.md) · [故障分类契约](../../contracts/tool_failures.md) · [总计划](../../plan.md)

## 知识点与架构

埋点放在 MCP 客户端调用边界：这里同时能看见工具入参、协议结果、异常、耗时和重试序号。服务端工具负责业务执行，观测包装负责写 Span；两者解耦。`operation_id` 关联同一逻辑操作，`span_id` 区分每一次实际尝试。此处 `raw_status`、`outcome` 是项目自定义 Trace 属性。

## 实践产物

教师新增 `tracing/observed_sql.py` 的 `call_store_net_observed`：调用一次 `get_store_net`，按成功、空结果、MCP 错误、协议错误或超时分类，并在 `finally` 中调用 `append_span`。记录门店 ID、结果金额或错误类型，不记录任意异常消息。调用失败会在写盘后继续抛出；无效的 `attempt` 在调用前被拒绝。

## 验收标准与结果

- 真实进程内 MCP SQL 调用：门店 A 返回 12000 分，未知门店归 `empty_result`。
- MCP 错误、缺失结构化结果、超时均落盘并向上传播。
- 同一操作的超时与成功两次尝试各有独立 Span，保留共同 `operation_id` 和递增的 `attempt`。
- 全套 pytest：32 passed。

## 面试考点与踩坑

- 工具失败后仍需留下可归因的尝试记录；最终成功不覆盖早期失败。
- 业务空结果不是协议故障；MCP `is_error` 不能自动推断更细的根因。
- 本课仅覆盖 SQL 客户端路径；搜索与 Python 的统一观测、参数脱敏策略和真实 stdio 调用链尚待后续课时。

## 提交与评审记录

- 2026-11-01：教师实现并验证，课时通过。
