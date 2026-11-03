"""对阶段 4～7 的正式资产、封存 Holdout 与批次证据做只读核验。"""

import hashlib
import json
from pathlib import Path

from merchant_agent.evaluation.agreement import validate_resolution_for_task
from merchant_agent.evaluation.rubric import load_task_rubric
from merchant_agent.evaluation.task import load_eval_task, task_exposure_sha256


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit_evidence(project_root: Path, batch_plan_path: Path) -> dict:
    """只读审计证据链；失败项显式返回，不修改既有 Trial 或标注。"""
    root = project_root.resolve()
    failures: list[str] = []
    paths_by_split = {
        split: sorted((root / "eval_sets" / split / "tasks").glob("*.json"))
        for split in ("golden", "regression")
    }
    holdout_paths = sorted((root / "holdout/tasks").glob("*.json"))
    all_paths = [*paths_by_split["golden"], *paths_by_split["regression"], *holdout_paths]
    task_ids = []
    exposures = []
    for path in all_paths:
        try:
            task = load_eval_task(path, project_root=root)
            load_task_rubric(task, project_root=root)
            validate_resolution_for_task(path, project_root=root)
            task_ids.append(task.task_id)
            exposures.append(task_exposure_sha256(path))
        except Exception as exc:
            failures.append(f"task:{path.relative_to(root)}:{type(exc).__name__}")
    if len(task_ids) != len(set(task_ids)):
        failures.append("duplicate_task_id")
    if len(exposures) != len(set(exposures)):
        failures.append("duplicate_task_exposure")

    manifest_path = root / "holdout/manifest.json"
    if not manifest_path.is_file():
        failures.append("missing_holdout_manifest")
    else:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest_by_id = {item["task_id"]: item for item in manifest["tasks"]}
        if manifest.get("status") != "sealed" or set(manifest_by_id) != {path.stem for path in holdout_paths}:
            failures.append("holdout_manifest_membership")
        for path in holdout_paths:
            item = manifest_by_id.get(path.stem)
            if item is None:
                continue
            task = load_eval_task(path, project_root=root)
            annotations = [root / "runs/annotations" / task.task_id / f"{reviewer}.json"
                           for reviewer in ("reviewer_one", "reviewer_two")]
            resolution = root / "runs/adjudications" / f"{task.task_id}.json"
            if (item["task_sha256"] != _sha256(path)
                    or item["fixture_sha256"] != _sha256(task.fixture_path)
                    or item["rubric_sha256"] != task.rubric_sha256
                    or any(not source.is_file() for source in [*annotations, resolution])
                    or item["annotation_sha256"] != [_sha256(source) for source in annotations]
                    or item["adjudication_sha256"] != _sha256(resolution)):
                failures.append(f"holdout_manifest_hash:{task.task_id}")

    plan_path = batch_plan_path.resolve()
    if not plan_path.is_relative_to(root / "runs/pilot_repeated"):
        raise ValueError("只允许审计项目内的重复运行清单")
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    if plan.get("status") != "completed" or plan.get("holdout_used") is not False:
        failures.append("batch_plan_status_or_holdout_flag")
    for relative, frozen_sha in plan.get("evaluator_sha256", {}).items():
        source = (root / relative).resolve()
        if not source.is_relative_to(root / "src/merchant_agent/evaluation") or not source.is_file() or _sha256(source) != frozen_sha:
            failures.append(f"evaluator_version_drift:{relative}")
    trial_count = 0
    for split, paths in paths_by_split.items():
        frozen = {item["task_id"]: item["sha256"] for item in plan["collections"][split]}
        if frozen != {path.stem: _sha256(path) for path in paths}:
            failures.append(f"task_snapshot:{split}")
        brief = plan["batches"].get(split)
        if brief is None:
            failures.append(f"missing_batch:{split}")
            continue
        batch_path = root / "runs/batches" / brief["batch_id"] / "batch.json"
        batch = json.loads(batch_path.read_text(encoding="utf-8"))
        batch_manifest = {item["task_id"]: item["sha256"] for item in batch.get("manifest", [])}
        observed_keys = [(item.get("task_id"), item.get("repeat_index")) for item in batch.get("items", [])]
        expected_keys = {(task_id, repeat_index) for task_id in frozen
                         for repeat_index in range(plan["repeats"])}
        if (batch.get("status") != "completed" or batch.get("collection") != split
                or batch.get("model_version") != plan["model_version"]
                or batch.get("harness_version") != plan["harness_version"]
                or batch_manifest != frozen
                or len(observed_keys) != len(expected_keys)
                or set(observed_keys) != expected_keys):
            failures.append(f"batch_contract:{split}")
        for item in batch.get("items", []):
            trial_count += 1
            trial_path = root / "runs/trials" / item["trial_id"] / "trial.json"
            if not trial_path.is_file():
                failures.append(f"missing_trial:{item['trial_id']}")
                continue
            trial = json.loads(trial_path.read_text(encoding="utf-8"))
            trace_relative = Path(trial["trace_path"])
            trace_path = (root / trace_relative).resolve()
            if (trace_relative.is_absolute() or not trace_path.is_relative_to(root / "runs/trials")
                    or not trace_path.is_file() or trial.get("trace_sha256") != _sha256(trace_path)
                    or trial.get("task_id") != item.get("task_id")
                    or trial.get("model_version") != plan["model_version"]
                    or trial.get("harness_version") != plan["harness_version"]
                    or not isinstance(item.get("score"), dict)
                    or item["score"].get("trial_id") != item["trial_id"]):
                failures.append(f"trial_trace_binding:{item['trial_id']}")
    holdout_ids = {path.stem for path in holdout_paths}
    for trial_path in (root / "runs/trials").glob("*/trial.json"):
        trial = json.loads(trial_path.read_text(encoding="utf-8"))
        if trial.get("task_id") in holdout_ids:
            failures.append(f"holdout_was_run:{trial['task_id']}")
    return {
        "passed": not failures,
        "failures": failures,
        "task_counts": {split: len(paths) for split, paths in paths_by_split.items()},
        "holdout_count": len(holdout_paths),
        "audited_batch_trials": trial_count,
        "batch_plan_sha256": _sha256(plan_path),
    }
