"""负样例 Task 的独立盲标记录；不展示或复用草稿 Oracle。"""

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from merchant_agent.evaluation.negative_task import make_negative_packet


def submit_negative_annotation(
    task_path: Path, *, project_root: Path, reviewer_id: str, category: str,
    expected_behavior: str, forbidden_tools: list[str], evidence_note: str,
    records_root: Path | None = None,
) -> Path:
    """原子新增一人一题的独立标签，绑定题面与环境版本。"""
    if not re.fullmatch(r"[a-z][a-z0-9_-]{2,63}", reviewer_id):
        raise ValueError("标注者 ID 无效")
    packet = make_negative_packet(task_path, project_root=project_root)
    record = {
        "schema_version": "1.0", "task_id": packet.task_id,
        "task_sha256": packet.task_sha256, "fixture_sha256": packet.fixture_sha256,
        "reviewer_id": reviewer_id, "submitted_at": datetime.now(timezone.utc).isoformat(),
        "judgment": {"category": category, "expected_behavior": expected_behavior,
                     "forbidden_tools": sorted(forbidden_tools), "evidence_note": evidence_note},
    }
    schema = json.loads((project_root / "schemas/negative_annotation.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(record)
    folder = (records_root or project_root / "runs/negative_annotations") / packet.task_id
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    folder.chmod(0o700)
    destination = folder / f"{reviewer_id}.json"
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump(record, output, ensure_ascii=False, sort_keys=True)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    return destination
