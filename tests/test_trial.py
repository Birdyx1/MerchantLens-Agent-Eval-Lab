import asyncio
import json
import sqlite3
from pathlib import Path

from merchant_agent.evaluation.trial import run_trial


ROOT = Path(__file__).resolve().parents[1]


def _project(tmp_path):
    for relative in ("schemas/eval_task.schema.json", "fixtures/business_data/orders.csv"):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / relative).read_bytes())
    task_dir = tmp_path / "eval_sets/golden/tasks"
    task_dir.mkdir(parents=True)
    task = task_dir / "store_net_a.json"
    task.write_bytes((ROOT / "fixtures/eval_task_examples/store_net_a.json").read_bytes())
    return task


def test_each_trial_has_fresh_database_state_and_identity(tmp_path):
    task = _project(tmp_path)
    seen = []

    async def invoke(state, db_path, trace_path, thread_id):
        with sqlite3.connect(db_path) as db:
            count = db.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        seen.append((count, state["trace_id"], thread_id, state["user_request"]))
        trace_path.write_text(json.dumps({"trace_id": state["trace_id"], "span_id": state["root_span_id"]}) + "\n")
        return {**state, "final_answer": "12000 分", "termination_reason": "completed"}

    first = asyncio.run(run_trial(task, project_root=tmp_path, invoke=invoke,
                                  model_version="model-a", harness_version="harness-a"))
    second = asyncio.run(run_trial(task, project_root=tmp_path, invoke=invoke,
                                   model_version="model-a", harness_version="harness-a"))
    assert first["status"] == second["status"] == "completed"
    assert seen[0][0] == seen[1][0] > 0
    assert seen[0][1] != seen[1][1] and seen[0][2] != seen[1][2]
    assert first["environment_sha256_before"] == first["environment_sha256_after"]
    assert first["traffic"]["traffic_type"] == "evaluation"
    assert "evaluation" not in seen[0][3]
    path = tmp_path / "runs/trials" / first["trial_id"] / "trial.json"
    assert json.loads(path.read_text())["model_version"] == "model-a"
    assert path.stat().st_mode & 0o777 == 0o600


def test_trial_marks_changed_database_as_contaminated(tmp_path):
    task = _project(tmp_path)

    async def invoke(state, db_path, trace_path, thread_id):
        with sqlite3.connect(db_path) as db:
            db.execute("DELETE FROM orders")
        trace_path.write_text(json.dumps({"trace_id": state["trace_id"], "span_id": state["root_span_id"]}) + "\n")
        return {**state, "termination_reason": "completed"}

    result = asyncio.run(run_trial(task, project_root=tmp_path, invoke=invoke,
                                   model_version="model-a", harness_version="harness-a"))
    assert result["status"] == "contaminated"
    assert result["environment_sha256_before"] != result["environment_sha256_after"]


def test_trial_records_failure_without_losing_snapshot(tmp_path):
    task = _project(tmp_path)

    async def invoke(state, db_path, trace_path, thread_id):
        raise RuntimeError("simulated failure")

    result = asyncio.run(run_trial(task, project_root=tmp_path, invoke=invoke,
                                   model_version="model-a", harness_version="harness-a"))
    assert result["status"] == "error"
    assert result["error_type"] == "RuntimeError"
    assert (tmp_path / "runs/trials" / result["trial_id"] / "trial.json").is_file()


def test_trial_cannot_complete_without_trace(tmp_path):
    task = _project(tmp_path)

    async def invoke(state, db_path, trace_path, thread_id):
        return {**state, "termination_reason": "completed"}

    result = asyncio.run(run_trial(task, project_root=tmp_path, invoke=invoke,
                                   model_version="model-a", harness_version="harness-a"))
    assert result["status"] == "missing_trace"
    assert result["trace_status"] == "missing"
