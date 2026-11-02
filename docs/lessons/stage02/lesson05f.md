# 2.5f 启动 stdio MCP 服务

状态：已通过（教师代写）。

[2.5 总览](lesson05.md) · [阶段文档](README.md) · [总计划](../../plan.md)

建议用时：15 分钟。

## 知识点

前面用 `Client(server)` 做了进程内协议测试；真实宿主可以通过 stdio 启动独立服务进程。官方 SDK 的 `server.run()` 默认使用 stdio，需放在 `if __name__ == "__main__"` 下，避免导入模块时阻塞。[官方运行文档](https://py.sdk.modelcontextprotocol.io/run/)

stdio 的标准输出用于协议消息；启动代码不能向 stdout 打印日志。

## 实践任务

新建 `src/merchant_agent/mcp_stdio.py`：

1. 从环境变量 `MERCHANT_DB_PATH` 读取固定数据库路径；缺失或空白时抛 `RuntimeError`，不启动服务。
2. 调用现有 `create_server(db_path)` 创建服务。本课先只暴露 SQL 工具。
3. 在 `if __name__ == "__main__":` 下调用 `server.run()`；导入模块时不能启动。
4. 不打印到 stdout。

## 验收标准

- 导入模块能立即返回，不启动 stdio 服务。
- 缺失数据库路径时启动失败，错误明确；有效路径时服务等待 MCP 客户端连接。
- 下一课使用独立进程客户端验证工具发现与调用；本课不把进程内测试当作传输验收。

## 面试考点与踩坑

- stdio 是本地宿主与子进程通信的传输方式；后续部署 HTTP 才涉及监听端口。
- stdout 混入调试文本可能破坏协议流。
- 数据库路径属于部署配置，不应暴露给模型。

## 提交与评审记录

- 2026-11-01：开课，等待学员提交。
- 2026-11-01：应学员要求，教师实现 stdio 启动入口。验证导入模块不启动、缺失路径报错且不创建服务、有效路径去除首尾空白后调用 `create_server` 与 `run()`。跨进程传输留到下一课验收。
