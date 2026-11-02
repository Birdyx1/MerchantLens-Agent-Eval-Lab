"""单次评测试验：冻结输入、隔离环境、执行并落盘证据。"""

import asyncio
import hashlib
import json
import math
import os
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from pathlib import Path

from merchant_agent.agent.state import AgentState, initial_state
from merchant_agent.evaluation.holdout import prepare_eval_dispatch
from merchant_agent.evaluation.task import load_eval_task
from merchant_agent.tools.sql.init_orders_db import create_orders_db
from merchant_agent.tracing.reader import read_spans


TrialInvoker = Callable[[AgentState, Path, Path, str], Awaitable[AgentState]]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


async def run_trial(
    task_path: Path, *, project_root: Path, invoke: TrialInvoker,
    model_version: str, harness_version: str, timeout_seconds: float | None = None,
) -> dict:
    """为一个 Task 建立全新环境；失败也保留 Trial 记录。"""
    root = project_root.resolve()
    task = load_eval_task(task_path, project_root=root)
    if not model_version.strip() or not harness_version.strip():
        raise ValueError("模型和 Harness 版本不能为空")
    if timeout_seconds is not None and (
        isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float))
        or not math.isfinite(timeout_seconds) or timeout_seconds <= 0
    ):
        raise ValueError("Trial 时限必须是有限正数")
    trial_id = uuid.uuid4().hex
    dispatch = prepare_eval_dispatch(task_path, project_root=root, run_id=trial_id)
    trial_dir = root / "runs" / "trials" / trial_id
    trial_dir.mkdir(parents=True, exist_ok=False, mode=0o700)
    db_path = trial_dir / "orders.sqlite"
    trace_path = trial_dir / "trace.jsonl"
    record_path = trial_dir / "trial.json"
    create_orders_db(str(task.fixture_path), str(db_path))
    before_db = _sha256(db_path)
    state = initial_state(task.task_id, uuid.uuid4().hex, uuid.uuid4().hex[:16], dispatch.agent_input)
    thread_id = f"eval-{trial_id}"
    started = datetime.now(timezone.utc).isoformat()
    record = {
        "trial_id": trial_id,
        "task_id": task.task_id,
        "task_sha256": _sha256(task_path),
        "fixture_sha256": _sha256(task.fixture_path),
        "environment_sha256_before": before_db,
        "environment_sha256_after": None,
        "trace_id": state["trace_id"],
        "thread_id": thread_id,
        "traffic": dispatch.metadata,
        "model_version": model_version,
        "harness_version": harness_version,
        "started_at": started,
        "ended_at": None,
        "status": "running",
        "final_answer": None,
        "termination_reason": None,
        "error_type": None,
        "trace_status": "missing",
        "trace_sha256": None,
        "trace_path": str(trace_path.relative_to(root)),
        "environment_path": str(db_path.relative_to(root)),
    }
    try:
        if timeout_seconds is None:
            result = await invoke(state, db_path, trace_path, thread_id)
        else:
            async with asyncio.timeout(timeout_seconds):
                result = await invoke(state, db_path, trace_path, thread_id)
        record["final_answer"] = result.get("final_answer")
        record["termination_reason"] = result.get("termination_reason")
        record["status"] = "completed" if record["termination_reason"] == "completed" else "incomplete"
    except TimeoutError:
        record["status"] = "timeout"
        record["error_type"] = "TimeoutError"
    except Exception as exc:
        record["status"] = "error"
        record["error_type"] = type(exc).__name__
    finally:
        if trace_path.is_file():
            record["trace_sha256"] = _sha256(trace_path)
            try:
                spans = read_spans(str(trace_path))
                if spans and all(span.get("trace_id") == state["trace_id"] for span in spans):
                    record["trace_status"] = "present"
                else:
                    record["trace_status"] = "invalid"
            except (OSError, ValueError, KeyError, TypeError):
                record["trace_status"] = "invalid"
        if record["status"] == "completed" and record["trace_status"] != "present":
            record["status"] = "missing_trace"
        record["environment_sha256_after"] = _sha256(db_path)
        if record["environment_sha256_after"] != before_db:
            record["status"] = "contaminated"
        record["ended_at"] = datetime.now(timezone.utc).isoformat()
        payload = json.dumps(record, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")
        fd = os.open(record_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
    return record
