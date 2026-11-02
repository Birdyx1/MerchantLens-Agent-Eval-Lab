import pytest

from merchant_agent.tools.python_sandbox.failure_classification import classify_python_result
from merchant_agent.tools.python_sandbox.python_result import PythonRunResult


@pytest.mark.parametrize("status, category", [
    ("succeeded", "success"),
    ("timeout", "timeout"),
    ("program_error", "program_error"),
    ("infrastructure_error", "dependency_error"),
])
def test_status_mapping_preserves_original_result(status, category):
    result = PythonRunResult(status, "", "", None, 1, False, False)
    assert classify_python_result(result) == category
    assert result.status == status


def test_empty_stdout_is_still_success():
    result = PythonRunResult("succeeded", "", "warning", 0, 1, False, False)
    assert classify_python_result(result) == "success"


def test_unknown_status_is_rejected():
    result = PythonRunResult("unexpected", "", "", None, 1, False, False)
    with pytest.raises(ValueError):
        classify_python_result(result)
