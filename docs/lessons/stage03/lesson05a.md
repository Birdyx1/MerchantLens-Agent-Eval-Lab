# 3.5a 工具故障转为观察

状态：已通过（教师实现）。

[3.5 总览](lesson05.md) · [故障分类契约](../../contracts/tool_failures.md) · [总计划](../../plan.md)

## 知识点

反思节点要先看见故障，才能决定修正参数、有限重试或结束。MCP 工具错误与协议结构错误可形成 `dependency_error` 观察；明确的调用超时形成 `timeout` 观察。Trace 写盘失败则不是普通工具故障：关键证据缺失时必须中断运行。

## 实践产物

教师新增 `ObservedToolFailure`，由 SQL、搜索和 Python 观测包装在 MCP 错误或协议错误时抛出；包装层仍先记录尝试 Span。`make_tool_node` 只捕获该类型与明确的超时，把失败类别、原始状态写入 `last_tool_result` 和工具消息，递增 `tool_attempt`。其他异常继续传播。

## 验收标准与结果

- MCP `is_error` 与超时各生成一次失败观察，State 中的 operation ID 与 Span 一致。
- Trace 写盘抛 `OSError` 时图中断，不生成伪观察。
- 全套 pytest：74 passed。

## 面试考点与踩坑

- 故障属于工具执行层，写盘失败属于可观测性基础设施；不能用同一个宽泛 `except Exception` 吞掉。
- 当前只把明确的 MCP 工具错误、协议错误和超时转成观察；其他客户端异常仍中断图。
- 本课尚未自动重试。下一小课制定可重试条件、次数和预算，并保留每次尝试 Span。

## 提交与评审记录

- 2026-11-02：教师实现并验收，本课通过。
