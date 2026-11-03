"""对封存 Holdout 做首次真实运行：只运行一次、只读、不参与开发调参。

教师代写（2026-11-03）。Holdout 位于常规集合之外，由 prepare_eval_dispatch
识别为 split=holdout；本次运行后该 Holdout 即被"使用"，不再视为未见数据。
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
from merchant_agent.evaluation.live_invoke import invoke_live_agent
from merchant_agent.evaluation.llm_judge import RUBRIC_PATH, judge_answer_clarity
from merchant_agent.evaluation.pilot_repeated_live import _save
from merchant_agent.evaluation.task import load_eval_task
from merchant_agent.evaluation.trial import run_trial

ROOT = Path(__file__).resolve().parents[3]
HOLDOUT_TASKS = ROOT / "holdout" / "tasks"
TIMEOUT_SECONDS = 90


async def main() -> Path:
    """逐题真实运行封存 Holdout 并评分；结果只作首次观测证据。"""
    paths = sorted(HOLDOUT_TASKS.glob("*.json"))
    if not paths:
        raise ValueError("Holdout 目录为空")
    manifest = []
    for path in paths:
        task = load_eval_task(path, project_root=ROOT)
        if task.label_status != "adjudicated":
            raise ValueError("Holdout 只接受已仲裁题目")
        manifest.append({"task_id": task.task_id,
                         "path": str(path.relative_to(ROOT)),
                         "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})

    key, model_name = _config()
    model = DeepSeekResponsesModel(model_name, key)
    probe_id = uuid.uuid4().hex

    directory = ROOT / "runs" / "holdout_runs" / probe_id
    directory.mkdir(parents=True, exist_ok=False, mode=0o700)
    output = directory / "results.json"
    record = {
        "status": "running",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "ended_at": None,
        "model_version": model_name,
        "harness_version": _harness_fingerprint(),
        "rubric_sha256": hashlib.sha256((ROOT / "rubrics/store_net_v1.json").read_bytes()).hexdigest(),
        "judge_rubric_sha256": hashlib.sha256((ROOT / RUBRIC_PATH).read_bytes()).hexdigest(),
        "note": "封存 Holdout 的首次真实运行；运行后该 Holdout 即被使用，不再视为未见数据。",
        "manifest": manifest,
        "items": [],
    }
    _save(output, record)

    async def invoke(state, db_path, trace_path, thread_id):
        return await invoke_live_agent(state, db_path, trace_path, thread_id, model=model)

    try:
        for item in manifest:
            path = ROOT / item["path"]
            if hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
                raise ValueError("运行中 Task 快照变化")
            trial = await run_trial(path, project_root=ROOT, invoke=invoke,
                                    model_version=model_name,
                                    harness_version=record["harness_version"],
                                    timeout_seconds=TIMEOUT_SECONDS)
            code_score = evaluate_trial(trial, path, project_root=ROOT)
            judge = await judge_answer_clarity(trial, code_score, project_root=ROOT, model=model)
            record["items"].append({
                "task_id": item["task_id"],
                "trial_id": trial["trial_id"],
                "trial_status": trial["status"],
                "traffic": trial["traffic"],
                "termination_reason": trial["termination_reason"],
                "final_answer": trial["final_answer"],
                "code_score": code_score,
                "judge": judge,
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
    print(f"Holdout 记录：{asyncio.run(main())}")
