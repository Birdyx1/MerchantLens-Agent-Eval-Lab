"""对 nl2sql 题做真实 Trial，记录结果集与评分（教师代写）。

draft 合成题，不入正式集合；结果只作结果导向评测的探索性观测。
"""

import asyncio
import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from merchant_agent.agent.deepseek_responses_model import DeepSeekResponsesModel
from merchant_agent.evaluation.base_admission_live import _config
from merchant_agent.evaluation.code_evaluator import evaluate_trial
from merchant_agent.evaluation.data_closure_live import _harness_fingerprint
from merchant_agent.evaluation.holdout import EvalDispatch
from merchant_agent.evaluation.live_invoke import invoke_live_agent
from merchant_agent.evaluation.pilot_repeated_live import _save
from merchant_agent.evaluation.task import load_eval_task
from merchant_agent.evaluation.trial import run_trial

ROOT = Path(__file__).resolve().parents[3]
TASK_DIR = ROOT / "fixtures" / "eval_task_nl2sql"
TIMEOUT_SECONDS = 120
MAX_STEPS = 10
MAX_TOTAL_TOKENS = 8192


async def main() -> Path:
    """逐题真实运行 nl2sql Agent，记录结果集与结果导向评分。"""
    paths = sorted(TASK_DIR.glob("*.json"))
    if not paths:
        raise ValueError("nl2sql 任务目录为空")
    manifest = []
    for path in paths:
        task = load_eval_task(path, project_root=ROOT)
        if task.label_status != "draft":
            raise ValueError("nl2sql 探针只接受 draft 题")
        manifest.append({"task_id": task.task_id,
                         "path": str(path.relative_to(ROOT)),
                         "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})

    key, model_name = _config()
    model = DeepSeekResponsesModel(model_name, key)
    probe_id = uuid.uuid4().hex
    directory = ROOT / "runs" / "nl2sql_probe" / probe_id
    directory.mkdir(parents=True, exist_ok=False, mode=0o700)
    output = directory / "results.json"
    record = {
        "status": "running",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "ended_at": None,
        "model_version": model_name,
        "harness_version": f"{_harness_fingerprint()}:budget:max{MAX_STEPS}/tok{MAX_TOTAL_TOKENS}",
        "note": "nl2sql 结果导向探针：draft 合成题，不入正式集合。",
        "manifest": manifest,
        "items": [],
    }
    _save(output, record)

    async def invoke(state, db_path, trace_path, thread_id):
        return await invoke_live_agent(state, db_path, trace_path, thread_id, model=model)

    try:
        for item in manifest:
            path = ROOT / item["path"]
            task = load_eval_task(path, project_root=ROOT)
            dispatch = EvalDispatch(
                agent_input=task.agent_input(),
                metadata={"traffic_type": "evaluation_probe", "split": "probe",
                          "task_id": task.task_id, "run_id": probe_id},
            )
            trial = await run_trial(path, project_root=ROOT, invoke=invoke,
                                    model_version=model_name,
                                    harness_version=record["harness_version"],
                                    timeout_seconds=TIMEOUT_SECONDS, dispatch=dispatch,
                                    max_steps=MAX_STEPS, max_total_tokens=MAX_TOTAL_TOKENS)
            score = evaluate_trial(trial, path, project_root=ROOT)
            record["items"].append({
                "task_id": item["task_id"],
                "trial_id": trial["trial_id"],
                "trial_status": trial["status"],
                "termination_reason": trial["termination_reason"],
                "final_answer": trial["final_answer"],
                "code_score": score,
            })
            _save(output, record)
        record["status"] = "completed"
    except BaseException as exc:
        record["status"] = "failed"
        record["error_type"] = type(exc).__name__
        raise
    finally:
        record["ended_at"] = datetime.now(timezone.utc).isoformat()
        _save(output, record)
    return output


if __name__ == "__main__":
    print(f"nl2sql 记录：{asyncio.run(main())}")
