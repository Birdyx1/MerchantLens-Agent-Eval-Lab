# 2.3g 容器清理

状态：已通过。

[阶段文档](README.md) · [总计划](../../plan.md)

建议用时：20—30 分钟。目标：为之后的执行器实现一个受限的容器清理函数。

## 知识点

等待 Docker 客户端超时，并不等于容器一定已经停止。执行器需要主动处理目标容器，并在清理失败时向上报告。`docker rm --force` 可以强制删除运行中的目标容器；其命令失败或超时不能当成清理成功。[Docker 官方文档](https://docs.docker.com/reference/cli/docker/container/rm/)

## 实践任务

在 `src/merchant_agent/tools/python_sandbox/python_runner.py` 中新增：

```python
def remove_container(container_id: str) -> None:
    ...
```

输入约定：container_id 由**可信执行器内部**取得，不直接接受 Agent 或用户指定的目标。本课限制它为 64 位小写十六进制；格式错误时抛出 ValueError，不调用 Docker。

格式正确时，通过 `subprocess.run` 的参数列表执行 `docker rm --force` 和该 ID；使用 `check=True`、`capture_output=True`、`text=True`、`timeout=5`，不使用 shell。命令失败、超时或 Docker 不存在时，让异常传给调用方。

**练习时只用 mock 模拟 subprocess，不实际删除容器。** 本课不实现“容器不存在时视作成功”，不要求你处理并发。

## 验收标准

1. 有效 ID 产生预期的参数列表和固定选项，成功返回 None。
2. ID 长度错误、含非法字符或空字符串时抛 ValueError，且不调用 subprocess。
3. 非零退出、超时与 Docker 不存在的异常能向上传播。
4. 测试使用模拟 subprocess，不删除真实容器。不能凭函数定义声称 Docker 容器已被清理。

## 面试考点与踩坑

- `subprocess.run` 的超时只说明客户端等待超时，不能证明守护进程没有继续处理；清理结果仍需核验。
- 格式检查不是授权机制；执行器必须只清理自己创建并记录的容器。
- 真实运行器还要解决创建时超时、输出的流式限制和各种失败路径；本课没有完成这些能力。

## 提交与评审记录

- 2026-11-01：学员实现 `remove_container`。mock 验证有效 ID 的参数与返回值、非法 ID 不调用 Docker，以及非零退出、超时、命令不存在的异常传播；本课通过。没有实际删除容器；真实执行器与隔离验证仍在 2.3h。
