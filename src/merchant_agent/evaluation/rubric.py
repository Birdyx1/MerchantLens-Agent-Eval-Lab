"""固定 Rubric 的结构校验与 Task 绑定。"""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from jsonschema import Draft202012Validator

from merchant_agent.evaluation.task import EvalTask


# 代码检查项的证据契约：按题型分组，后续实现 Grader 时保持同名和相同数据来源。
CHECK_CONTRACTS = {
    "store_net": {
        "answer_amount_equals_oracle": (
            "result", frozenset({"trial.final_answer", "task.oracle"})
        ),
        "required_tool_call": (
            "trajectory", frozenset({"trial.trace.tool.get_store_net", "task.oracle"})
        ),
        "answer_matches_tool_result": (
            "trajectory", frozenset({"trial.final_answer", "trial.trace.tool.get_store_net"})
        ),
    },
    "store_net_sum": {
        "total_amount_equals_oracle": (
            "result", frozenset({"trial.final_answer", "task.oracle"})
        ),
        "required_tool_calls": (
            "trajectory", frozenset({"trial.trace.tool.get_store_net", "task.oracle"})
        ),
        "answer_matches_tool_sum": (
            "trajectory", frozenset({"trial.final_answer", "trial.trace.tool.get_store_net"})
        ),
    },
    "nl2sql": {
        "result_set_matches_oracle": (
            "result", frozenset({"trial.trace.tool.run_sql", "task.oracle"})
        ),
        "no_security_rejection": (
            "trajectory", frozenset({"trial.trace.tool.run_sql"})
        ),
        "query_executed": (
            "trajectory", frozenset({"trial.trace.tool.run_sql"})
        ),
    },
    "attribution": {
        "facts_present": (
            "result", frozenset({"trial.final_answer", "task.oracle"})
        ),
        "query_evidence_present": (
            "trajectory", frozenset({"trial.trace.tool.run_sql", "task.oracle"})
        ),
        "no_security_rejection": (
            "trajectory", frozenset({"trial.trace.tool.run_sql"})
        ),
    },
}


@dataclass(frozen=True, slots=True)
class Criterion:
    """单条二元判据；本课只定义，不执行评分。"""

    criterion_id: str
    dimension: str
    question: str
    check_key: str
    evidence_sources: tuple[str, ...]
    evaluator: str
    missing_evidence: str
    severity: str
    pass_example: str
    fail_example: str


@dataclass(frozen=True, slots=True)
class Rubric:
    """由多条独立判据组成的固定评分规范。"""

    rubric_id: str
    task_type: str
    criteria: tuple[Criterion, ...]


def load_rubric(path: Path, *, project_root: Path) -> Rubric:
    """校验 Rubric 的形状、覆盖范围与每条判据的证据来源。"""
    schema = json.loads((project_root / "schemas/rubric.schema.json").read_text(encoding="utf-8"))
    data = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(data)
    if path.stem != data["rubric_id"]:
        raise ValueError("Rubric 文件名与 ID 不一致")
    contracts = CHECK_CONTRACTS.get(data["task_type"])
    if contracts is None:
        raise ValueError("未知题型")
    checks = [item["check_key"] for item in data["criteria"]]
    ids = [item["id"] for item in data["criteria"]]
    if len(set(ids)) != len(ids) or set(checks) != set(contracts) or len(set(checks)) != len(checks):
        raise ValueError("Rubric 判据缺失或重复")
    for item in data["criteria"]:
        dimension, evidence = contracts[item["check_key"]]
        if item["dimension"] != dimension or frozenset(item["evidence_sources"]) != evidence:
            raise ValueError("Rubric 判据的维度或证据来源不匹配")
        if item["pass_example"] == item["fail_example"]:
            raise ValueError("通过与失败示例不能相同")
    return Rubric(
        rubric_id=data["rubric_id"],
        task_type=data["task_type"],
        criteria=tuple(Criterion(
            criterion_id=item["id"], dimension=item["dimension"],
            question=item["question"], check_key=item["check_key"],
            evidence_sources=tuple(item["evidence_sources"]),
            evaluator=item["evaluator"], missing_evidence=item["missing_evidence"],
            severity=item["severity"],
            pass_example=item["pass_example"], fail_example=item["fail_example"],
        ) for item in data["criteria"]),
    )


def load_task_rubric(task: EvalTask, *, project_root: Path) -> Rubric:
    """按 Task 固定的 ID 和文件哈希读取 Rubric，拒绝暗中修改判据。"""
    path = project_root / "rubrics" / f"{task.rubric_id}.json"
    if not path.is_file():
        raise ValueError("Task 引用的 Rubric 不存在")
    if hashlib.sha256(path.read_bytes()).hexdigest() != task.rubric_sha256:
        raise ValueError("Task 引用的 Rubric 哈希不匹配")
    rubric = load_rubric(path, project_root=project_root)
    if rubric.task_type != task.task_type:
        raise ValueError("Rubric 与 Task 类型不匹配")
    return rubric
