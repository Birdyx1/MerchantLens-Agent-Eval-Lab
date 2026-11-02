import asyncio
from types import SimpleNamespace

import pytest
from mcp import Client

from merchant_agent.mcp_server import create_server
from merchant_agent.tools.python_sandbox.python_result import PythonRunResult
from merchant_agent.tracing.observed_python import execute_python_observed
from merchant_agent.tracing.reader import read_spans


def _call(client, trace_path, attempt=1):
    return execute_python_observed(
        client, "print(1)", 2, trace_path=str(trace_path), trace_id="a" * 32,
        parent_span_id="b" * 16, operation_id="python-1", attempt=attempt,
    )


@pytest.mark.parametrize("status, outcome", [
    ("succeeded", "success"),
    ("timeout", "timeout"),
    ("program_error", "program_error"),
    ("infrastructure_error", "dependency_error"),
])
def test_real_mcp_python_status_mapping(tmp_path, status, outcome):
    expected = PythonRunResult(status, "1\n", "", 0 if status == "succeeded" else None,
                               123, False, False, False)
    calls = []

    def executor(code, timeout_seconds):
        calls.append((code, timeout_seconds))
        return expected

    trace_path = tmp_path / "trace.jsonl"

    async def run():
        async with Client(create_server("unused.db", python_executor=executor)) as client:
            return await _call(client, trace_path)

    result = asyncio.run(run())
    assert result == expected
    assert calls == [("print(1)", 2)]
    (span,) = read_spans(str(trace_path))
    assert span["attributes"]["raw_status"] == status
    assert span["attributes"]["outcome"] == outcome
    assert span["attributes"]["arguments"] == {"code": "print(1)", "timeout_seconds": 2}
    assert span["attributes"]["python_result"]["duration_ms"] == 123


class FakeClient:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error

    async def call_tool(self, name, arguments):
        if self.error:
            raise self.error
        return self.response


@pytest.mark.parametrize("client, outcome, raw_status", [
    (FakeClient(SimpleNamespace(is_error=True, structured_content=None)), "dependency_error", "mcp_error"),
    (FakeClient(SimpleNamespace(is_error=False, structured_content={})), "dependency_error", "protocol_error"),
    (FakeClient(error=asyncio.TimeoutError()), "timeout", "timeout"),
])
def test_failed_mcp_call_keeps_attempt_span(tmp_path, client, outcome, raw_status):
    trace_path = tmp_path / "trace.jsonl"
    with pytest.raises((RuntimeError, asyncio.TimeoutError)):
        asyncio.run(_call(client, trace_path))
    (span,) = read_spans(str(trace_path))
    assert span["attributes"]["outcome"] == outcome
    assert span["attributes"]["raw_status"] == raw_status
    assert "python_result" not in span["attributes"]


def test_unknown_executor_status_is_protocol_error(tmp_path):
    content = dict(status="new_status", stdout="", stderr="", exit_code=None,
                   duration_ms=1, stdout_truncated=False, stderr_truncated=False, oom_killed=None)
    client = FakeClient(SimpleNamespace(is_error=False, structured_content=content))
    trace_path = tmp_path / "trace.jsonl"
    with pytest.raises(RuntimeError, match="执行状态无效"):
        asyncio.run(_call(client, trace_path))
    (span,) = read_spans(str(trace_path))
    assert span["attributes"]["outcome"] == "dependency_error"
    assert span["attributes"]["raw_status"] == "protocol_error"
