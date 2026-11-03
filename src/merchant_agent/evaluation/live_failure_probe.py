"""对合成难例边界题做一次真实失败探针：运行 DeepSeek 并用 Code 与 LLM 裁判打分。

教师代写（2026-11-03）。这些难例是 label_status=draft 的合成探测题，
未经过双标共识，不入 Golden/Regression；失败为模型自然产生，非故障注入。
"""

import asyncio
import hashlib
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from merchant_agent.agent.deepseek_responses_model import DeepSeekResponsesModel
from merchant_agent.evaluation.base_admission_live import _config
from merchant_agent.evaluation.code_evaluator import evaluate_trial
from merchant_agent.evaluation.data_closure_live import _harness_fingerprint
from merchant_agent.evaluation.holdout import EvalDispatch
from merchant_agent.evaluation.live_invoke import invoke_live_agent
from merchant_agent.evaluation.llm_judge import RUBRIC_PATH, judge_answer_clarity
from merchant_agent.evaluation.pilot_repeated_live import _save
from merchant_agent.evaluation.task import load_eval_task
from merchant_agent.evaluation.trial import run_trial

ROOT = Path(__file__).resolve().parents[3]
TASK_DIR = ROOT / "fixtures" / "eval_task_trap"
TIMEOUT_SECONDS = 90


async def main(patterns: tuple[str, ...] = ("*.json",)) -> Path:
    """冻结难例清单后逐题真实运行并评分；结果只作区分度探针，不作能力结论。"""
    paths = sorted({path for pattern in patterns for path in TASK_DIR.glob(pattern)})
    if not paths:
        raise ValueError("难例任务目录为空")
    manifest = []
    for path in paths:
        task = load_eval_task(path, project_root=ROOT)
        if task.label_status != "draft":
            raise ValueError("失败探针只接受未入库的 draft 难例")
        manifest.append({"task_id": task.task_id,
                         "path": str(path.relative_to(ROOT)),
                         "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})

    key, model_name = _config()
    model = DeepSeekResponsesModel(model_name, key)
    probe_id = uuid.uuid4().hex

    directory = ROOT / "runs" / "failure_probe" / probe_id
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
        "evaluator_sha256": {
            "code_evaluator": hashlib.sha256(
                (ROOT / "src/merchant_agent/evaluation/code_evaluator.py").read_bytes()).hexdigest(),
            "llm_judge": hashlib.sha256(
                (ROOT / "src/merchant_agent/evaluation/llm_judge.py").read_bytes()).hexdigest(),
        },
        "note": "合成难例探测：label_status=draft，未双标共识，不入 Golden/Regression；"
                "失败为模型自然产生，非故障注入，也不代表稳定能力。",
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
            task = load_eval_task(path, project_root=ROOT)
            dispatch = EvalDispatch(
                agent_input=task.agent_input(),
                metadata={"traffic_type": "evaluation_probe", "split": "probe",
                          "task_id": task.task_id, "run_id": probe_id},
            )
            trial = await run_trial(path, project_root=ROOT, invoke=invoke,
                                    model_version=model_name,
                                    harness_version=record["harness_version"],
                                    timeout_seconds=TIMEOUT_SECONDS, dispatch=dispatch)
            code_score = evaluate_trial(trial, path, project_root=ROOT)
            judge = await judge_answer_clarity(trial, code_score, project_root=ROOT, model=model)
            record["items"].append({
                "task_id": item["task_id"],
                "trial_id": trial["trial_id"],
                "trial_status": trial["status"],
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
    patterns = tuple(sys.argv[1:]) or ("*.json",)
    print(f"失败探针记录：{asyncio.run(main(patterns))}")
