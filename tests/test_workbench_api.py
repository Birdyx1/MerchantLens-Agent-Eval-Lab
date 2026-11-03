"""工作台概览必须随实际标注变化，由后端统一计算。"""

import json

import pytest

pytest.importorskip("fastapi")
from merchant_agent.evaluation import api
from merchant_agent.evaluation.workbench import submit_label


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    candidates_path = tmp_path / "candidates.json"
    monkeypatch.setattr(api, "CANDIDATES", candidates_path)
    monkeypatch.setattr(api, "LABELS_ROOT", tmp_path / "labels")
    return candidates_path


def test_missing_candidates_have_empty_summary(workspace):
    response = api.list_candidates()
    assert response["candidates"] == []
    assert response["summary"] == {
        "total": 0,
        "status_counts": {"pending": 0, "one_label": 0, "agreed": 0, "disputed": 0},
        "reviewed": 0,
        "review_progress_pct": 0,
    }


def test_summary_tracks_real_labels_and_preserves_source_fields(workspace):
    items = [
        {"candidate_id": f"t{i}__tool_failure", "task_id": f"t{i}",
         "anomaly_types": ["tool_failure"], "title": f"来自数据源的任务 {i}"}
        for i in range(4)
    ]
    workspace.write_text(json.dumps(items), encoding="utf-8")
    assert api.list_candidates()["summary"]["status_counts"]["pending"] == 4
    for index, judgments in [(1, [True]), (2, [True, True]), (3, [True, False])]:
        for reviewer, judgment in enumerate(judgments):
            submit_label(api._to_candidate(items[index]), reviewer_id=f"r{reviewer}",
                         is_real_badcase=judgment, root_cause="测试根因",
                         fix_direction="测试修复", root=api.LABELS_ROOT)
    response = api.list_candidates()
    assert response["count"] == 4
    assert response["summary"] == {
        "total": 4,
        "status_counts": {"pending": 1, "one_label": 1, "agreed": 1, "disputed": 1},
        "reviewed": 2,
        "review_progress_pct": 50,
    }
    assert [c["label_count"] for c in response["candidates"]] == [0, 1, 2, 2]
    assert response["candidates"][0]["title"] == items[0]["title"]
