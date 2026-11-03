"""标注工作台：把异常候选变成可标注、可复核、可仲裁的记录。"""

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Candidate:
    candidate_id: str
    task_id: str
    anomaly_types: tuple[str, ...]
    final_answer: str | None


def load_candidates(findings: list[dict]) -> list[Candidate]:
    """把 9.2 去重后的 finding 转成工作台候选；同一 task+类型组唯一。"""
    candidates = []
    for finding in findings:
        types = tuple(sorted({anomaly["type"] for anomaly in finding["anomalies"]}))
        candidate_id = f"{finding['task_id']}__{'-'.join(types)}"
        candidates.append(Candidate(
            candidate_id=candidate_id,
            task_id=finding["task_id"],
            anomaly_types=types,
            final_answer=finding.get("final_answer"),
        ))
    return candidates


def submit_label(candidate: Candidate, *, reviewer_id: str, is_real_badcase: bool,
                 root_cause: str, fix_direction: str, root: Path) -> Path:
    """保存一份标注；同一人对同一候选不可覆盖。"""
    if not reviewer_id.strip():
        raise ValueError("标注者 ID 无效")
    if not root_cause.strip() or not fix_direction.strip():
        raise ValueError("根因与修复方向不能为空")
    record = {
        "schema_version": "1.0",
        "candidate_id": candidate.candidate_id,
        "task_id": candidate.task_id,
        "anomaly_types": list(candidate.anomaly_types),
        "reviewer_id": reviewer_id,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "judgment": {
            "is_real_badcase": is_real_badcase,
            "root_cause": root_cause,
            "fix_direction": fix_direction,
        },
    }
    folder = root / candidate.candidate_id
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    destination = folder / f"{reviewer_id}.json"
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as output:
        json.dump(record, output, ensure_ascii=False, indent=2)
        output.write("\n")
    return destination


def label_status(candidate: Candidate, *, root: Path) -> dict:
    """返回候选的标注进度：pending / one_label / agreed / disputed。"""
    folder = root / candidate.candidate_id
    labels = {}
    if folder.is_dir():
        for path in sorted(folder.glob("*.json")):
            labels[path.stem] = json.loads(path.read_text(encoding="utf-8"))
    if not labels:
        return {"candidate_id": candidate.candidate_id, "status": "pending", "labels": 0}
    if len(labels) == 1:
        return {"candidate_id": candidate.candidate_id, "status": "one_label", "labels": 1}
    badges = {record["judgment"]["is_real_badcase"] for record in labels.values()}
    status = "agreed" if len(badges) == 1 else "disputed"
    return {"candidate_id": candidate.candidate_id, "status": status, "labels": len(labels)}
