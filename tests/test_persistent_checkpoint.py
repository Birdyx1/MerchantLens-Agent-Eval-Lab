import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from merchant_agent.tracing.reader import read_spans


def test_sqlite_checkpoint_resumes_in_a_new_process(tmp_path):
    db_path = tmp_path / "orders.sqlite"
    with sqlite3.connect(db_path) as db:
        db.execute("CREATE TABLE orders (order_id TEXT, store_id TEXT, paid_fen INTEGER, refunded_fen INTEGER)")
        db.execute("INSERT INTO orders VALUES ('1', 'A', 15000, 3000)")
    checkpoint_path = tmp_path / "checkpoints.sqlite"
    trace_path = tmp_path / "trace.jsonl"
    worker = Path(__file__).parent / "support" / "checkpoint_worker.py"
    src_path = Path(__file__).resolve().parents[1] / "src"
    env = os.environ | {"PYTHONPATH": str(src_path), "LANGGRAPH_STRICT_MSGPACK": "true"}

    def call(mode):
        result = subprocess.run(
            [sys.executable, str(worker), mode, str(checkpoint_path), str(db_path), str(trace_path)],
            env=env, capture_output=True, text=True, check=True, timeout=15,
        )
        return json.loads(result.stdout)

    paused = call("write")
    assert paused["next"] == ["act"]
    assert paused["final_answer"] is None
    assert paused["step_count"] == 1
    assert not trace_path.exists()

    resumed = call("resume")
    assert resumed["next"] == []
    assert resumed["final_answer"] == "门店 A 净收入为 12000 分"
    assert resumed["step_count"] == 3
    assert resumed["trace_id"] == paused["trace_id"]
    assert resumed["memory_check"]["passed"] is True
    assert all(resumed["memory_check"]["checks"].values())
    (span,) = read_spans(str(trace_path))
    assert span["attributes"]["result_fen"] == 12000
