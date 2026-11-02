"""固定任务快照的顺序批量评测流水线。"""

import hashlib
import json
import os
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from merchant_agent.evaluation.code_evaluator import evaluate_trial
from merchant_agent.evaluation.metrics import aggregate_metrics, trial_metrics
from merchant_agent.evaluation.sets import EvalCollection
from merchant_agent.evaluation.task import load_eval_task
from merchant_agent.evaluation.trial import TrialInvoker, run_trial
from merchant_agent.evaluation.uncertainty import summarize_repeats


def _save(path: Path, data: dict) -> None:
    """用同目录临时文件替换清单，保留中断前的完整 JSON。"""
    temporary = path.with_name(f".{path.name}-{uuid.uuid4().hex}")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump(data, output, ensure_ascii=False, indent=2)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


async def run_batch(*, project_root: Path, collection: EvalCollection,
                    repeats: int, model_version: str, harness_version: str,
                    invoke_factory: Callable[[Path, int], TrialInvoker],
                    timeout_seconds: float | None = None) -> dict:
    """冻结单集合任务清单；每题每轮运行一次并记录评分与指标。"""
    if not isinstance(collection, EvalCollection):
        raise ValueError("只能选择一个正式评测集合")
    if type(repeats) is not int or repeats < 2:
        raise ValueError("每题重复次数至少为 2")
    root = project_root.resolve()
    task_dir = root / "eval_sets" / collection.value / "tasks"
    paths = sorted(task_dir.glob("*.json"))
    if not paths:
        raise ValueError("评测集合为空，不得生成虚构报告")
    manifest = []
    for path in paths:
        task = load_eval_task(path, project_root=root)
        if path.stem != task.task_id:
            raise ValueError("Task 文件名与 ID 不一致")
        manifest.append({"task_id": task.task_id, "path": str(path.relative_to(root)),
                         "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    batch_id = uuid.uuid4().hex
    directory = root / "runs" / "batches" / batch_id
    directory.mkdir(parents=True, exist_ok=False, mode=0o700)
    output_path = directory / "batch.json"
    output = {"batch_id": batch_id, "collection": collection.value, "repeats": repeats,
              "model_version": model_version, "harness_version": harness_version,
              "started_at": datetime.now(timezone.utc).isoformat(), "ended_at": None,
              "status": "running", "manifest": manifest, "items": [],
              "aggregate": None, "uncertainty": None}
    _save(output_path, output)
    rows = []
    try:
        for item in manifest:
            path = root / item["path"]
            for repeat_index in range(repeats):
                if hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
                    raise ValueError("批次运行中 Task 快照发生变化")
                invoke = invoke_factory(path, repeat_index)
                trial = await run_trial(path, project_root=root, invoke=invoke,
                                        model_version=model_version, harness_version=harness_version,
                                        timeout_seconds=timeout_seconds)
                entry = {"task_id": item["task_id"], "repeat_index": repeat_index,
                         "trial_id": trial["trial_id"], "trial_status": trial["status"],
                         "score": None, "metrics": None}
                output["items"].append(entry)
                _save(output_path, output)
                score = evaluate_trial(trial, path, project_root=root)
                metrics = trial_metrics(trial, score, project_root=root)
                rows.append(metrics)
                entry["score"] = score
                entry["metrics"] = metrics
                _save(output_path, output)
        output["aggregate"] = aggregate_metrics(rows)
        output["uncertainty"] = summarize_repeats(rows, expected_repeats=repeats)
        output["status"] = "completed"
    except Exception as exc:
        output["status"] = "failed"
        output["error_type"] = type(exc).__name__
        raise
    finally:
        output["ended_at"] = datetime.now(timezone.utc).isoformat()
        _save(output_path, output)
    return output
