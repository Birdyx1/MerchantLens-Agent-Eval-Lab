import pytest

from merchant_agent.tracing.tool_attempt import ToolAttempt


@pytest.fixture
def attempt_fields():
    return dict(
        trace_id="a" * 32, span_id="b" * 16, parent_span_id="c" * 16,
        tool_name="execute_python", operation_id="operation-1", attempt=2,
        raw_status="infrastructure_error", outcome="dependency_error",
        start_time="2026-11-01T00:00:00Z", end_time="2026-11-01T00:00:01Z",
        duration_ms=1000,
    )


def test_span_preserves_attempt_and_raw_status(attempt_fields):
    span = ToolAttempt(**attempt_fields).to_span()
    assert span["name"] == "tool.execute_python"
    assert span["attributes"]["attempt"] == 2
    assert span["attributes"]["raw_status"] == "infrastructure_error"
    assert span["attributes"]["outcome"] == "dependency_error"
    assert span["parent_span_id"] == "c" * 16


@pytest.mark.parametrize("change", [
    {"attempt": 0}, {"attempt": True}, {"outcome": "unknown"},
    {"duration_ms": -1},
])
def test_invalid_attempt_and_outcome_rejected(attempt_fields, change):
    with pytest.raises(ValueError):
        ToolAttempt(**(attempt_fields | change))
