"""固定 Rubric 的确定性结果与轨迹裁判。"""

import hashlib
import json
import re
from pathlib import Path

from jsonschema import Draft202012Validator

from merchant_agent.evaluation.rubric import load_task_rubric
from merchant_agent.evaluation.task import load_eval_task
from merchant_agent.tracing.reader import read_spans
from merchant_agent.tracing.validator import validate_trace


AMOUNT_PATTERN = re.compile(r"(?<!\d)(\d+)\s*分")


def _answer_amount(answer: object) -> int | None:
    """只接受一个明确以“分”为单位的金额，避免从多个数字中挑对的。"""
    if not isinstance(answer, str):
        return None
    matches = AMOUNT_PATTERN.findall(answer)
    if len(matches) != 1:
        return None
    return int(matches[0])


def evaluate_trial(trial_record: dict, task_path: Path, *, project_root: Path) -> dict:
    """以固定 Task 和 Trace 证据执行三条 Code 判据；缺证据失败。"""
    root = project_root.resolve()
    task = load_eval_task(task_path, project_root=root)
    rubric = load_task_rubric(task, project_root=root)
    task_digest = hashlib.sha256(task_path.read_bytes()).hexdigest()
    if trial_record.get("task_id") != task.task_id or trial_record.get("task_sha256") != task_digest:
        raise ValueError("Trial 与 Task 快照不一致")
    if trial_record.get("fixture_sha256") != hashlib.sha256(task.fixture_path.read_bytes()).hexdigest():
        raise ValueError("Trial 与环境快照不一致")
    trace_relative = Path(trial_record["trace_path"])
    trace_path = (root / trace_relative).resolve()
    if trace_relative.is_absolute() or not trace_path.is_relative_to(root / "runs" / "trials"):
        raise ValueError("Trial Trace 路径越界")
    trace_valid = False
    spans = []
    if trace_path.is_file() and trial_record.get("trace_sha256") == hashlib.sha256(trace_path.read_bytes()).hexdigest():
        try:
            spans = read_spans(str(trace_path))
            schema = json.loads((root / "schemas" / "span.schema.json").read_text(encoding="utf-8"))
            validator = Draft202012Validator(schema)
            roots = [span for span in spans if span.get("name") == "agent.request" and span.get("parent_span_id") is None]
            trace_valid = (
                bool(spans) and all(validator.is_valid(span) for span in spans)
                and not validate_trace(spans)
                and all(span["trace_id"] == trial_record.get("trace_id") for span in spans)
                and len(roots) == 1
                and roots[0]["attributes"].get("task_id") == task.task_id
                and roots[0]["attributes"].get("termination_reason") == trial_record.get("termination_reason")
                and all(span is roots[0] or span.get("parent_span_id") == roots[0]["span_id"] for span in spans)
            )
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            trace_valid = False
    eligible = trial_record.get("status") == "completed" and trace_valid
    amount = _answer_amount(trial_record.get("final_answer"))
    required_store = task.required_tool_arguments["store_id"]
    calls = [span for span in spans if trace_valid and span["name"] == f"tool.{task.required_tool_name}"
             and span["attributes"].get("store_id") == required_store
             and span["attributes"].get("outcome") == "success"
             and isinstance(span["attributes"].get("result_fen"), int)
             and not isinstance(span["attributes"].get("result_fen"), bool)]
    checks = {
        "answer_amount_equals_oracle": eligible and amount == task.expected_amount_fen,
        "required_tool_call": eligible and bool(calls),
        "answer_matches_tool_result": eligible and amount is not None and any(
            span["attributes"]["result_fen"] == amount for span in calls
        ),
    }
    criteria = [{"id": item.criterion_id, "dimension": item.dimension,
                 "passed": bool(checks[item.check_key]), "check_key": item.check_key}
                for item in rubric.criteria]
    return {
        "trial_id": trial_record.get("trial_id"),
        "task_id": task.task_id,
        "rubric_id": rubric.rubric_id,
        "trace_valid": trace_valid,
        "eligible": eligible,
        "answer_amount_fen": amount,
        "criteria": criteria,
        "passed": all(item["passed"] for item in criteria),
    }
