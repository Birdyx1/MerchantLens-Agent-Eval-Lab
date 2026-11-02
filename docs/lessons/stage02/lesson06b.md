# 2.6b Python 执行状态归一化

状态：已通过（教师代写）。

[2.6 总览](lesson06.md) · [故障分类契约](../../contracts/tool_failures.md) · [总计划](../../plan.md)

建议用时：15 分钟。

## 知识点

工具内部状态与评测分类应分层。`run_python` 返回自己的 `PythonRunResult.status`；评测层读取它并映射到统一类别，同时保留原始状态，避免把 Docker 故障和用户程序错误混淆。此映射是本项目约定，不是 MCP 标准。

## 实践任务

新建 `src/merchant_agent/tools/python_sandbox/failure_classification.py`，实现纯函数：

```python
def classify_python_result(result: PythonRunResult) -> str:
    ...
```

映射：`succeeded → success`，`timeout → timeout`，`program_error → program_error`，`infrastructure_error → dependency_error`。未知状态抛 `ValueError`，不猜测类别。不修改原 `result`，不在函数里写 Trace、调用 Docker 或自动重试。

## 验收标准

1. 四种已知状态返回指定类别；未知状态抛 `ValueError`。
2. `succeeded` 且 `stdout` 为空仍归 `success`：Python 程序没有输出，不等于业务空结果。
3. 原始 `PythonRunResult.status` 不变；函数无 I/O 和副作用。

## 面试考点与踩坑

- 故障归一化属于适配层，不能把评测口径硬塞进 Docker 执行器。
- `program_error` 表示用户代码执行失败；`infrastructure_error` 表示执行环境故障，根因与重试策略不同。
- 不要根据 `stderr` 是否为空分类；成功程序也可能写标准错误流。

## 提交与评审记录

- 2026-11-01：开课，等待学员提交。
- 2026-11-01：学员调整学习方式，由教师实现、学员理解架构。教师完成纯函数与三项单元测试；四种状态映射、空 stdout、未知状态均通过，全套 14 个测试通过。本课已通过。
