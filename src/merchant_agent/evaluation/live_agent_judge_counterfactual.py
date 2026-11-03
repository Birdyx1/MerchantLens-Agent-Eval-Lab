"""人工构造的错误金额轨迹：检验真实 Agent 裁判能否独立复算并拒绝。"""

import asyncio
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from merchant_agent.agent.siliconflow_chat_model import SiliconFlowChatModel
from merchant_agent.evaluation.agent_judge import judge_with_evidence
from merchant_agent.evaluation.code_evaluator import evaluate_trial
from merchant_agent.evaluation.live_siliconflow_panel_challenges import _config
from merchant_agent.evaluation.pilot_repeated_live import _save


ROOT = Path(__file__).resolve().parents[3]
TASK_PATH = ROOT / "fixtures/eval_task_examples/store_net_a.json"
FALSE_AMOUNT_FEN = 13000


def _prepare_case() -> tuple[Path, dict, dict]:
    """生成格式有效但业务金额错误的受控轨迹，随后真实运行 Code 裁判。"""
    run_id = uuid.uuid4().hex
    directory = ROOT / "runs/trials" / run_id
    directory.mkdir(parents=True, exist_ok=False, mode=0o700)
    task_bytes = TASK_PATH.read_bytes()
    task = json.loads(task_bytes)
    fixture_path = ROOT / task["environment"]["fixture_path"]
    trace_id = uuid.uuid4().hex
    root_span = uuid.uuid4().hex[:16]
    tool_span = uuid.uuid4().hex[:16]
    now = datetime.now(timezone.utc).isoformat()
    spans = [
        {"trace_id": trace_id, "span_id": tool_span, "parent_span_id": root_span,
         "name": "tool.get_store_net", "start_time": now, "end_time": now,
         "attributes": {"store_id": "A", "result_fen": FALSE_AMOUNT_FEN,
                        "outcome": "success", "simulated": True}},
        {"trace_id": trace_id, "span_id": root_span, "parent_span_id": None,
         "name": "agent.request", "start_time": now, "end_time": now,
         "attributes": {"task_id": task["task_id"], "termination_reason": "completed",
                        "simulated": True}},
    ]
    trace_path = directory / "trace.jsonl"
    raw_trace = ("\n".join(json.dumps(span, ensure_ascii=False) for span in spans) + "\n").encode()
    fd = os.open(trace_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as output:
        output.write(raw_trace)
    trial = {"trial_id": run_id, "task_id": task["task_id"], "status": "completed",
             "termination_reason": "completed", "final_answer": f"门店 A 的净收入为 {FALSE_AMOUNT_FEN} 分。",
             "task_sha256": hashlib.sha256(task_bytes).hexdigest(),
             "fixture_sha256": hashlib.sha256(fixture_path.read_bytes()).hexdigest(),
             "trace_id": trace_id, "trace_path": str(trace_path.relative_to(ROOT)),
             "trace_sha256": hashlib.sha256(raw_trace).hexdigest(),
             "provenance": "人工构造的反事实控制样本，非被测 Agent 产出"}
    _save(directory / "trial.json", trial)
    code_score = evaluate_trial(trial, TASK_PATH, project_root=ROOT)
    if not code_score["trace_valid"] or code_score["passed"]:
        raise ValueError("受控错误轨迹未通过格式校验或未被 Code 裁判拒绝")
    return directory, trial, code_score


async def main() -> Path:
    """只把合成 Trace 发给 GLM；评测侧按本地冻结订单独立复算。"""
    directory, trial, code_score = _prepare_case()
    key, models = _config()
    target = directory / "agent_judge_counterfactual.json"
    record = {"status": "running", "started_at": datetime.now(timezone.utc).isoformat(),
              "task_id": trial["task_id"], "trial_id": trial["trial_id"],
              "trial_sha256": hashlib.sha256((directory / "trial.json").read_bytes()).hexdigest(),
              "trace_sha256": trial["trace_sha256"], "code_score": code_score,
              "judge_model_config": models[0], "provenance": trial["provenance"],
              "holdout_used": False, "judge_result": None}
    _save(target, record)
    try:
        record["judge_result"] = await judge_with_evidence(
            trial, code_score, TASK_PATH, project_root=ROOT,
            model=SiliconFlowChatModel(models[0], key))
        record["status"] = "completed"
    except BaseException as exc:
        record["status"] = "failed"
        record["error_type"] = type(exc).__name__
        record["error_detail"] = str(exc) if isinstance(exc, ValueError) else None
        raise
    finally:
        record["ended_at"] = datetime.now(timezone.utc).isoformat()
        _save(target, record)
    return target


if __name__ == "__main__":
    print(f"受控错误轨迹裁判记录：{asyncio.run(main())}")
