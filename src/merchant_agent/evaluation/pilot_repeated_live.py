"""冻结评测配置后，对试点 Golden 与 Regression 各跑两轮真实 Trial。"""

import asyncio
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from merchant_agent.agent.deepseek_responses_model import DeepSeekResponsesModel
from merchant_agent.evaluation.base_admission_live import _config
from merchant_agent.evaluation.batch import run_batch
from merchant_agent.evaluation.data_closure_live import _harness_fingerprint
from merchant_agent.evaluation.live_invoke import invoke_live_agent
from merchant_agent.evaluation.sets import EvalCollection
from merchant_agent.evaluation.task import load_eval_task


ROOT = Path(__file__).resolve().parents[3]
COLLECTIONS = (EvalCollection.GOLDEN, EvalCollection.REGRESSION)
EVALUATOR_FILES = (
    "src/merchant_agent/evaluation/code_evaluator.py",
    "src/merchant_agent/evaluation/trajectory_evaluator.py",
    "src/merchant_agent/evaluation/metrics.py",
    "src/merchant_agent/evaluation/uncertainty.py",
    "src/merchant_agent/evaluation/batch.py",
)


def _freeze_plan(model_name: str, harness_version: str) -> dict:
    """在运行前固定全部题目和评分源码摘要，禁止边跑边改判据。"""
    sets = {}
    for collection in COLLECTIONS:
        paths = sorted((ROOT / "eval_sets" / collection.value / "tasks").glob("*.json"))
        if not paths:
            raise ValueError(f"{collection.value} 集合为空")
        sets[collection.value] = []
        for path in paths:
            task = load_eval_task(path, project_root=ROOT)
            if task.label_status != "adjudicated":
                raise ValueError("批量评测只接受已仲裁题目")
            sets[collection.value].append({"task_id": task.task_id,
                                           "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    return {
        "status": "planned", "created_at": datetime.now(timezone.utc).isoformat(),
        "model_version": model_name, "harness_version": harness_version,
        "repeats": 2, "collections": sets,
        "evaluator_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                             for name in EVALUATOR_FILES},
        "holdout_used": False, "batches": {},
    }


def _save(path: Path, payload: dict) -> None:
    """原子更新运行清单，中断时仍保留已完成批次证据。"""
    temporary = path.with_name(f".{path.name}-{uuid.uuid4().hex}")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as output:
        json.dump(payload, output, ensure_ascii=False, indent=2)
        output.write("\n")
        output.flush()
        os.fsync(output.fileno())
    os.replace(temporary, path)


async def main() -> Path:
    """各集合独立运行；不同集合的分数不能当成版本差值。"""
    key, model_name = _config()
    model = DeepSeekResponsesModel(model_name, key)
    plan = _freeze_plan(model_name, _harness_fingerprint())
    directory = ROOT / "runs" / "pilot_repeated" / uuid.uuid4().hex
    directory.mkdir(parents=True, exist_ok=False, mode=0o700)
    path = directory / "plan.json"
    _save(path, plan)

    def invoke_factory(_task_path: Path, _repeat_index: int):
        async def invoke(state, db_path, trace_path, thread_id):
            return await invoke_live_agent(state, db_path, trace_path, thread_id, model=model)
        return invoke

    try:
        for collection in COLLECTIONS:
            batch = await run_batch(project_root=ROOT, collection=collection,
                                    repeats=2, model_version=model_name,
                                    harness_version=plan["harness_version"],
                                    invoke_factory=invoke_factory, timeout_seconds=90)
            plan["batches"][collection.value] = {
                "batch_id": batch["batch_id"], "status": batch["status"],
                "aggregate": batch["aggregate"], "uncertainty": batch["uncertainty"],
            }
            _save(path, plan)
        plan["status"] = "completed"
    except BaseException as exc:
        plan["status"] = "failed"
        plan["error_type"] = type(exc).__name__
        raise
    finally:
        plan["ended_at"] = datetime.now(timezone.utc).isoformat()
        _save(path, plan)
    return path


if __name__ == "__main__":
    print(f"重复运行清单：{asyncio.run(main())}")
