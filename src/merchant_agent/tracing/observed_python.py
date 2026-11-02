"""为 MCP Python 工具调用记录执行结果和单次尝试 Trace。"""

import asyncio
import time
import uuid
from dataclasses import asdict
from datetime import datetime, timezone

from merchant_agent.tools.python_sandbox.failure_classification import classify_python_result
from merchant_agent.tools.python_sandbox.python_result import PythonRunResult
from merchant_agent.tracing.tool_attempt import ToolAttempt
from merchant_agent.tracing.tool_failure import ObservedToolFailure
from merchant_agent.tracing.writer import append_span


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_result(content: object) -> PythonRunResult:
    """只接受执行器约定的结构化字段，拒绝损坏的协议结果。"""
    if not isinstance(content, dict):
        raise ObservedToolFailure("execute_python 结构化结果无效", raw_status="protocol_error")
    required = {
        "status", "stdout", "stderr", "exit_code", "duration_ms",
        "stdout_truncated", "stderr_truncated", "oom_killed",
    }
    if not required <= content.keys():
        raise ObservedToolFailure("execute_python 结构化结果缺少字段", raw_status="protocol_error")
    if (not isinstance(content["status"], str)
            or not isinstance(content["stdout"], str)
            or not isinstance(content["stderr"], str)
            or isinstance(content["duration_ms"], bool)
            or not isinstance(content["duration_ms"], int)
            or content["duration_ms"] < 0
            or any(not isinstance(content[key], bool) for key in ("stdout_truncated", "stderr_truncated"))
            or (content["exit_code"] is not None
                and (isinstance(content["exit_code"], bool) or not isinstance(content["exit_code"], int)))
            or (content["oom_killed"] is not None and not isinstance(content["oom_killed"], bool))):
        raise ObservedToolFailure("execute_python 结构化结果字段类型无效", raw_status="protocol_error")
    result = PythonRunResult(**{key: content[key] for key in required})
    try:
        classify_python_result(result)
    except ValueError:
        raise ObservedToolFailure("execute_python 执行状态无效", raw_status="protocol_error") from None
    return result


async def execute_python_observed(
    client,
    code: str,
    timeout_seconds: int,
    *,
    trace_path: str,
    trace_id: str,
    parent_span_id: str,
    operation_id: str,
    attempt: int = 1,
) -> PythonRunResult:
    """调用一次 MCP Python 工具；正常返回包含程序错误或超时的执行结果。"""
    if isinstance(attempt, bool) or not isinstance(attempt, int) or attempt < 1:
        raise ValueError("attempt 必须是从 1 开始的整数")
    if not operation_id:
        raise ValueError("operation_id 不能为空")

    started_at = _utc_now()
    started = time.monotonic()
    raw_status = "not_started"
    outcome = "dependency_error"
    result = None
    error_type = None
    try:
        response = await client.call_tool(
            "execute_python", {"code": code, "timeout_seconds": timeout_seconds}
        )
        if response.is_error:
            raw_status = "mcp_error"
            raise ObservedToolFailure("execute_python 工具调用失败", raw_status=raw_status)
        raw_status = "protocol_error"
        result = _parse_result(response.structured_content)
        raw_status = result.status
        outcome = classify_python_result(result)
        return result
    except asyncio.TimeoutError:
        raw_status = "timeout"
        outcome = "timeout"
        error_type = "TimeoutError"
        raise
    except Exception as exc:
        error_type = type(exc).__name__
        if raw_status == "not_started":
            raw_status = "client_exception"
        raise
    finally:
        span = ToolAttempt(
            trace_id=trace_id,
            span_id=uuid.uuid4().hex[:16],
            parent_span_id=parent_span_id,
            tool_name="execute_python",
            operation_id=operation_id,
            attempt=attempt,
            raw_status=raw_status,
            outcome=outcome,
            start_time=started_at,
            end_time=_utc_now(),
            duration_ms=int((time.monotonic() - started) * 1000),
        ).to_span()
        span["attributes"]["arguments"] = {"code": code, "timeout_seconds": timeout_seconds}
        if result is not None:
            span["attributes"]["python_result"] = asdict(result)
        if error_type is not None:
            span["attributes"]["error_type"] = error_type
        append_span(trace_path, span)
