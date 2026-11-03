"""挑战校准只接受与冻结案例、Rubric 摘要一致的双份标签。"""

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from merchant_agent.evaluation.challenge_calibration import calibrate_challenges


ROOT = Path(__file__).resolve().parents[1]


def _fixture(tmp_path: Path) -> Path:
    fixture_path = tmp_path / "fixtures/judge_clarity_challenges_v1.json"
    fixture_path.parent.mkdir(parents=True)
    shutil.copyfile(ROOT / "fixtures/judge_clarity_challenges_v1.json", fixture_path)
    rubric_path = tmp_path / "rubrics/judge_clarity_v1.json"
    rubric_path.parent.mkdir(parents=True)
    shutil.copyfile(ROOT / "rubrics/judge_clarity_v1.json", rubric_path)
    fixture = json.loads(fixture_path.read_text())
    fixture_hash = hashlib.sha256(fixture_path.read_bytes()).hexdigest()
    rubric_hash = hashlib.sha256(rubric_path.read_bytes()).hexdigest()
    result_path = tmp_path / "runs/judge_challenges/run01/results.json"
    result_path.parent.mkdir(parents=True)
    result_path.write_text(json.dumps({"status": "completed", "fixture_id": fixture["fixture_id"],
                                      "fixture_sha256": fixture_hash, "rubric_sha256": rubric_hash,
                                      "results": [{"case_id": case["case_id"],
                                                   "judge": {"status": "scored",
                                                             "trial_id": f"synthetic-{case['case_id']}",
                                                             "rubric_sha256": rubric_hash,
                                                             "score": case["designed_score"]}}
                                                  for case in fixture["cases"]]}))
    for reviewer in ("reviewer_one", "reviewer_two"):
        for case in fixture["cases"]:
            path = tmp_path / "runs/judge_challenge_reviews" / fixture["fixture_id"] / reviewer / f"{case['case_id']}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"fixture_id": fixture["fixture_id"],
                                        "case_id": case["case_id"], "fixture_sha256": fixture_hash,
                                        "rubric_sha256": rubric_hash, "reviewer_id": reviewer,
                                        "score": case["designed_score"], "reason": "按规则判断"}))
    return result_path


def test_challenge_calibration_reports_all_score_layers(tmp_path: Path) -> None:
    report = calibrate_challenges(_fixture(tmp_path), project_root=tmp_path)
    assert report["human_raw_agreement"] == 1.0
    assert report["judge_exact_agreement"] == 1.0
    assert [report["by_reference_score"][str(score)]["n"] for score in (0, 1, 2)] == [2, 2, 2]


def test_challenge_calibration_rejects_wrong_label_hash(tmp_path: Path) -> None:
    source = _fixture(tmp_path)
    path = tmp_path / "runs/judge_challenge_reviews/judge_clarity_challenges_v1/reviewer_two/no_conclusion.json"
    label = json.loads(path.read_text())
    label["fixture_sha256"] = "bad"
    path.write_text(json.dumps(label))
    with pytest.raises(ValueError, match="人工标签无效"):
        calibrate_challenges(source, project_root=tmp_path)
