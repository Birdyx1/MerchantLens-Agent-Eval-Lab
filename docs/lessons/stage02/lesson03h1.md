# 2.3h1 构造容器创建命令

状态：已通过。

[2.3h 总览](lesson03h.md) · [阶段文档](README.md) · [总计划](../../plan.md)

建议用时：15—20 分钟。产物：一个纯参数构造函数。

## 知识点

`docker create` 创建容器但不启动，并把容器 ID 输出到标准输出；后续运行器可先取得 ID，再跟踪和清理这个容器。`--rm` 会在退出时自动删除容器，不适合这一步需要显式跟踪和核验的流程。[Docker 官方 create 文档](https://docs.docker.com/reference/cli/docker/container/create/) · [run 文档](https://docs.docker.com/reference/cli/docker/container/run/)

本课只处理命令列表；不运行 Docker，也不声称容器隔离已验证。

## 实践任务

在 `src/merchant_agent/tools/python_sandbox/python_command.py` 新增：

```python
def build_docker_create_args(code: str, timeout_seconds: int) -> list[str]:
    ...
```

输入校验沿用 `validate_python_request`。返回的新列表以 `docker create` 开头，保留现有 `build_docker_args` 的固定隔离选项、镜像和 `python -I -c code`，但去掉 `--rm`。保留原函数的行为，不要改动它；不要调用 subprocess。

## 验收标准

1. 有效输入返回新列表；命令开头是 `docker create`，没有 `--rm`，其余固定选项与 `build_docker_args` 一致，代码仍作为最后一个独立参数。
2. 非法代码、超出 1～5 秒或布尔型超时抛 `ValueError`。
3. 连续调用得到相互独立的列表；原 `build_docker_args` 仍返回 `docker run --rm`。
4. 本课不启动或删除真实容器。

## 面试考点与踩坑

- 为什么先创建再启动？先拿到 ID，才能在后续超时路径中定位目标容器。
- `--rm` 与显式清理的取舍是什么？本项目选择显式清理以便记录和核验失败路径。
- 参数列表中的代码应是一个独立参数，不要拼接 shell 命令。

## 提交与评审记录

- 2026-11-01：学员完成函数；本地验证命令参数与原函数一致（除 `create` 和 `--rm`）、非法输入、列表独立性，未运行 Docker。本课通过。两个构造函数的固定参数有重复，后续共同参数变动时需同步检查或提取共享配置；不阻塞本课。创建失败、ID 校验、启动、输出采集、超时和清理留给后续小课。
