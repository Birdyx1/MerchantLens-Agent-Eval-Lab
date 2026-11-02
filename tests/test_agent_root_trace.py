import asyncio
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from merchant_agent.agent.runner import AgentDeadlineExceeded, run_agent
from merchant_agent.agent.state import initial_state
from merchant_agent.tracing.reader import read_spans


def _state():
    return initial_state("task-1", "a" * 32, "b" * 16, "问题")


def _run(graph, path, **kwargs):
    return asyncio.run(run_agent(graph, _state(), trace_path=str(path), **kwargs))


def _root(path):
    spans = read_spans(str(path))
    assert len(spans) == 1
    span = spans[0]
    schema = json.loads((Path(__file__).resolve().parents[1] / "schemas/span.schema.json").read_text())
    assert Draft202012Validator(schema).is_valid(span)
    assert span["span_id"] == "b" * 16
    assert span["parent_span_id"] is None
    return span["attributes"]


@pytest.mark.parametrize("reason", ["completed", "max_steps", "max_tokens"])
def test_root_span_records_graph_termination(tmp_path, reason):
    class Graph:
        async def ainvoke(self, state, config):
            return {**state, "termination_reason": reason}

    path = tmp_path / "trace.jsonl"
    _run(Graph(), path)
    assert _root(path)["termination_reason"] == reason


def test_root_span_records_deadline_without_success(tmp_path):
    class Graph:
        async def ainvoke(self, state, config):
            await asyncio.sleep(0.1)

    path = tmp_path / "trace.jsonl"
    with pytest.raises(AgentDeadlineExceeded):
        _run(Graph(), path, timeout_seconds=0.01)
    assert _root(path)["termination_reason"] == "deadline"


def test_root_span_records_inner_failure(tmp_path):
    class Graph:
        async def ainvoke(self, state, config):
            raise TimeoutError("模型超时")

    path = tmp_path / "trace.jsonl"
    with pytest.raises(TimeoutError, match="模型超时"):
        _run(Graph(), path, timeout_seconds=1)
    assert _root(path)["termination_reason"] == "error"
    assert _root(path)["error_type"] == "TimeoutError"


def test_root_span_records_external_cancellation(tmp_path):
    async def scenario():
        entered = asyncio.Event()

        class Graph:
            async def ainvoke(self, state, config):
                entered.set()
                await asyncio.sleep(10)

        task = asyncio.create_task(run_agent(Graph(), _state(), trace_path=str(tmp_path / "trace.jsonl")))
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())
    assert _root(tmp_path / "trace.jsonl")["termination_reason"] == "cancelled"
