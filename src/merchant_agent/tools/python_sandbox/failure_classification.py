"""将 Python 执行器状态映射为项目评测类别。"""

from merchant_agent.tools.python_sandbox.python_result import PythonRunResult


_CATEGORY_BY_STATUS = {
    "succeeded": "success",
    "timeout": "timeout",
    "program_error": "program_error",
    "infrastructure_error": "dependency_error",
}


def classify_python_result(result: PythonRunResult) -> str:
    """分类单次执行结果，不修改执行器返回的原始状态。"""
    try:
        return _CATEGORY_BY_STATUS[result.status]
    except KeyError:
        raise ValueError(f"未知 Python 执行状态: {result.status!r}") from None
