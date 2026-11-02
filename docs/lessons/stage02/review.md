# 阶段 2 复盘：业务工具与 MCP

状态：项目范围内完成（2026-11-01）。

[阶段课时](README.md) · [总计划](../../plan.md)

## 已形成的架构

业务工具层负责 SQL 只读查询、Tavily 网页检索和受限 Docker Python 执行；`create_server` 通过依赖注入把工具暴露为 MCP，stdio 入口根据环境配置决定工具可见性。客户端观测层分别记录 SQL、搜索和 Python 的每次调用，统一生成项目 Span 并写 JSONL。基座模型和 Agent Harness 尚未进入本阶段。

## 验收证据

- SQL 净收入口径与模拟订单可复算；真实 stdio 查询门店 A 返回 12000 分。
- 搜索有模拟服务与 Tavily 真服务；真实 stdio 搜索返回结构化结果列表。
- Python 执行器使用限制容器；真实 stdio 调用输出 `sandbox-ready`。
- 三工具同一 Trace 的四条 Span 通过 JSON Schema 与基础跨记录检查；默认 pytest 45 passed。
- 2.6a～2.6h 及部分前序课时由教师实现，不能作为学员独立编码成果陈述。

## 尚存边界

- Docker 隔离仍依赖本机守护进程和镜像供应链，部署环境需要单独审计。数据库初始化失败清理和并发保护尚未补齐。
- Trace 当前记录原始查询、代码和输出，仅用于本地受控数据；脱敏、权限和保留期未实现。
- `validate_trace` 目前只检查 Trace ID 一致和 Span ID 去重；父子时间、重试序号等通用语义校验待补。
- 搜索快照只说明当时检索结果，网页正文核验与回答证据链仍待后续阶段。

## 架构理解题

1. 为什么 MCP 调用成功不能直接判定 Python 程序成功？
2. 为什么一次重试必须生成新 Span，同时保留原 operation ID？
3. 为什么搜索快照与网页正文证据不是同一层？

下一阶段进入 LangGraph ReAct Agent，先做模型适配与 Harness 边界，再接现有 MCP 工具和 Trace。
