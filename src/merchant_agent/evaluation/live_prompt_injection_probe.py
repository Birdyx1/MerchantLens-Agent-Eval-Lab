"""对提示注入候选真实运行 Agent，执行 8.2 硬约束裁判（教师代写）。

只做确定性硬约束（Trace、禁止工具、系统提示关键词泄露、有回答）；注入是否真被忽略仍需语义复核。
"""

import asyncio
import json
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from merchant_agent.agent.deepseek_responses_model import DeepSeekResponsesModel
from merchant_agent.agent.state import initial_state
from merchant_agent.evaluation.base_admission_live import _config
from merchant_agent.evaluation.live_invoke import invoke_live_agent
from merchant_agent.evaluation.prompt_injection import PromptInjectionCase, assess_prompt_injection
from merchant_agent.tools.sql.init_orders_db import create_orders_db
from merchant_agent.tracing.reader import read_spans

ROOT = Path(__file__).resolve().parents[3]
CASES = ROOT / "fixtures/prompt_injection_candidates.json"
MAX_STEPS = 8
MAX_TOTAL_TOKENS = 4096


async def main() -> Path:
    """逐条真实运行注入输入，记录硬约束结果、最终回答与 Trace。"""
    cases = [
        PromptInjectionCase(
            case_id=item["case_id"], attack_type=item["attack_type"],
            user_request=item["user_request"], expected_behavior=item["expected_behavior"],
            forbidden_tools=tuple(item["forbidden_tools"]),
            forbidden_output_markers=tuple(item["forbidden_output_markers"]),
        )
        for item in json.loads(CASES.read_text(encoding="utf-8"))
    ]
    key, model_name = _config()
    model = DeepSeekResponsesModel(model_name, key)
    probe_id = uuid.uuid4().hex
    output_dir = ROOT / "runs" / "prompt_injection_probe" / probe_id
    output_dir.mkdir(parents=True, exist_ok=False, mode=0o700)
    output = output_dir / "results.json"
    record = {"status": "running", "created_at": datetime.now(timezone.utc).isoformat(),
              "ended_at": None, "model_version": model_name, "items": []}
    output.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

    with tempfile.TemporaryDirectory() as directory:
        db_path = Path(directory) / "orders.sqlite"
        create_orders_db(str(ROOT / "fixtures/business_data/orders.csv"), str(db_path))
        for case in cases:
            trace_path = output_dir / f"{case.case_id}.jsonl"
            state = initial_state(f"inj_{case.case_id}", uuid.uuid4().hex,
                                  uuid.uuid4().hex[:16], case.user_request,
                                  max_steps=MAX_STEPS, max_total_tokens=MAX_TOTAL_TOKENS)
            try:
                result = await invoke_live_agent(state, db_path, trace_path,
                                                 f"inj-{case.case_id}", model=model)
                spans = read_spans(str(trace_path))
                tool_names = [span["name"].removeprefix("tool.") for span in spans
                              if span["name"].startswith("tool.")]
                trace_valid = bool(spans) and all(span.get("trace_id") == state["trace_id"]
                                                  for span in spans)
                assessment = assess_prompt_injection(
                    case, final_answer=result.get("final_answer"),
                    tool_names=tool_names, trace_valid=trace_valid,
                )
                record["items"].append({
                    **assessment,
                    "final_answer": result.get("final_answer"),
                    "tool_names": tool_names,
                    "termination_reason": result.get("termination_reason"),
                })
            except Exception as exc:
                record["items"].append({
                    "case_id": case.case_id,
                    "attack_type": case.attack_type,
                    "expected_behavior": case.expected_behavior,
                    "hard_constraints_passed": False,
                    "overall_verdict": "error",
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:200],
                })
            output.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    record["status"] = "completed"
    record["ended_at"] = datetime.now(timezone.utc).isoformat()
    output.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(record["items"], ensure_ascii=False, indent=2))
    return output


if __name__ == "__main__":
    print(f"提示注入记录：{asyncio.run(main())}")
