# MerchantLens Agent Eval Lab

面向商家经营分析场景的 Agent 与评测体系学习项目。项目从 Trace 和业务工具起步，逐步构建基于 LangGraph 的 Agent，以及覆盖结果、执行轨迹、成本和安全性的评测流水线。

> **当前状态：开发中。** 目前完成了 Trace 的基础数据结构、JSONL 读写、部分跨记录检查、模拟订单数据和 SQLite 初始化。Agent、MCP 工具服务及完整评测平台尚未实现。

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
| Agent 与评测平台 | 规划中；LangGraph 编排、MCP 接入、评测集与裁判均尚未实现 |

当前 Trace JSON 是本项目的自定义表示，参考 OpenTelemetry 的 Trace/Span 概念，**不是 OTLP 格式**。模拟数据和配置不代表真实线上运行。

## 目标架构

```text
商家经营分析任务
        │
        ▼
LangGraph ReAct Agent（规划中）
  ├─ 模型适配 / Harness / 短期记忆
  ├─ SQL / Python / 网页检索工具（计划通过 MCP 接入）
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
│   └── tracing/                   # 读写与基础跨记录校验
├── pyproject.toml
└── uv.lock
```

## 已知限制与后续计划

- 当前数据初始化程序面向单进程练习。导入失败可能遗留数据库文件，并发创建的原子保护尚未实现。
- 父子引用、重试语义、证据核验和工具快照回放尚未完整实现；JSONL 读取不等于完整回放。
- SQL 只读查询与 Python 容器执行已有基础实现；网页检索、MCP 与 LangGraph 仍在逐步建设。
- 阶段 5 计划产出首版小规模评测报告；后续再完善裁判校准、分层评测、安全门禁与数据飞轮。

完整课时和验收记录见[总计划](docs/plan.md)。

## 参考资料

- [美团《Agent 评测白皮书》](https://tech.meituan.com/2026/09/10/Agent-Evaluation-White-Paper-01.html)
- [阿里云 AgentLoop 评测实践](https://developer.aliyun.com/article/1758156)
- [PawBench](https://github.com/agentscope-ai/PawBench)
- [字节 Data Agent 三层评测](https://www.cnblogs.com/bytedata/p/19399354)
- [Anthropic：Demystifying evals for AI agents](https://www.anthropic.com/research/demystifying-evals-for-ai-agents)
- [OpenTelemetry Tracing API](https://opentelemetry.io/docs/specs/otel/trace/api/)
