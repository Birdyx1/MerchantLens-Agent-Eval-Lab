import asyncio
import json
from pathlib import Path

import pytest

from merchant_agent.evaluation import batch
from merchant_agent.evaluation.sets import EvalCollection


ROOT = Path(__file__).resolve().parents[1]


def _project(tmp_path, *, with_task=True):
    for relative in ("schemas/eval_task.schema.json", "fixtures/business_data/orders.csv"):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / relative).read_bytes())
    task_dir = tmp_path / "eval_sets/golden/tasks"
    task_dir.mkdir(parents=True)
    if with_task:
        (task_dir / "store_net_a_001.json").write_bytes(
            (ROOT / "fixtures/eval_task_examples/store_net_a.json").read_bytes())


def test_empty_collection_is_rejected(tmp_path):
    _project(tmp_path, with_task=False)
    with pytest.raises(ValueError, match="为空"):
        asyncio.run(batch.run_batch(project_root=tmp_path, collection=EvalCollection.GOLDEN,
                                    repeats=2, model_version="m1", harness_version="h1",
                                    invoke_factory=lambda path, index: None))


def test_batch_runs_each_repeat_and_persists_summary(tmp_path, monkeypatch):
    _project(tmp_path)
    calls = []

    async def fake_trial(path, *, invoke, **kwargs):
        calls.append((path, invoke))
        return {"trial_id": f"trial_{len(calls)}", "task_id": path.stem, "status": "completed"}

    monkeypatch.setattr(batch, "run_trial", fake_trial)
    monkeypatch.setattr(batch, "evaluate_trial", lambda trial, path, **kwargs:
                        {"trial_id": trial["trial_id"], "task_id": path.stem, "passed": True})
    monkeypatch.setattr(batch, "trial_metrics", lambda trial, score, **kwargs:
                        {"trial_id": trial["trial_id"], "task_id": trial["task_id"],
                         "overall_success": True, "result_success": True,
                         "trajectory_success": True, "total_tokens": 10,
                         "latency_ms": 20, "tool_calls": 1, "safety_status": "unknown"})
    result = asyncio.run(batch.run_batch(project_root=tmp_path, collection=EvalCollection.GOLDEN,
                                         repeats=2, model_version="m1", harness_version="h1",
                                         invoke_factory=lambda path, index: index))
    assert result["status"] == "completed"
    assert [invoke for _, invoke in calls] == [0, 1]
    assert result["aggregate"]["trials"] == 2
    assert result["uncertainty"]["tasks"] == 1
    saved = tmp_path / "runs/batches" / result["batch_id"] / "batch.json"
    assert json.loads(saved.read_text())["manifest"][0]["task_id"] == "store_net_a_001"
    assert saved.stat().st_mode & 0o777 == 0o600


def test_batch_preserves_partial_work_on_failure(tmp_path, monkeypatch):
    _project(tmp_path)
    count = 0

    async def fake_trial(path, *, invoke, **kwargs):
        nonlocal count
        count += 1
        return {"trial_id": f"trial_{count}", "task_id": path.stem, "status": "completed"}

    def fake_score(trial, path, **kwargs):
        if trial["trial_id"] == "trial_2":
            raise RuntimeError("grader failed")
        return {"trial_id": trial["trial_id"], "task_id": path.stem, "passed": True}

    monkeypatch.setattr(batch, "run_trial", fake_trial)
    monkeypatch.setattr(batch, "evaluate_trial", fake_score)
    monkeypatch.setattr(batch, "trial_metrics", lambda trial, score, **kwargs:
                        {"trial_id": trial["trial_id"], "task_id": trial["task_id"],
                         "overall_success": True})
    with pytest.raises(RuntimeError, match="grader failed"):
        asyncio.run(batch.run_batch(project_root=tmp_path, collection=EvalCollection.GOLDEN,
                                    repeats=2, model_version="m1", harness_version="h1",
                                    invoke_factory=lambda path, index: index))
    saved = next((tmp_path / "runs/batches").glob("*/batch.json"))
    data = json.loads(saved.read_text())
    assert data["status"] == "failed"
    assert len(data["items"]) == 2
    assert data["items"][0]["score"] is not None
    assert data["items"][1]["score"] is None
