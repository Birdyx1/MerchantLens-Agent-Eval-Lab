# 2.6h 真实 stdio 三工具集成验收

状态：已通过（教师实现与执行）。

[2.6 总览](lesson06.md) · [阶段复盘](review.md) · [总计划](../../plan.md)

## 知识点与架构

进程内 MCP 测试不能覆盖子进程环境、真实网络和 Docker socket。真实验收由客户端启动独立 stdio 服务，把数据库路径、Tavily Key、Python 开关及 Docker CLI 所需环境显式传入；三工具调用进入同一 Trace。密钥只进入子进程环境，不进入 MCP 工具参数或控制台输出。

## 实践产物

教师新增 `src/merchant_agent/mcp_live_smoke.py`。脚本创建临时 SQLite 数据库，读取本地 Key，启动 stdio MCP 服务，依次调用 SQL、真实 Tavily 搜索和真实 Docker Python 执行，再写父 Span、检查工具结果与 Trace 关联。运行命令：

```bash
PYTHONPATH=src .venv/bin/python -m merchant_agent.mcp_live_smoke
```

生成的 Trace 放在被 Git 忽略的 `runs/` 目录。该命令调用外部服务和本机 Docker，不纳入默认 pytest。

## 验收标准与结果

- 真实 stdio 子进程发现三个工具，并实际调用三者。
- SQL 返回 12000 分；Tavily 返回结构化结果列表；Docker Python 输出 `sandbox-ready`。
- 三次工具调用结果类别均为 `success`；与父 Span 组成四条记录，同一 Trace，Span ID 无重复。
- 四条记录通过当前 Span JSON Schema；默认 pytest 为 45 passed。
- 2026-11-01：真实验收通过，本地 Trace 路径记录在运行输出中，未提交仓库。

## 面试考点与踩坑

- 子进程环境与当前 shell 环境不同；Python 导入路径、Docker CLI 的 `PATH`/`HOME` 和 Key 都需明确配置。
- 实际调用检验部署链路，模拟调用检验稳定的功能分支，两者都需要。
- 当前本地 Trace 包含查询、代码及工具输出；生产使用前需补脱敏、访问控制和保留期策略。
