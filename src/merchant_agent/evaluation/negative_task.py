"""Negative Task 的独立契约与盲标包，不复用数值题 Oracle。"""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from jsonschema import Draft202012Validator

from merchant_agent.evaluation.negative_input import NegativeInputCase


@dataclass(frozen=True, slots=True)
class NegativeTask:
    task_id: str
    user_request: str
    fixture_path: Path
    fixture_sha256: str
    rubric_sha256: str
    case: NegativeInputCase
    label_status: str


@dataclass(frozen=True, slots=True)
class NegativePacket:
    """标注者仅看到题面与环境摘要，不看到类别、期望行为和禁用工具。"""

    task_id: str
    task_sha256: str
    user_request: str
    fixture_path: Path
    fixture_sha256: str


def negative_task_content_sha256(path: Path) -> str:
    """标签和状态不参与题面摘要，允许仲裁后修正草稿 Oracle。"""
    data = json.loads(path.read_text(encoding="utf-8"))
    data.pop("oracle", None)
    data.pop("label_status", None)
    payload = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_negative_task(path: Path, *, project_root: Path) -> NegativeTask:
    """验证任务结构、数据快照和固定 Rubric 版本。"""
    root = project_root.resolve()
    schema = json.loads((root / "schemas/negative_task.schema.json").read_text(encoding="utf-8"))
    data = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(data)
    relative = Path(data["environment"]["fixture_path"])
    fixture = (root / relative).resolve()
    if relative.is_absolute() or not fixture.is_relative_to(root) or not fixture.is_file():
        raise ValueError("Negative Task 环境路径越界或不存在")
    fixture_sha256 = hashlib.sha256(fixture.read_bytes()).hexdigest()
    if fixture_sha256 != data["environment"]["fixture_sha256"]:
        raise ValueError("Negative Task 环境快照已变化")
    rubric_path = root / "rubrics/negative_input_v1.json"
    rubric_bytes = rubric_path.read_bytes()
    rubric = json.loads(rubric_bytes)
    expected_checks = (("trace_valid", "code"), ("forbidden_tool_absent", "code"),
                       ("behavior_appropriate", "human_or_llm"))
    if (hashlib.sha256(rubric_bytes).hexdigest() != data["rubric_sha256"]
            or rubric.get("rubric_id") != data["rubric_id"]
            or rubric.get("task_type") != data["task_type"]
            or tuple((item.get("id"), item.get("evaluator"))
                     for item in rubric.get("criteria", [])) != expected_checks):
        raise ValueError("Negative Task Rubric 契约或哈希不匹配")
    oracle = data["oracle"]
    case = NegativeInputCase(data["task_id"], oracle["category"], data["input"]["user_request"],
                             oracle["expected_behavior"], tuple(oracle["forbidden_tools"]))
    return NegativeTask(data["task_id"], data["input"]["user_request"], fixture,
                        fixture_sha256, data["rubric_sha256"], case, data["label_status"])


def make_negative_packet(path: Path, *, project_root: Path) -> NegativePacket:
    """读取完整 Task 校验后，只输出标注所需的盲标字段。"""
    task = load_negative_task(path, project_root=project_root)
    return NegativePacket(task.task_id, negative_task_content_sha256(path), task.user_request,
                          task.fixture_path, task.fixture_sha256)
