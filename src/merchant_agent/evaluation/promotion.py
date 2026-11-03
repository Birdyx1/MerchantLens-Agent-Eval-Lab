"""Badcase 入库：把 agreed 的标注候选转成正式 Task。"""

import json
from dataclasses import dataclass
from pathlib import Path

from merchant_agent.evaluation.workbench import Candidate, label_status


@dataclass(frozen=True, slots=True)
class PromotionResult:
    candidate_id: str
    task_id: str
    task_path: Path
    label_status: str


def promote_badcase(candidate: Candidate, *, labels_root: Path, tasks_root: Path,
                    task_type: str, user_request: str, fixture_path: str,
                    fixture_sha256: str, rubric_id: str, rubric_sha256: str) -> PromotionResult:
    """只有 agreed 且两份标注都判为真 badcase 的候选才能入库。"""
    status = label_status(candidate, root=labels_root)
    if status["status"] != "agreed":
        raise ValueError(f"候选状态为 {status['status']}，不是 agreed，不能入库")
    folder = labels_root / candidate.candidate_id
    records = [json.loads(path.read_text(encoding="utf-8"))
               for path in sorted(folder.glob("*.json"))]
    if not records or not all(record["judgment"]["is_real_badcase"] for record in records):
        raise ValueError("标注认为不是真实 badcase，不能入库")
    task_id = f"badcase_{candidate.candidate_id}"
    task = {
        "schema_version": "1.2",
        "task_id": task_id,
        "task_type": task_type,
        "rubric_id": rubric_id,
        "rubric_sha256": rubric_sha256,
        "input": {"user_request": user_request},
        "environment": {"fixture_path": fixture_path, "fixture_sha256": fixture_sha256},
        "provenance": {"kind": "production_badcase", "source_ref": candidate.candidate_id},
        "label_status": "adjudicated",
    }
    tasks_root.mkdir(parents=True, exist_ok=True)
    path = tasks_root / f"{task_id}.json"
    if path.exists():
        raise FileExistsError(f"任务已存在：{path}")
    path.write_text(json.dumps(task, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return PromotionResult(candidate.candidate_id, task_id, path, status["status"])
