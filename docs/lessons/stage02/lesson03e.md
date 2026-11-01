# 2.3e 执行前检查镜像

状态：已通过。

[阶段文档](README.md) · [总计划](../../plan.md)

建议用时：15—25 分钟。目标：用 Python 检查本地 Docker 镜像并读取其 ID。

## 知识点

上一课手动执行了 `docker image inspect`。执行器也需要检查镜像是否存在，并记录具体镜像 ID：标签可能被更新，记录 ID 有助于后续复查实验使用的镜像。

Python 的 `subprocess.run` 可以接收参数列表并等待进程完成。这里是一次只读检查，不启动容器，不执行用户代码。

## 实践任务

创建 `src/merchant_agent/tools/python_sandbox/python_runner.py`，实现：

```python
def inspect_python_image() -> str:
    ...
```

要求：用 `subprocess.run` 执行固定参数列表，相当于：

```text
docker image inspect --format {{.Id}} python:3.13-alpine
```

捕获文本输出、等待最多 5 秒；成功时返回去掉首尾空白的镜像 ID。Docker 不存在、镜像不存在、检查失败或超时，应把异常传给调用方。不要使用 `shell=True`。

提示：查阅 `subprocess.run` 的 `capture_output`、`text`、`check` 和 `timeout` 参数。[Python 官方文档](https://docs.python.org/3/library/subprocess.html#subprocess.run)

## 验收标准

1. 镜像存在且 Docker 可访问时返回以 `sha256:` 开头的 ID，不含尾部换行。
2. 命令为参数列表，使用固定镜像，不启动容器或执行传入代码。
3. 检查失败、超时和 Docker 命令不存在时，异常不被吞掉。
4. 不修改镜像或数据库。本课不声称已实现沙箱、代码执行或清理。

当前 Codex 的受限工具环境不能访问 Docker socket；实际检查可在用户终端执行，评审可通过模拟 subprocess 验证参数及异常传播。不得把模拟测试当成真实容器测试。

## 面试考点与踩坑

- 镜像标签可能指向不同内容；镜像 ID 是本地镜像标识，仓库 digest 与它概念不同。
- `check=True` 可以让非零退出码变为异常；`timeout` 限制此处的 inspect 进程，不等于限制未来容器执行。
- 不用 `shell=True`，也不从用户代码拼接宿主机 shell 命令。

## 提交与评审记录

- 2026-11-01：已开课，等待学员提交。上一课根据学员终端输出确认固定容器可以运行。
- 2026-11-01：学员提交函数；模拟验证固定参数、成功输出、命令不存在、非零退出和超时均通过。沙箱外执行真实只读检查，返回本地镜像 ID `sha256:7984cf56ceaddebe4fefeb75d64000b9f45d8b77b11a09b24524da6cdc3af0c8`。
- 本课通过；未借此执行容器或验证隔离、超时终止和清理。相关工作安排在 2.3h。
