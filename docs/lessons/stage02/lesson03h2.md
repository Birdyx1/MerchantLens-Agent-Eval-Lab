# 2.3h2 校验容器 ID 输出

状态：已通过。

[2.3h 总览](lesson03h.md) · [阶段文档](README.md) · [总计划](../../plan.md)

建议用时：15 分钟。产物：一个纯解析函数。

## 知识点

Docker 官方说明 `docker create` 会把新容器 ID 写到标准输出。[Docker create 文档](https://docs.docker.com/reference/cli/docker/container/create/) 执行器不能把外部进程的任意输出直接交给清理命令；先验证它是完整的 64 位小写十六进制 ID。本项目采用这一严格格式作为内部契约，不声称这是 Docker 所有接口的统一输出规范。

## 实践任务

在 `src/merchant_agent/tools/python_sandbox/python_runner.py` 新增：

```python
def parse_container_id(stdout: str) -> str:
    ...
```

去除输出首尾空白后，若恰好为 64 位小写十六进制字符串，则返回该 ID。否则抛 `RuntimeError`，错误信息用固定文字，不拼接原始输出。本函数不调用 Docker。

## 验收标准

1. 64 位小写十六进制 ID 加末尾换行能正常解析；前后空白允许去除。
2. 空串、63 位、65 位、大写、非法字符、多余文字或多行内容均抛 `RuntimeError`。
3. 非字符串输入也抛 `RuntimeError`，不发生意外的 `AttributeError` 或 `TypeError`。
4. 错误消息不包含原始输出；函数不调用 subprocess。

## 面试考点与踩坑

- 为什么 `strip()` 之后仍要 `fullmatch`？去空白不能排除额外行或恶意字符。
- 为什么不把异常输出原样写入错误消息？外部输出可能含代码、控制字符或敏感信息；后续需单独做安全日志记录。
- 即使 ID 校验通过，创建超时或输出格式异常仍可能留下未知容器。真实创建前必须设计可追踪的名称和失败清理，不能把本课当成完整清理保障。

## 提交与评审记录

- 2026-11-01：开课，等待学员实现；本课不创建或删除容器。
- 2026-11-01：学员完成实现；有效 ID、空白、非法长度与字符、多行、非字符串和固定错误消息均通过验证；mock 确认未调用 subprocess。本课通过。
