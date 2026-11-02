# 2.6f MCP Python 调用埋点

状态：已通过（教师实现）。

[2.6 总览](lesson06.md) · [故障分类契约](../../contracts/tool_failures.md) · [总计划](../../plan.md)

## 知识点与架构

Python 工具与 SQL、搜索不同：MCP 调用成功也可能返回 `timeout`、`program_error` 或 `infrastructure_error`。因此不能只看 MCP 的 `is_error`；要读取 `PythonRunResult.status`，用 2.6b 的映射函数得到评测类别，同时保留原始状态。

## 实践产物

教师新增 `tracing/observed_python.py` 的 `execute_python_observed`。它调用一次 MCP Python 工具、校验结构化结果、记录代码与超时时限、完整执行结果、状态、类别及耗时。执行器返回的超时是正常结构化结果，仍返回给上层；MCP 调用自身抛出的超时会先落盘再向上传播。协议损坏或未知状态归 `dependency_error`，不猜测成程序错误。

## 验收标准与结果

- 模拟执行器经真实进程内 MCP 协议，四种状态分别映射到 `success`、`timeout`、`program_error`、`dependency_error`。
- MCP 错误、缺失结果、调用超时及未知执行器状态均留下失败 Span。
- 全套 pytest：44 passed。

## 面试考点与踩坑

- “工具调用成功”不等于“用户程序成功”；两层状态都要保留。
- 代码、stdout 和 stderr 当前进入本地受控 Trace；上线前需要脱敏、访问控制、保留期与大小预算。
- 本课未运行真实 Docker，也未验证 Python 的真实 stdio 调用；这些是后续集成验收边界。

## 提交与评审记录

- 2026-11-01：教师实现并验证，本课通过。
