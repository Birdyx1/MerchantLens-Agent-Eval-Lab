# MerchantLens Agent Eval Lab

面向商家经营分析场景的 Agent 与评测体系学习项目。项目从 Trace 和业务工具起步，逐步构建基于 LangGraph 的 Agent，以及覆盖结果、执行轨迹、成本和安全性的评测流水线。

> **当前状态：开发中。** Trace 基础、业务工具、官方 SDK 的 MCP stdio 服务与 LangGraph Agent 已完成项目范围内验收；评测平台仍在建设。

## 为什么做这个项目

仅检查 Agent 的最终答案，难以判断它是否使用了正确数据、是否调用了合适的工具，以及结果是否依赖可信证据。本项目围绕商家经营分析任务，逐步建立可追踪、可对比和可复盘的评测能力。

例如：门店净支付金额 = 已支付金额 − 已退款金额。项目使用模拟订单，明确计算口径，再逐步实现 SQL 工具、分析 Agent 和相应的评测任务。

## 当前进度

| 模块 | 当前状态 |
| --- | --- |
| Trace 数据 | 已有模拟 Span、重试样例和单条 Span JSON Schema |
| Trace 读写 | 已实现 JSONL 追加写入和逐行读取 |
| 跨记录检查 | 已实现同一 Trace 的 `trace_id` 一致性与 `span_id` 去重检查 |
| 版本清单 | 已有模拟运行清单，记录模型、Harness、工具和数据快照 |
| 业务数据 | 已有模拟订单、净支付金额口径及 SQLite 初始化程序 |
| MCP 工具服务 | 已接入 SQL、Tavily 搜索和受限 Python 执行；工具按服务端环境配置暴露 |
| Agent 与评测平台 | LangGraph 编排、评测集与裁判尚未实现 |

当前 Trace JSON 是本项目的自定义表示，参考 OpenTelemetry 的 Trace/Span 概念，**不是 OTLP 格式**。模拟数据和配置不代表真实线上运行。

## 目标架构

```text
商家经营分析任务
        │
        ▼
LangGraph ReAct Agent（规划中）
  ├─ 模型适配 / Harness / 短期记忆
  ├─ SQL / Python / 网页检索工具（MCP stdio 已接入）
  └─ 结构化 Trace 与运行清单
        │
        ▼
Python 评测流水线（规划中）
  ├─ 基座 / 组件 / 端到端评测
  ├─ Code / LLM / Agent 裁判及人工校准
  ├─ 结果 / 轨迹 / 成本 / 安全指标
  └─ 版本对比 / 失败归因 / 回归门禁
```

评测资产计划物理隔离为 Golden、Regression、Badcase 和 Negative 四类；同时引入 Holdout、标注一致性检查和安全红线。多裁判、Agent 裁判和标注工作台安排为后续扩展，详见[学习总计划](docs/plan.md)。

## 环境与快速体验

项目声明要求 **Python 3.13 或更高版本**。以下示例只使用标准库，并在临时目录写入数据，不需要模型 API Key。

在项目根目录执行：

```bash
PYTHONPATH=src python3 - <<'PY'
import json
import sqlite3
import tempfile
from pathlib import Path

from merchant_agent.tools.sql.init_orders_db import create_orders_db
from merchant_agent.tracing.reader import read_spans
from merchant_agent.tracing.validator import validate_trace
from merchant_agent.tracing.writer import append_span

spans = json.loads(Path("fixtures/traces/retry.json").read_text(encoding="utf-8"))

with tempfile.TemporaryDirectory() as directory:
    trace_path = Path(directory) / "trace.jsonl"
    for span in spans:
        append_span(str(trace_path), span)

    restored = read_spans(str(trace_path))
    print("Span 数量:", len(restored))
    print("Trace 检查结果:", validate_trace(restored))

    db_path = Path(directory) / "orders.db"
    create_orders_db("fixtures/business_data/orders.csv", str(db_path))
    with sqlite3.connect(db_path) as connection:
        net_fen = connection.execute(
            "SELECT SUM(paid_fen - refunded_fen) FROM orders WHERE store_id = ?",
            ("A",),
        ).fetchone()[0]
    print("门店 A 净支付金额（分）:", net_fen)
PY
```

预期输出：

```text
Span 数量: 3
Trace 检查结果: []
门店 A 净支付金额（分）: 12000
```

`validate_trace` 当前只检查两项：Trace ID 是否一致，以及 Span ID 是否重复。空列表不表示所有轨迹语义均已通过。

## MCP stdio 配置

服务入口为 `merchant_agent.mcp_stdio`，由 MCP 客户端以 `python -m` 启动。客户端须向子进程显式传入以下环境变量；不要把密钥放入工具参数或提交到仓库。

| 变量 | 用途 |
| --- | --- |
| `PYTHONPATH` | 指向本项目 `src` 的绝对路径 |
| `MERCHANT_DB_PATH` | 必填，SQLite 数据库路径 |
| `TAVILY_API_KEY` | 非空时注册 `search_web`；缺省时不注册 |
| `MERCHANT_ENABLE_PYTHON` | `0`（默认）或 `1`；`1` 时注册 `execute_python`，要求本机 Docker 可用 |

`get_store_net` 始终注册。`MERCHANT_ENABLE_PYTHON` 的其他值会使服务在启动前报错。默认测试运行 `.venv/bin/python -m pytest -q`；它使用模拟搜索与 Python 执行器，不产生真实 Tavily 请求或 Docker 容器。

真实三工具 stdio 验收运行 `PYTHONPATH=src .venv/bin/python -m merchant_agent.mcp_live_smoke`，需要本地 Tavily Key、Docker 和 `python:3.13-alpine` 镜像。该命令会实际调用 Tavily 与 Docker，Trace 写入 Git 忽略的 `runs/`。2026-11-01 的验收结果为 SQL、搜索、Python 三次调用均成功，四条 Span 通过当前 Schema；详情见[阶段 2 复盘](docs/lessons/stage02/review.md)。

真实模型可使用 `DeepSeekResponsesModel`，从本地 `.env` 读取 `DEEPSEEK_API_KEY` 与 `DEEPSEEK_MODEL`；参考 `.env.example`。`.env` 不会自动加载，调用入口须显式读取配置。2026-11-02 使用 `deepseek-flash` 完成真实模型与 MCP SQL 端到端烟雾测试；详见[阶段 3 复盘](docs/lessons/stage03/review.md)。

## 项目结构

```text
├── docs/
│   ├── contracts/                 # 业务口径
│   ├── lessons/                   # 分阶段课时、任务与评审记录
│   └── plan.md                    # 总计划与进度
├── fixtures/
│   ├── business_data/orders.csv   # 虚构订单数据
│   └── traces/                    # 模拟 Trace 与运行清单
├── schemas/span.schema.json       # 单条 Span 结构约束
├── src/merchant_agent/
│   ├── tools/
│   │   ├── python_sandbox/        # Python 容器执行与恢复
│   │   ├── sql/                   # SQLite 数据初始化与查询
│   │   └── search/                # 搜索结果、接口与模拟服务
│   ├── tracing/                   # 读写与基础跨记录校验
│   ├── mcp_server.py              # 工具注册
│   ├── mcp_stdio.py               # stdio 服务入口
│   ├── mcp_live_smoke.py          # 真实三工具跨进程验收
│   └── mcp_stdio_smoke.py         # 跨进程验收辅助
├── pyproject.toml
└── uv.lock
```

## 已知限制与后续计划

- 当前数据初始化程序面向单进程练习。导入失败可能遗留数据库文件，并发创建的原子保护尚未实现。
- 父子引用、重试语义、证据核验和工具快照回放尚未完整实现；JSONL 读取不等于完整回放。
- SQL、Python 容器执行与 Tavily 搜索已有基础实现，三工具真实 stdio 调用已通过。部署级隔离审计、Trace 脱敏及完整轨迹语义校验仍待实现。
- 阶段 5 计划产出首版小规模评测报告；后续再完善裁判校准、分层评测、安全门禁与数据飞轮。

完整课时和验收记录见[总计划](docs/plan.md)。

## 参考资料

- [美团《Agent 评测白皮书》](https://tech.meituan.com/2026/09/10/Agent-Evaluation-White-Paper-01.html)
- [阿里云 AgentLoop 评测实践](https://developer.aliyun.com/article/1758156)
- [PawBench](https://github.com/agentscope-ai/PawBench)
- [字节 Data Agent 三层评测](https://www.cnblogs.com/bytedata/p/19399354)
- [Anthropic：Demystifying evals for AI agents](https://www.anthropic.com/research/demystifying-evals-for-ai-agents)
- [OpenTelemetry Tracing API](https://opentelemetry.io/docs/specs/otel/trace/api/)
