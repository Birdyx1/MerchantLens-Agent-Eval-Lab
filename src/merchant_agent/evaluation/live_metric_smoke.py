"""验证 Agent 能通过 MCP 调用新增的业务指标工具。

教师代写（2026-11-03）。只做工具可达性与工具选择 smoke，不作能力结论。
"""

import asyncio
import json
import tempfile
import uuid
from pathlib import Path

from merchant_agent.agent.deepseek_responses_model import DeepSeekResponsesModel
from merchant_agent.agent.state import initial_state
from merchant_agent.evaluation.base_admission_live import _config
from merchant_agent.evaluation.live_invoke import invoke_live_agent
from merchant_agent.tools.sql.init_orders_db import create_orders_db
from merchant_agent.tracing.reader import read_spans

ROOT = Path(__file__).resolve().parents[3]
QUESTIONS = [
    ("order_count", "请查询门店 A 的订单数。", "get_store_order_count"),
    ("refund_rate", "请查询门店 A 的退款率。", "get_store_refund_rate"),
    ("aov", "请查询门店 A 的客单价。", "get_store_aov"),
    ("paid_total", "请查询门店 A 的支付总额。", "get_store_paid_total"),
    ("refunded_total", "请查询门店 A 的退款总额。", "get_store_refunded_total"),
    ("refunded_order_count", "请查询门店 A 有多少笔订单发生了退款。",
     "get_store_refunded_order_count"),
]


async def main() -> list[dict]:
    """对每个指标问题各真实运行一次 Agent，记录工具选择与最终回答。"""
    key, model_name = _config()
    model = DeepSeekResponsesModel(model_name, key)
    results = []
    with tempfile.TemporaryDirectory() as directory:
        db_path = Path(directory) / "orders.sqlite"
        create_orders_db(str(ROOT / "fixtures/business_data/orders.csv"), str(db_path))
        trace_path = Path(directory) / "trace.jsonl"
        for label, question, expected_tool in QUESTIONS:
            state = initial_state(f"smoke_{label}", uuid.uuid4().hex,
                                  uuid.uuid4().hex[:16], question)
            result = await invoke_live_agent(state, db_path, trace_path,
                                             f"smoke-{label}", model=model)
            spans = read_spans(str(trace_path))
            tool_names = [span["name"] for span in spans if span["name"].startswith("tool.")]
            results.append({
                "label": label,
                "question": question,
                "expected_tool": expected_tool,
                "final_answer": result.get("final_answer"),
                "termination_reason": result.get("termination_reason"),
                "tools_called": tool_names,
                "expected_tool_called": f"tool.{expected_tool}" in tool_names,
            })
            trace_path.unlink(missing_ok=True)
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return results


if __name__ == "__main__":
    asyncio.run(main())
