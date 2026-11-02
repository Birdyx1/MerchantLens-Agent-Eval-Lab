"""任务参考真值的盲标材料与独立提交记录。"""

import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from merchant_agent.evaluation.task import load_eval_task, task_content_sha256


@dataclass(frozen=True, slots=True)
class AnnotationPacket:
    """标注者可见的题目材料；不包含 Oracle 和 Rubric 示例。"""

    task_id: str
    task_sha256: str
    user_request: str
    fixture_path: Path
    fixture_sha256: str


def make_annotation_packet(task_path: Path, *, project_root: Path) -> AnnotationPacket:
    """从已校验 Task 提取盲标材料，不泄露现有参考答案。"""
    task = load_eval_task(task_path, project_root=project_root)
    return AnnotationPacket(
        task_id=task.task_id,
        task_sha256=task_content_sha256(task_path),
        user_request=task.user_request,
        fixture_path=task.fixture_path,
        fixture_sha256=hashlib.sha256(task.fixture_path.read_bytes()).hexdigest(),
    )


def submit_task_annotation(
    task_path: Path,
    *,
    project_root: Path,
    reviewer_id: str,
    solvable: bool,
    expected_amount_fen: int | None,
    store_id: str | None,
    evidence_note: str,
    records_root: Path | None = None,
) -> Path:
    """保存一名标注者的独立结果，同一人对同一题不可覆盖提交。"""
    packet = make_annotation_packet(task_path, project_root=project_root)
    if not isinstance(reviewer_id, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{2,63}", reviewer_id):
        raise ValueError("标注者 ID 无效")
    record = {
        "schema_version": "1.0",
        "task_id": packet.task_id,
        "task_sha256": packet.task_sha256,
        "fixture_sha256": packet.fixture_sha256,
        "reviewer_id": reviewer_id,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "judgment": {
            "solvable": solvable,
            "expected_amount_fen": expected_amount_fen,
            "store_id": store_id,
            "evidence_note": evidence_note,
        },
    }
    schema_path = project_root / "schemas/task_annotation.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(record)

    root = records_root or project_root / "runs/annotations"
    folder = root / packet.task_id
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    folder.chmod(0o700)
    destination = folder / f"{reviewer_id}.json"
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            fd = -1
            json.dump(record, output, ensure_ascii=False, sort_keys=True)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
    except BaseException:
        if fd != -1:
            os.close(fd)
        destination.unlink(missing_ok=True)
        raise
    return destination
