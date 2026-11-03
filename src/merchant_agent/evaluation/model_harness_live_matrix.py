"""在同题同轮上交错运行 DeepSeek/GLM × 两版 Harness 的真实四格试点。"""

import asyncio
import hashlib
import random
import uuid
from datetime import datetime, timezone
from pathlib import Path

from merchant_agent.agent.deepseek_responses_model import DeepSeekResponsesModel
from merchant_agent.agent.siliconflow_chat_model import SiliconFlowChatModel
from merchant_agent.evaluation.base_admission_live import _config as deepseek_config
from merchant_agent.evaluation.batch import _save as save_batch
from merchant_agent.evaluation.code_evaluator import evaluate_trial
from merchant_agent.evaluation.data_closure_live import _harness_fingerprint
from merchant_agent.evaluation.live_invoke import invoke_live_agent
from merchant_agent.evaluation.live_siliconflow_panel_challenges import _config as siliconflow_config
from merchant_agent.evaluation.metrics import aggregate_metrics, trial_metrics
from merchant_agent.evaluation.model_harness_matrix import compare_model_harness_matrix
from merchant_agent.evaluation.pilot_repeated_live import _save
from merchant_agent.evaluation.prompt_harness_experiment import PROMPTS
from merchant_agent.evaluation.sets import EvalCollection
from merchant_agent.evaluation.task import load_eval_task
from merchant_agent.evaluation.trial import run_trial
from merchant_agent.evaluation.uncertainty import summarize_repeats


ROOT = Path(__file__).resolve().parents[3]
COLLECTION = EvalCollection.REGRESSION
REPEATS = 2
SEED = 20261103
ARMS = ("baseline", "explicit_json_after_tool")


async def main() -> Path:
    """预先冻结四格和调度顺序；每个题目/轮次内随机排列四个单元。"""
    deepseek_key, deepseek_name = deepseek_config()
    siliconflow_key, siliconflow_names = siliconflow_config()
    glm_name = siliconflow_names[0]
    models = {
        "deepseek": DeepSeekResponsesModel(deepseek_name, deepseek_key),
        "glm": SiliconFlowChatModel(glm_name, siliconflow_key, json_mode=True),
    }
    model_names = {"deepseek": deepseek_name, "glm": glm_name}
    if len(set(model_names.values())) != 2:
        raise ValueError("两条模型轴必须有不同的模型 ID")
    source_fingerprint = _harness_fingerprint()
    harness_versions = {arm: f"{source_fingerprint}:prompt-sha256:{hashlib.sha256(PROMPTS[arm].encode()).hexdigest()}"
                        for arm in ARMS}
    paths = sorted((ROOT / "eval_sets" / COLLECTION.value / "tasks").glob("*.json"))
    if not paths:
        raise ValueError("Regression 集为空")
    manifest = []
    for path in paths:
        task = load_eval_task(path, project_root=ROOT)
        if task.label_status != "adjudicated":
            raise ValueError("四格实验只接受已仲裁 Task")
        manifest.append({"task_id": task.task_id, "path": str(path.relative_to(ROOT)),
                         "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    evaluator_paths = ("src/merchant_agent/evaluation/code_evaluator.py",
                       "src/merchant_agent/evaluation/metrics.py",
                       "src/merchant_agent/evaluation/model_harness_matrix.py")
    directory = ROOT / "runs/model_harness_matrix" / uuid.uuid4().hex
    directory.mkdir(parents=True, exist_ok=False, mode=0o700)
    target = directory / "experiment.json"
    batches = {}
    for model_key in models:
        for arm in ARMS:
            batch_id = uuid.uuid4().hex
            batch_dir = ROOT / "runs/batches" / batch_id
            batch_dir.mkdir(parents=True, exist_ok=False, mode=0o700)
            batch = {"batch_id": batch_id, "collection": COLLECTION.value,
                     "repeats": REPEATS, "model_version": model_names[model_key],
                     "harness_version": harness_versions[arm],
                     "started_at": datetime.now(timezone.utc).isoformat(),
                     "ended_at": None, "status": "running", "manifest": manifest,
                     "items": [], "aggregate": None, "uncertainty": None}
            batches[(model_key, arm)] = batch
            save_batch(batch_dir / "batch.json", batch)
    rng = random.Random(SEED)
    schedule = []
    for task in manifest:
        for repeat_index in range(REPEATS):
            cells = list(batches)
            rng.shuffle(cells)
            schedule.extend({"task_id": task["task_id"], "repeat_index": repeat_index,
                             "model_key": model_key, "arm": arm}
                            for model_key, arm in cells)
    record = {
        "status": "running", "started_at": datetime.now(timezone.utc).isoformat(),
        "collection": COLLECTION.value, "repeats": REPEATS, "seed": SEED,
        "manifest": manifest, "models": model_names, "harness_versions": harness_versions,
        "source_fingerprint": source_fingerprint,
        "evaluator_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                             for name in evaluator_paths},
        "adapter_parameters": {"deepseek": {"endpoint_type": "responses"},
                               "glm": {"endpoint_type": "chat_completions", "json_mode": True}},
        "schedule": schedule, "completed": [], "batch_ids": {
            f"{model_key}/{arm}": batch["batch_id"] for (model_key, arm), batch in batches.items()},
        "holdout_used": False, "comparison": None,
    }
    _save(target, record)
    path_by_id = {item["task_id"]: ROOT / item["path"] for item in manifest}
    hash_by_id = {item["task_id"]: item["sha256"] for item in manifest}
    first_trial_seen = set()
    try:
        for slot in schedule:
            task_id = slot["task_id"]
            path = path_by_id[task_id]
            if hashlib.sha256(path.read_bytes()).hexdigest() != hash_by_id[task_id]:
                raise ValueError("四格运行中 Task 快照变化")
            model_key, arm = slot["model_key"], slot["arm"]
            model = models[model_key]
            prompt = PROMPTS[arm]

            async def invoke(state, db_path, trace_path, thread_id):
                return await invoke_live_agent(state, db_path, trace_path, thread_id,
                                               model=model, planning_instruction=prompt)

            trial = await run_trial(path, project_root=ROOT, invoke=invoke,
                                    model_version=model_names[model_key],
                                    harness_version=harness_versions[arm], timeout_seconds=90)
            score = evaluate_trial(trial, path, project_root=ROOT)
            metrics = trial_metrics(trial, score, project_root=ROOT)
            batch = batches[(model_key, arm)]
            batch["items"].append({"task_id": task_id, "repeat_index": slot["repeat_index"],
                                   "trial_id": trial["trial_id"], "trial_status": trial["status"],
                                   "score": score, "metrics": metrics})
            save_batch(ROOT / "runs/batches" / batch["batch_id"] / "batch.json", batch)
            record["completed"].append({**slot, "trial_id": trial["trial_id"],
                                        "trial_status": trial["status"], "passed": score["passed"]})
            _save(target, record)
            if model_key not in first_trial_seen:
                first_trial_seen.add(model_key)
                if trial["status"] != "completed":
                    raise RuntimeError(f"{model_key} 首次 Trial 未完成，已停止四格运行")
        for batch in batches.values():
            rows = [item["metrics"] for item in batch["items"]]
            batch["aggregate"] = aggregate_metrics(rows)
            batch["uncertainty"] = summarize_repeats(rows, expected_repeats=REPEATS)
            batch["status"] = "completed"
            batch["ended_at"] = datetime.now(timezone.utc).isoformat()
            save_batch(ROOT / "runs/batches" / batch["batch_id"] / "batch.json", batch)
        record["comparison"] = compare_model_harness_matrix(
            list(batches.values()), models=(deepseek_name, glm_name),
            harnesses=(harness_versions[ARMS[0]], harness_versions[ARMS[1]]))
        record["status"] = "completed"
    except BaseException as exc:
        record["status"] = "failed"
        record["error_type"] = type(exc).__name__
        raise
    finally:
        record["ended_at"] = datetime.now(timezone.utc).isoformat()
        _save(target, record)
    return target


if __name__ == "__main__":
    print(f"真实四格实验记录：{asyncio.run(main())}")
