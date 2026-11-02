import asyncio
import json
from types import SimpleNamespace

import pytest

from merchant_agent.agent.action import make_tool_node
from merchant_agent.agent.graph import build_observation_loop_graph
from merchant_agent.agent.model_port import ModelResponse
from merchant_agent.agent.retry_policy import should_retry_tool
from merchant_agent.agent.state import initial_state
from merchant_agent.tracing.reader import read_spans


class SequenceModel:
    def __init__(self, tool_name, arguments):
        self.tool_name = tool_name
        self.arguments = arguments
        self.calls = 0

    async def generate(self, messages):
        self.calls += 1
        action = ({"type": "tool", "name": self.tool_name, "arguments": self.arguments}
                  if self.calls == 1 else {"type": "finish", "answer": "已读取工具观察"})
        return ModelResponse(json.dumps({"plan": ["核对工具结果"], "action": action}),
                             "fixed-model", 10, 4)


class FlakySqlClient:
    def __init__(self, *, always_timeout=False, mcp_error=False):
        self.calls = 0
        self.always_timeout = always_timeout
        self.mcp_error = mcp_error

    async def call_tool(self, name, arguments):
        self.calls += 1
        if self.always_timeout or self.calls == 1 and not self.mcp_error:
            raise asyncio.TimeoutError()
        if self.mcp_error:
            return SimpleNamespace(is_error=True, structured_content=None)
        return SimpleNamespace(is_error=False, structured_content={"result": 12000})


def _run(tmp_path, model, client, **state_options):
    trace_path = tmp_path / "trace.jsonl"
    graph = build_observation_loop_graph(model, make_tool_node(client, str(trace_path)))
    state = asyncio.run(graph.ainvoke(initial_state(
        "task-1", "a" * 32, "b" * 16, "门店 A 净收入？", **state_options
    )))
    return state, read_spans(str(trace_path))


def test_read_only_timeout_retries_once_with_same_operation_id(tmp_path):
    model = SequenceModel("get_store_net", {"store_id": "A"})
    client = FlakySqlClient()
    state, spans = _run(tmp_path, model, client)
    assert client.calls == 2
    assert model.calls == 2
    assert state["retry_count"] == 1
    assert state["tool_attempt"] == 2
    assert state["step_count"] == 4
    assert state["termination_reason"] == "completed"
    assert [span["attributes"]["outcome"] for span in spans] == ["timeout", "success"]
    assert [span["attributes"]["attempt"] for span in spans] == [1, 2]
    assert spans[0]["span_id"] != spans[1]["span_id"]
    assert spans[0]["attributes"]["operation_id"] == spans[1]["attributes"]["operation_id"]


@pytest.mark.parametrize("options, expected_reason", [
    ({"max_tool_attempts": 1}, "completed"),
    ({"max_steps": 2}, "max_steps"),
])
def test_retry_respects_attempt_and_step_budgets(tmp_path, options, expected_reason):
    model = SequenceModel("get_store_net", {"store_id": "A"})
    client = FlakySqlClient(always_timeout=True)
    state, spans = _run(tmp_path, model, client, **options)
    assert client.calls == len(spans) == 1
    assert state["retry_count"] == 0
    assert state["termination_reason"] == expected_reason


def test_ambiguous_mcp_error_is_not_automatically_retried(tmp_path):
    model = SequenceModel("get_store_net", {"store_id": "A"})
    client = FlakySqlClient(mcp_error=True)
    state, spans = _run(tmp_path, model, client)
    assert client.calls == len(spans) == 1
    assert state["retry_count"] == 0
    assert state["last_tool_result"]["outcome"] == "dependency_error"


def test_python_timeout_result_is_not_automatically_retried(tmp_path):
    class PythonClient:
        calls = 0

        async def call_tool(self, name, arguments):
            self.calls += 1
            return SimpleNamespace(is_error=False, structured_content={
                "status": "timeout", "stdout": "", "stderr": "", "exit_code": None,
                "duration_ms": 2000, "stdout_truncated": False,
                "stderr_truncated": False, "oom_killed": False,
            })

    client = PythonClient()
    model = SequenceModel("execute_python", {"code": "print(1)", "timeout_seconds": 2})
    state, spans = _run(tmp_path, model, client)
    assert client.calls == len(spans) == 1
    assert state["retry_count"] == 0
    assert state["last_tool_result"]["outcome"] == "timeout"


def test_search_timeout_is_retryable_under_budget():
    state = initial_state("task-1", "a" * 32, "b" * 16, "检索商家资料")
    state["selected_tool"] = "search_web"
    state["operation_id"] = "operation-1"
    state["tool_attempt"] = 1
    state["step_count"] = 2
    state["last_tool_result"] = {
        "tool_name": "search_web", "outcome": "timeout", "raw_status": "timeout"
    }
    assert should_retry_tool(state) is True
    state["last_tool_result"]["raw_status"] = "mcp_error"
    assert should_retry_tool(state) is False
