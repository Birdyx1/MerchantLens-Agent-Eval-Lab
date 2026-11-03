"""对首条已仲裁 Golden 题执行一次真实模型闭环试跑。"""

import asyncio
import hashlib
import json
import os
import sys
import uuid
from pathlib import Path

from merchant_agent.agent.deepseek_responses_model import DeepSeekResponsesModel
from merchant_agent.evaluation.base_admission_live import _config
from merchant_agent.evaluation.code_evaluator import evaluate_trial
from merchant_agent.evaluation.live_invoke import invoke_live_agent
from merchant_agent.evaluation.metrics import trial_metrics
from merchant_agent.evaluation.trajectory_evaluator import evaluate_trial_trajectory
from merchant_agent.evaluation.trial import run_trial


ROOT = Path(__file__).resolve().parents[3]
TASKS = {
    "d": ROOT / "eval_sets/golden/tasks/pilot_store_net_d_001.json",
    "e": ROOT / "eval_sets/regression/tasks/pilot_store_net_e_001.json",
    "f": ROOT / "eval_sets/golden/tasks/pilot_store_net_f_001.json",
    "g": ROOT / "eval_sets/regression/tasks/pilot_store_net_g_001.json",
}


def _harness_fingerprint() -> str:
    """记录本次 Agent、工具和评测核心源码摘要，避免脏工作区只写模糊版本名。"""
    paths = sorted((ROOT / "src/merchant_agent/agent").glob("*.py"))
    paths += sorted((ROOT / "src/merchant_agent/tracing").glob("*.py"))
    paths += sorted((ROOT / "src/merchant_agent/tools/sql").glob("*.py"))
    digest = hashlib.sha256()
    for path in paths:
        digest.update(str(path.relative_to(ROOT)).encode("utf-8"))
        digest.update(path.read_bytes())
    return f"source-sha256:{digest.hexdigest()}"


async def main(task_key: str = "d") -> Path:
    """只打印私有摘要路径；密钥和完整模型回复保留在本地记录。"""
    key, model_name = _config()
    if task_key not in TASKS:
        raise ValueError("仅允许运行已完成仲裁和入库的试点题")
    task_path = TASKS[task_key]
    model = DeepSeekResponsesModel(model_name, key)

    async def invoke(state, db_path, trace_path, thread_id):
        return await invoke_live_agent(state, db_path, trace_path, thread_id, model=model)

    trial = await run_trial(task_path, project_root=ROOT, invoke=invoke,
                            model_version=model_name, harness_version=_harness_fingerprint(),
                            timeout_seconds=90)
    score = evaluate_trial(trial, task_path, project_root=ROOT)
    trajectory = evaluate_trial_trajectory(trial, task_path, project_root=ROOT)
    metrics = trial_metrics(trial, score, project_root=ROOT)
    summary = {
        "task_id": trial["task_id"], "trial_id": trial["trial_id"],
        "task_sha256": trial["task_sha256"], "fixture_sha256": trial["fixture_sha256"],
        "model_version": trial["model_version"], "harness_version": trial["harness_version"],
        "trial_status": trial["status"], "trace_sha256": trial["trace_sha256"],
        "code_score": score, "trajectory": trajectory, "metrics": metrics,
    }
    directory = ROOT / "runs/data_closure"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    destination = directory / f"{uuid.uuid4().hex}.json"
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as output:
        json.dump(summary, output, ensure_ascii=False, indent=2)
        output.write("\n")
        output.flush()
        os.fsync(output.fileno())
    return destination


if __name__ == "__main__":
    print(f"闭环记录：{asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else 'd'))}")
