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


AMOUNT_PATTERN = re.compile(r"(?<![\d,.-])(\d{1,3}(?:,\d{3})+|\d+)\s*分")
# 多步合计题：答案常同时给出分项与合计，优先取“合计/总计/共计”附近的分金额。
TOTAL_PATTERN = re.compile(r"(?:合计|总计|共计)[^\d]{0,8}(\d{1,3}(?:,\d{3})+|\d+)\s*分")


def _answer_amount(answer: object) -> int | None:
    """只接受一个明确以“分”为单位的金额，避免从多个数字中挑对的。"""
    if not isinstance(answer, str):
        return None
    matches = AMOUNT_PATTERN.findall(answer)
    if len(matches) != 1:
        return None
    # 只删除符合三位分组规范的千位逗号；畸形分组不会被局部截取成另一金额。
    return int(matches[0].replace(",", ""))


def _sum_answer_amount(answer: object) -> int | None:
    """合计题：优先取唯一的“合计”金额；无合计表述时仅在答案只含一个金额时接受。"""
    if not isinstance(answer, str):
        return None
    totals = TOTAL_PATTERN.findall(answer)
    if len(totals) == 1:
        return int(totals[0].replace(",", ""))
    if len(totals) > 1:
        return None
    matches = AMOUNT_PATTERN.findall(answer)
    if len(matches) != 1:
        return None
    return int(matches[0].replace(",", ""))



def _store_net_checks(task, spans, trace_valid, eligible, amount: int | None) -> dict:
    """单门店净收入：一次成功 SQL 调用，金额等于 Oracle 且与工具返回一致。"""
    required_store = task.required_tool_arguments["store_id"]
    calls = [span for span in spans if trace_valid and span["name"] == f"tool.{task.required_tool_name}"
             and span["attributes"].get("store_id") == required_store
             and span["attributes"].get("outcome") == "success"
             and isinstance(span["attributes"].get("result_fen"), int)
             and not isinstance(span["attributes"].get("result_fen"), bool)]
    return {
        "answer_amount_equals_oracle": eligible and amount == task.expected_amount_fen,
        "required_tool_call": eligible and bool(calls),
        "answer_matches_tool_result": eligible and amount is not None and any(
            span["attributes"]["result_fen"] == amount for span in calls
        ),
    }


def _store_net_sum_checks(task, spans, trace_valid, eligible, amount: int | None) -> dict:
    """两门店净收入合计：两次成功 SQL 调用，金额等于两门店之和且与 Oracle 一致。"""
    required_stores = [call["store_id"] for call in task.required_tool_calls]
    calls = [span for span in spans if trace_valid and span["name"] == "tool.get_store_net"
             and span["attributes"].get("store_id") in required_stores
             and span["attributes"].get("outcome") == "success"
             and isinstance(span["attributes"].get("result_fen"), int)
             and not isinstance(span["attributes"].get("result_fen"), bool)]
    # 每个必查门店只取其第一次成功调用的返回值，避免重复调用被重复累加。
    per_store: dict[str, int] = {}
    for span in calls:
        store = span["attributes"]["store_id"]
        if store not in per_store:
            per_store[store] = span["attributes"]["result_fen"]
    all_called = all(store in per_store for store in required_stores)
    total = sum(per_store[store] for store in required_stores) if all_called else None
    return {
        "total_amount_equals_oracle": eligible and amount == task.expected_total_fen,
        "required_tool_calls": eligible and all_called,
        "answer_matches_tool_sum": eligible and amount is not None and total is not None and total == amount,
    }


def _value_matches(actual, expected, tolerance: float) -> bool:
    """数值用容差比较，其余按字符串比较。"""
    if isinstance(actual, (int, float)) and not isinstance(actual, bool) \
            and isinstance(expected, (int, float)) and not isinstance(expected, bool):
        return abs(float(actual) - float(expected)) <= tolerance
    return str(actual) == str(expected)


def _align_rows(result_set: dict, expected_columns: tuple[str, ...]) -> list[list] | None:
    """按 expected_columns 顺序重排结果集的行；列名集合不匹配返回 None。"""
    columns = result_set.get("columns") or []
    rows = result_set.get("rows") or []
    if set(columns) != set(expected_columns):
        return None
    index = [columns.index(name) for name in expected_columns]
    return [[row[i] for i in index] for row in rows]


def _rows_match(actual_rows, expected_rows, tolerance: float) -> bool:
    """行数一致、按值排序后逐格比较；数值容差。"""
    if len(actual_rows) != len(expected_rows):
        return False

    def sort_key(row):
        return tuple(str(value) for value in row)

    for actual, expected in zip(sorted(actual_rows, key=sort_key),
                                sorted(expected_rows, key=sort_key)):
        if len(actual) != len(expected):
            return False
        if not all(_value_matches(a, e, tolerance) for a, e in zip(actual, expected)):
            return False
    return True


def _nl2sql_checks(task, spans, trace_valid: bool, eligible: bool) -> dict:
    """结果导向：结果集匹配 Oracle + 无越权尝试 + 至少一次成功查询。"""
    run_spans = [span for span in spans if trace_valid and span["name"] == "tool.run_sql"]
    security = [span for span in run_spans
                if span["attributes"].get("outcome") == "security_rejected"]
    successful = [span for span in run_spans
                  if span["attributes"].get("outcome") == "success"]
    expected_columns = tuple(task.expected_columns or ())
    matched = None
    # 优先取列集合与 Oracle 匹配的结果；agent 探索时先跑别的查询也不会误判。
    for span in successful:
        result_set = span["attributes"].get("result_set")
        if isinstance(result_set, dict) and set(result_set.get("columns") or []) == set(expected_columns):
            matched = result_set
            break
    if matched is None and successful:
        candidate = successful[-1]["attributes"].get("result_set")
        if isinstance(candidate, dict):
            matched = candidate
    truncated = bool(matched and matched.get("truncated"))
    rows_match = False
    if matched is not None and not truncated:
        aligned = _align_rows(matched, expected_columns)
        if aligned is not None:
            rows_match = _rows_match(aligned, tuple(task.expected_rows or ()),
                                     float(task.column_tolerance))
    return {
        "result_set_matches_oracle": eligible and rows_match,
        "no_security_rejection": eligible and not security,
        "query_executed": eligible and bool(successful),
    }


def evaluate_trial(trial_record: dict, task_path: Path, *, project_root: Path) -> dict:
    """以固定 Task 和 Trace 证据执行确定性判据；缺证据失败。"""
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
    if task.task_type == "store_net":
        amount = _answer_amount(trial_record.get("final_answer"))
        checks = _store_net_checks(task, spans, trace_valid, eligible, amount)
    elif task.task_type == "store_net_sum":
        amount = _sum_answer_amount(trial_record.get("final_answer"))
        checks = _store_net_sum_checks(task, spans, trace_valid, eligible, amount)
    elif task.task_type == "nl2sql":
        amount = None
        checks = _nl2sql_checks(task, spans, trace_valid, eligible)
    else:
        raise ValueError("未知题型")
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
