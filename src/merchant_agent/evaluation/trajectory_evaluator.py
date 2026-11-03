"""在既有结果裁判之上检查端到端行动链的因果顺序。"""

from pathlib import Path

from merchant_agent.evaluation.code_evaluator import evaluate_trial
from merchant_agent.evaluation.task import load_eval_task
from merchant_agent.tracing.reader import read_spans


def _passed(score: dict, check_key: str) -> bool:
    return next(item["passed"] for item in score["criteria"] if item["check_key"] == check_key)


def _store_net_trajectory(trial: dict, task, score: dict, project_root: Path) -> dict:
    """单门店净收入：一次工具调用，前后必须有匹配的规划与结束。"""
    checks = {
        "answer_correct": _passed(score, "answer_amount_equals_oracle"),
        "required_tool_call": _passed(score, "required_tool_call"),
        "answer_grounded": _passed(score, "answer_matches_tool_result"),
        "ordered_evidence_chain": False,
    }
    if score["trace_valid"] and score["eligible"]:
        trace_path = (project_root.resolve() / trial["trace_path"]).resolve()
        spans = read_spans(str(trace_path))
        # JSONL 由同一运行器依次追加；根 Span 最后落盘，不能用它的位置代表开始时间。
        for tool_index, tool_span in enumerate(spans):
            attrs = tool_span.get("attributes", {})
            if (tool_span.get("name") != f"tool.{task.required_tool_name}"
                    or attrs.get("store_id") != task.required_tool_arguments["store_id"]
                    or attrs.get("outcome") != "success"
                    or type(attrs.get("result_fen")) is not int
                    or attrs["result_fen"] != score["answer_amount_fen"]):
                continue
            # 只认紧邻该工具的上一次规划与后续第一次规划，防止借用别的动作的证据。
            previous_plans = [span for span in spans[:tool_index] if span.get("name") == "model.plan"]
            next_plans = [span for span in spans[tool_index + 1:] if span.get("name") == "model.plan"]
            previous = previous_plans[-1].get("attributes", {}) if previous_plans else {}
            following = next_plans[0].get("attributes", {}) if next_plans else {}
            planned = (previous.get("outcome") == "success"
                       and previous.get("action_type") == "tool"
                       and previous.get("selected_tool") == task.required_tool_name
                       and previous.get("tool_arguments") == dict(task.required_tool_arguments))
            finished = following.get("outcome") == "success" and following.get("action_type") == "finish"
            if planned and finished:
                checks["ordered_evidence_chain"] = True
                break
    trajectory_passed = all(checks[key] for key in (
        "required_tool_call", "answer_grounded", "ordered_evidence_chain"
    ))
    return {
        "trial_id": trial.get("trial_id"),
        "task_id": task.task_id,
        "trace_valid": score["trace_valid"],
        "checks": checks,
        "result_passed": checks["answer_correct"],
        "trajectory_passed": trajectory_passed,
        "passed": checks["answer_correct"] and trajectory_passed,
        "failure_mode": ("invalid_trace" if not score["trace_valid"] else
                         "wrong_answer" if not checks["answer_correct"] else
                         "ungrounded_or_wrong_order" if not trajectory_passed else None),
    }


def _store_net_sum_trajectory(trial: dict, task, score: dict, project_root: Path) -> dict:
    """两门店合计：两次工具调用，每个都有匹配的规划，末次调用之后有结束。"""
    checks = {
        "answer_correct": _passed(score, "total_amount_equals_oracle"),
        "required_tool_calls": _passed(score, "required_tool_calls"),
        "answer_grounded": _passed(score, "answer_matches_tool_sum"),
        "ordered_evidence_chain": False,
    }
    if score["trace_valid"] and score["eligible"]:
        trace_path = (project_root.resolve() / trial["trace_path"]).resolve()
        spans = read_spans(str(trace_path))
        required_stores = [call["store_id"] for call in task.required_tool_calls]
        planned_stores: set[str] = set()
        tool_indices = []
        for tool_index, tool_span in enumerate(spans):
            attrs = tool_span.get("attributes", {})
            if (tool_span.get("name") != "tool.get_store_net"
                    or attrs.get("store_id") not in required_stores
                    or attrs.get("outcome") != "success"
                    or type(attrs.get("result_fen")) is not int):
                continue
            tool_indices.append(tool_index)
            previous_plans = [span for span in spans[:tool_index] if span.get("name") == "model.plan"]
            previous = previous_plans[-1].get("attributes", {}) if previous_plans else {}
            if (previous.get("outcome") == "success"
                    and previous.get("action_type") == "tool"
                    and previous.get("selected_tool") == "get_store_net"
                    and previous.get("tool_arguments") == {"store_id": attrs["store_id"]}):
                planned_stores.add(attrs["store_id"])
        all_planned = all(store in planned_stores for store in required_stores)
        finish_after = False
        if tool_indices:
            tail = spans[tool_indices[-1] + 1:]
            finish_after = any(span.get("name") == "model.plan"
                               and span.get("attributes", {}).get("action_type") == "finish"
                               and span.get("attributes", {}).get("outcome") == "success"
                               for span in tail)
        checks["ordered_evidence_chain"] = all_planned and finish_after
    trajectory_passed = all(checks[key] for key in (
        "required_tool_calls", "answer_grounded", "ordered_evidence_chain"
    ))
    return {
        "trial_id": trial.get("trial_id"),
        "task_id": task.task_id,
        "trace_valid": score["trace_valid"],
        "checks": checks,
        "result_passed": checks["answer_correct"],
        "trajectory_passed": trajectory_passed,
        "passed": checks["answer_correct"] and trajectory_passed,
        "failure_mode": ("invalid_trace" if not score["trace_valid"] else
                         "wrong_answer" if not checks["answer_correct"] else
                         "ungrounded_or_wrong_order" if not trajectory_passed else None),
    }


def _nl2sql_trajectory(trial: dict, task, score: dict) -> dict:
    """结果导向题型的轨迹：结果正确、无越权、至少一次成功查询。"""
    checks = {
        "result_correct": _passed(score, "result_set_matches_oracle"),
        "no_security_rejection": _passed(score, "no_security_rejection"),
        "query_executed": _passed(score, "query_executed"),
    }
    trajectory_passed = checks["no_security_rejection"] and checks["query_executed"]
    return {
        "trial_id": trial.get("trial_id"),
        "task_id": task.task_id,
        "trace_valid": score["trace_valid"],
        "checks": checks,
        "result_passed": checks["result_correct"],
        "trajectory_passed": trajectory_passed,
        "passed": checks["result_correct"] and trajectory_passed,
        "failure_mode": ("invalid_trace" if not score["trace_valid"] else
                         "wrong_answer" if not checks["result_correct"] else
                         "security_or_missing_query" if not trajectory_passed else None),
    }


def evaluate_trial_trajectory(trial: dict, task_path: Path, *, project_root: Path) -> dict:
    """复用可信 Trace 门禁；正确答案还必须有先规划、后取证、再结束的链路。"""
    score = evaluate_trial(trial, task_path, project_root=project_root)
    task = load_eval_task(task_path, project_root=project_root)
    if task.task_type == "store_net":
        return _store_net_trajectory(trial, task, score, project_root)
    if task.task_type == "store_net_sum":
        return _store_net_sum_trajectory(trial, task, score, project_root)
    if task.task_type == "nl2sql":
        return _nl2sql_trajectory(trial, task, score)
    raise ValueError("未知题型")
