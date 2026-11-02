# 3.7b 墙钟时限与取消

状态：已通过（教师实现，2026-11-02）。

[本课汇总](lesson07.md) · [阶段文档](README.md) · [总计划](../../plan.md)

## 知识点

`max_steps` 限制图的决策次数，不能保证运行耗时。`run_agent` 在单次 `ainvoke` 外设置 `asyncio.timeout`，超时抛出 `AgentDeadlineExceeded`，其 `reason` 为 `deadline`。这是一次未完成的调用，不能生成正常最终答案。

内部模型或工具抛出的 `TimeoutError` 应保持原类型；通过 `deadline.expired()` 判断是否由本层时限触发。外部 `CancelledError` 继续传播。

## 实践任务

在运行入口增加可选 `timeout_seconds`；校验有限正数；编写测试区分墙钟超时、内部超时、外部取消和非法参数。

输入：已编译图、初始状态、可选秒数。输出：完整 AgentState，或明确的超时／取消异常。

## 验收标准

- 墙钟时限到达时抛出 `AgentDeadlineExceeded`。
- 内部 `TimeoutError` 不被误判为墙钟超时。
- 外部取消继续传播；非法时限在调用图前拒绝。
- 全套 pytest 通过。

## 面试考点与踩坑

异步取消是协作式的：如果底层工具或清理动作阻塞，调用可能晚于指定秒数才结束。MCP 服务和 Docker 任务仍需各自的超时与清理机制。调用方需要将 deadline 记录为未完成运行，后续再接入根 Trace 的运行终止事件。

## 提交与评审记录

2026-11-02：教师实现；新增 8 个测试，全套 pytest 99 passed。
