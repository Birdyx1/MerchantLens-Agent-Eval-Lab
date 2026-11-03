"""校准必须拒绝标签串题或摘要不一致。"""

import hashlib
import json
from pathlib import Path

import pytest

from merchant_agent.evaluation.single_judge_calibration import calibrate


def _write(path: Path, value: dict) -> bytes:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(value, ensure_ascii=False).encode()
    path.write_bytes(raw)
    return raw


def _fixture(root: Path) -> Path:
    rubric = b'{"rubric_id":"judge_clarity_v1"}'
    rubric_path = root / "rubrics/judge_clarity_v1.json"
    rubric_path.parent.mkdir(parents=True)
    rubric_path.write_bytes(rubric)
    rubric_hash = hashlib.sha256(rubric).hexdigest()
    trial_id = "trial01"
    trial_raw = _write(root / "runs/trials/trial01/trial.json",
                       {"trial_id": trial_id, "task_id": "task01", "final_answer": "门店 A 净收入 1 分"})
    trial_hash = hashlib.sha256(trial_raw).hexdigest()
    result_path = root / "runs/judge_pilot/run01/results.json"
    _write(result_path, {"status": "completed", "rubric_sha256": rubric_hash,
                         "results": [{"trial_id": trial_id, "task_id": "task01",
                                      "trial_sha256": trial_hash,
                                      "judge": {"status": "scored", "trial_id": trial_id,
                                                "rubric_sha256": rubric_hash, "score": 2}}]})
    for reviewer in ("reviewer_one", "reviewer_two"):
        _write(root / "runs/judge_reviews/run01" / reviewer / "trial01.json",
               {"trial_id": trial_id, "task_id": "task01", "reviewer_id": reviewer,
                "trial_sha256": trial_hash, "rubric_sha256": rubric_hash,
                "score": 2, "reason": "对象、金额与单位清楚"})
    return result_path


def test_calibration_accepts_bound_independent_records(tmp_path: Path) -> None:
    result = calibrate(_fixture(tmp_path), project_root=tmp_path)
    assert result["human_raw_agreement"] == 1.0
    assert result["judge_exact_agreement"] == 1.0
    assert result["score_distribution"] == {"0": 0, "1": 0, "2": 1}


def test_calibration_rejects_tampered_trial(tmp_path: Path) -> None:
    source = _fixture(tmp_path)
    (tmp_path / "runs/trials/trial01/trial.json").write_text("{}")
    with pytest.raises(ValueError, match="Trial 内容发生变化"):
        calibrate(source, project_root=tmp_path)


def test_calibration_rejects_swapped_reviewer_record(tmp_path: Path) -> None:
    source = _fixture(tmp_path)
    path = tmp_path / "runs/judge_reviews/run01/reviewer_two/trial01.json"
    label = json.loads(path.read_text())
    label["reviewer_id"] = "reviewer_one"
    _write(path, label)
    with pytest.raises(ValueError, match="人工标签无效"):
        calibrate(source, project_root=tmp_path)
