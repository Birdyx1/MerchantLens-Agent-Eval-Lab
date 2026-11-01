# 2.3d 验证容器运行环境

状态：已通过（依据学员提交的终端输出）。

[阶段文档](README.md) · [总计划](../../plan.md)

建议用时：10—20 分钟。目标：准备镜像并验证固定测试代码能在受限容器中启动。

## 知识点

Docker 客户端能够连接服务端，不代表所需镜像已经存在。项目的参数中使用 `--pull never`，因此必须先准备镜像。镜像标签可能更新，运行实验时应记录镜像 ID 或摘要。

## 实践任务

在自己的终端执行：

```bash
docker pull python:3.13-alpine
docker image inspect python:3.13-alpine --format '{{.Id}}'
```

然后运行固定的无害测试代码：

```bash
docker run --rm --pull never --network none --memory 128m --cpus 0.5 --pids-limit 64 --read-only --cap-drop ALL --user 65534:65534 python:3.13-alpine python -I -c 'print("sandbox-ready")'
```

## 验收标准

1. 镜像检查能返回镜像 ID；容器命令输出 `sandbox-ready` 并正常退出。
2. 提交镜像 ID 和命令输出；若拉取或运行失败，提交错误信息，先定位问题。
3. 本次只验证固定代码能否运行，不代表恶意代码隔离、超时、输出限制或清理机制已经通过验证。

## 面试考点与踩坑

- `--pull never` 避免运行时自动拉取；镜像不在本地时会失败。
- `--network none` 限制容器网络；`--read-only` 限制容器根文件系统写入，均需要后续验证。
- 不把固定代码运行成功等同于安全沙箱验收。

## 提交与评审记录

- 2026-11-01：已开课；教师此前只读检查确认 Docker 服务端可用，课程镜像尚未找到。等待学员准备和验证镜像。
- 学员提交终端输出：镜像已拉取，inspect 显示 ID `sha256:7984cf56ceaddebe4fefeb75d64000b9f45d8b77b11a09b24524da6cdc3af0c8`；固定测试容器输出 `sandbox-ready` 并返回 shell 提示符。
- 依据学员提供的终端输出验收通过；教师未独立运行该容器。隔离效果、超时终止、输出上限与清理的验证仍留待 2.3h。
