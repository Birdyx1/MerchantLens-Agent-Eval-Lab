"""标注工作台后端 API：候选列表、提交标注、静态前端。"""

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from merchant_agent.evaluation.workbench import Candidate, label_status, submit_label

ROOT = Path(__file__).resolve().parents[3]
CANDIDATES = ROOT / "runs/workbench/candidates.json"
LABELS_ROOT = ROOT / "runs/workbench"
WEB = ROOT / "web"

app = FastAPI(title="标注工作台")


class LabelRequest(BaseModel):
    candidate_id: str
    reviewer_id: str
    is_real_badcase: bool
    root_cause: str
    fix_direction: str


def _load_candidates() -> list[dict]:
    if not CANDIDATES.is_file():
        return []
    return json.loads(CANDIDATES.read_text(encoding="utf-8"))


def _to_candidate(item: dict) -> Candidate:
    return Candidate(item["candidate_id"], item["task_id"], tuple(item["anomaly_types"]), None)


@app.get("/api/candidates")
def list_candidates():
    """返回候选、实时标注状态与全量统计；前端只负责展示。"""
    result = []
    counts = {"pending": 0, "one_label": 0, "agreed": 0, "disputed": 0}
    for item in _load_candidates():
        status = label_status(_to_candidate(item), root=LABELS_ROOT)
        result.append({**item, "status": status["status"], "label_count": status["labels"]})
        counts[status["status"]] += 1
    total = len(result)
    reviewed = counts["agreed"] + counts["disputed"]
    return {
        "candidates": result,
        "count": total,
        "summary": {
            "total": total,
            "status_counts": counts,
            "reviewed": reviewed,
            "review_progress_pct": round(reviewed / total * 100) if total else 0,
        },
    }


@app.post("/api/labels")
def create_label(request: LabelRequest):
    """提交一份标注；同一人对同一候选不可覆盖。"""
    items = {item["candidate_id"]: item for item in _load_candidates()}
    item = items.get(request.candidate_id)
    if item is None:
        raise HTTPException(status_code=404, detail="候选不存在")
    try:
        path = submit_label(
            _to_candidate(item), reviewer_id=request.reviewer_id,
            is_real_badcase=request.is_real_badcase, root_cause=request.root_cause,
            fix_direction=request.fix_direction, root=LABELS_ROOT,
        )
    except FileExistsError:
        raise HTTPException(status_code=409, detail="该候选你已提交过，不可覆盖") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return {"saved": str(path.relative_to(ROOT))}


app.mount("/", StaticFiles(directory=str(WEB), html=True), name="web")
