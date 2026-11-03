"""对多步合计题重复真实运行，估计失败率并产生 Judge 0/1/2 分样本。

教师代写（2026-11-03）。题目为 label_status=draft 的合成探测题，不入正式集合；
结果只作失败率与裁判区分度的探索性观测，不作稳定能力结论。
"""

import asyncio
import hashlib
import json
import sys
import uuid
from collections import Counter
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
DEFAULT_REPEATS = 2


def _failure_modes(code_score: dict) -> list[str]:
    """返回失败判据的 check_key；全部通过时为空。"""
    return [item["check_key"] for item in code_score["criteria"] if not item["passed"]]


async def main(repeats: int = DEFAULT_REPEATS) -> Path:
    """每道合计题重复运行 repeats 次；同样落盘每次 Trial 的评分与裁判分。"""
    if type(repeats) is not int or repeats < 1:
        raise ValueError("重复次数必须是正整数")
    paths = sorted(TASK_DIR.glob("trap_store_net_sum_*.json"))
    if not paths:
        raise ValueError("没有合计题型探测题")
    manifest = []
    for path in paths:
        task = load_eval_task(path, project_root=ROOT)
        if task.label_status != "draft":
            raise ValueError("重复探针只接受 draft 探测题")
        manifest.append({"task_id": task.task_id,
                         "path": str(path.relative_to(ROOT)),
                         "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})

    key, model_name = _config()
    model = DeepSeekResponsesModel(model_name, key)
    probe_id = uuid.uuid4().hex
    directory = ROOT / "runs" / "sum_repeat_probe" / probe_id
    directory.mkdir(parents=True, exist_ok=False, mode=0o700)
    output = directory / "results.json"
    record = {
        "status": "running",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "ended_at": None,
        "repeats": repeats,
        "model_version": model_name,
        "harness_version": _harness_fingerprint(),
        "judge_rubric_sha256": hashlib.sha256((ROOT / RUBRIC_PATH).read_bytes()).hexdigest(),
        "evaluator_sha256": hashlib.sha256(
            (ROOT / "src/merchant_agent/evaluation/code_evaluator.py").read_bytes()).hexdigest(),
        "note": "合成多步探测重复运行：draft 未双标，不入正式集合；只作失败率与裁判区分度探索。",
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
            for repeat_index in range(repeats):
                if hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
                    raise ValueError("运行中 Task 快照变化")
                trial = await run_trial(path, project_root=ROOT, invoke=invoke,
                                        model_version=model_name,
                                        harness_version=record["harness_version"],
                                        timeout_seconds=TIMEOUT_SECONDS, dispatch=dispatch)
                code_score = evaluate_trial(trial, path, project_root=ROOT)
                judge = await judge_answer_clarity(trial, code_score, project_root=ROOT, model=model)
                record["items"].append({
                    "task_id": item["task_id"],
                    "repeat_index": repeat_index,
                    "trial_id": trial["trial_id"],
                    "trial_status": trial["status"],
                    "final_answer": trial["final_answer"],
                    "code_passed": code_score["passed"],
                    "answer_amount_fen": code_score["answer_amount_fen"],
                    "failure_modes": _failure_modes(code_score),
                    "judge_score": judge.get("score"),
                    "judge_reason": judge.get("reason"),
                })
                _save(output, record)
        record["aggregate"] = _aggregate(record["items"])
        record["status"] = "completed"
    except BaseException as exc:
        record["status"] = "failed"
        record["error_type"] = type(exc).__name__
        raise
    finally:
        record["ended_at"] = datetime.now(timezone.utc).isoformat()
        _save(output, record)
    return output


def _aggregate(items: list[dict]) -> dict:
    """汇总成功率，明确区分运行故障与模型失败，避免把网络错误算作能力失败。"""
    total = len(items)
    completed = [item for item in items if item["trial_status"] == "completed"]
    errors = [item for item in items if item["trial_status"] != "completed"]
    passed = sum(1 for item in completed if item["code_passed"])
    by_task: dict[str, dict] = {}
    for item in items:
        bucket = by_task.setdefault(item["task_id"], {"trials": 0, "completed": 0, "errors": 0, "passed": 0})
        bucket["trials"] += 1
        if item["trial_status"] == "completed":
            bucket["completed"] += 1
            bucket["passed"] += 1 if item["code_passed"] else 0
        else:
            bucket["errors"] += 1
    failure_modes = Counter(mode for item in completed for mode in item["failure_modes"])
    judge_distribution = Counter(item["judge_score"] for item in completed)
    return {
        "trials": total,
        "completed": len(completed),
        "errors": len(errors),
        "passed": passed,
        "model_failures": len(completed) - passed,
        "pass_rate_completed": passed / len(completed) if completed else None,
        "error_rate": len(errors) / total if total else None,
        "by_task": by_task,
        "failure_modes": dict(failure_modes),
        "judge_distribution": {str(k): v for k, v in sorted(
            judge_distribution.items(), key=lambda kv: (kv[0] is None, kv[0]))},
        "failed_trial_ids": [item["trial_id"] for item in completed if not item["code_passed"]],
        "error_trial_ids": [item["trial_id"] for item in errors],
    }


if __name__ == "__main__":
    repeats = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_REPEATS
    print(f"重复探针记录：{asyncio.run(main(repeats))}")
