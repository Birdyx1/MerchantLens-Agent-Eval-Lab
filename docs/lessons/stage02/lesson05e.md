# 2.5e 暴露 Python 执行工具

状态：已通过（教师代写）。

[2.5 总览](lesson05.md) · [阶段文档](README.md) · [总计划](../../plan.md)

建议用时：20 分钟。

## 知识点

Python 执行器与 MCP 服务保持解耦。创建服务时注入执行函数，测试用模拟函数，真实运行时注入已实现的容器执行器。当前官方 SDK 2.3.0 能把返回的 dataclass 转为结构化工具结果；验收时仍要实际检查 `structured_content`。[官方工具文档](https://py.sdk.modelcontextprotocol.io/get-started/first-steps/)

## 实践任务

在 `src/merchant_agent/mcp_server.py` 给 `create_server` 增加可选参数 `python_executor: Callable[[str, int], PythonRunResult] | None = None`。仅当提供它时注册：

```python
def execute_python(code: str, timeout_seconds: int) -> PythonRunResult:
    ...
```

工具内部把参数传给注入的执行函数，并返回 `PythonRunResult`。保留 SQL 和搜索工具的原行为。不要让模型选择 Docker 镜像、容器名称或资源限制；这些在执行器内部固定。

## 验收标准

1. 不注入执行器时，不发现 `execute_python`；注入模拟函数时能发现，参数 Schema 只有 `code` 和 `timeout_seconds`。
2. 客户端调用后，模拟函数收到原参数，`structured_content` 包含状态、输出、退出码、耗时、截断标记和 OOM 标记。
3. SQL 与搜索工具的发现和调用不退化；本课不用 Docker 执行用户代码。

## 面试考点与踩坑

- MCP 负责工具协议，执行器负责隔离和资源限制；模型不应配置隔离边界。
- 注入模拟执行器可验证协议层，真实 Docker 验收已在 2.3 记录。
- 结构化结果比解析文本更适合评测和轨迹埋点。

## 提交与评审记录

- 2026-11-01：开课，等待学员提交。
- 2026-11-01：应学员要求由教师实现。进程内 MCP 客户端验证：未注入时不暴露 Python 工具，注入模拟函数后参数 Schema 仅有 code 与 timeout_seconds；结构化返回包含全部八个结果字段。SQL 和搜索工具回归通过。本课未运行 Docker。
