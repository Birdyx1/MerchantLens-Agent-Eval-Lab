"""评测 Task 的加载与模型输入隔离。"""

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from jsonschema import Draft202012Validator


@dataclass(frozen=True, slots=True)
class EvalTask:
    """固定评测任务；Oracle 留在评测侧，不作为模型输入。"""

    task_id: str
    task_type: str
    rubric_id: str
    rubric_sha256: str
    user_request: str
    fixture_path: Path
    expected_amount_fen: int
    required_tool_name: str
    required_tool_arguments: Mapping[str, str]
    provenance_kind: str
    label_status: str

    def agent_input(self) -> str:
        """只返回被测 Agent 可以看到的请求文本。"""
        return self.user_request


def load_eval_task(path: Path, *, project_root: Path) -> EvalTask:
    """校验 Task 结构与环境快照，拒绝漂移的评测数据。"""
    root = project_root.resolve()
    schema_path = root / "schemas" / "eval_task.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    data = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(data)

    relative_fixture = Path(data["environment"]["fixture_path"])
    fixture = (root / relative_fixture).resolve()
    if relative_fixture.is_absolute() or not fixture.is_relative_to(root) or not fixture.is_file():
        raise ValueError("评测环境文件必须位于项目内且实际存在")
    digest = hashlib.sha256(fixture.read_bytes()).hexdigest()
    if digest != data["environment"]["fixture_sha256"]:
        raise ValueError("评测环境文件哈希不匹配")

    oracle = data["oracle"]
    return EvalTask(
        task_id=data["task_id"],
        task_type=data["task_type"],
        rubric_id=data["rubric_id"],
        rubric_sha256=data["rubric_sha256"],
        user_request=data["input"]["user_request"],
        fixture_path=fixture,
        expected_amount_fen=oracle["expected_amount_fen"],
        required_tool_name=oracle["required_tool_call"]["name"],
        required_tool_arguments=MappingProxyType(dict(oracle["required_tool_call"]["arguments"])),
        provenance_kind=data["provenance"]["kind"],
        label_status=data["label_status"],
    )


def task_content_sha256(path: Path) -> str:
    """绑定盲标材料与评分版本；既有 Oracle 和流程状态不参与摘要。"""
    data = json.loads(path.read_text(encoding="utf-8"))
    data.pop("label_status", None)
    data.pop("oracle", None)
    canonical = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def task_exposure_sha256(path: Path) -> str:
    """识别跨集合复用的同一题面；忽略 Task ID、来源、Oracle 和流程状态。"""
    data = json.loads(path.read_text(encoding="utf-8"))
    exposure = {
        "task_type": data["task_type"],
        "rubric_id": data["rubric_id"],
        "rubric_sha256": data["rubric_sha256"],
        "input": data["input"],
        "environment": data["environment"],
    }
    canonical = json.dumps(exposure, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
