"""验证 Agent 能用 run_sql 回答多维经营问题（真实 smoke）。

教师代写（2026-11-03）。只做能力可达性 smoke，不作稳定能力结论。
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
    ("category_net", "请用 SQL 统计饮品品类的净收入合计（分）。"),
    ("channel_refund_rate", "请用 SQL 找出退款率最高的渠道，并给出该渠道的退款率。"),
    ("date_filter", "请用 SQL 统计 2026-10-15 当天的订单数。"),
]


async def main() -> list[dict]:
    """对每个问题真实运行一次 Agent，记录工具选择与最终回答。"""
    key, model_name = _config()
    model = DeepSeekResponsesModel(model_name, key)
    results = []
    with tempfile.TemporaryDirectory() as directory:
        db_path = Path(directory) / "orders.sqlite"
        create_orders_db(str(ROOT / "fixtures/business_data/analytics_orders.csv"), str(db_path))
        trace_path = Path(directory) / "trace.jsonl"
        for label, question in QUESTIONS:
            state = initial_state(f"smoke_{label}", uuid.uuid4().hex,
                                  uuid.uuid4().hex[:16], question,
                                  max_steps=10, max_total_tokens=8192)
            result = await invoke_live_agent(state, db_path, trace_path,
                                             f"smoke-{label}", model=model)
            spans = read_spans(str(trace_path))
            tool_names = [span["name"] for span in spans if span["name"].startswith("tool.")]
            results.append({
                "label": label,
                "question": question,
                "final_answer": result.get("final_answer"),
                "termination_reason": result.get("termination_reason"),
                "tools_called": tool_names,
            })
            trace_path.unlink(missing_ok=True)
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return results


if __name__ == "__main__":
    asyncio.run(main())
