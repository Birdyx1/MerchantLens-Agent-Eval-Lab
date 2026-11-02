import json
from pathlib import Path

import pytest

from merchant_agent.evaluation.agreement import (
    Judgment, PairComparison, compare_annotations, resolve_annotations,
    summarize_agreement, validate_resolution_for_task,
)
from merchant_agent.evaluation.annotation import submit_task_annotation
from merchant_agent.evaluation.task import task_content_sha256
from merchant_agent.evaluation.reference import store_net_from_fixture


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "fixtures/eval_task_examples/store_net_a.json"


def test_reference_calculation_uses_frozen_business_rows():
    fixture = ROOT / "fixtures/business_data/orders.csv"
    assert store_net_from_fixture(fixture, "A") == 12000
    assert store_net_from_fixture(fixture, "B") == 8000
    assert store_net_from_fixture(fixture, "missing") is None


def _project(tmp_path):
    (tmp_path / "schemas").mkdir()
    for name in ("eval_task", "task_annotation", "adjudication"):
        (tmp_path / f"schemas/{name}.schema.json").write_bytes(
            (ROOT / f"schemas/{name}.schema.json").read_bytes()
        )
    fixture = tmp_path / "fixtures/business_data/orders.csv"
    fixture.parent.mkdir(parents=True)
    fixture.write_bytes((ROOT / "fixtures/business_data/orders.csv").read_bytes())
    task = tmp_path / "task.json"
    task.write_bytes(EXAMPLE.read_bytes())
    return task


def _submit(task, root, reviewer, amount):
    return submit_task_annotation(
        task, project_root=root, reviewer_id=reviewer, solvable=True,
        expected_amount_fen=amount, store_id="A", evidence_note="模拟独立计算，不是人工证据",
    )


def _promote_status(task):
    data = json.loads(task.read_text(encoding="utf-8"))
    data["label_status"] = "adjudicated"
    task.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def test_consensus_survives_status_change_and_matches_oracle(tmp_path):
    task = _project(tmp_path)
    first = _submit(task, tmp_path, "reviewer_a", 12000)
    second = _submit(task, tmp_path, "reviewer_b", 12000)
    pair = compare_annotations(first, second, project_root=tmp_path)
    assert pair.exact_match
    assert summarize_agreement([pair]).solvable_kappa is None
    digest = task_content_sha256(task)
    resolution = resolve_annotations(first, second, task, project_root=tmp_path)
    assert json.loads(resolution.read_text())["resolution"] == "consensus"
    _promote_status(task)
    assert task_content_sha256(task) == digest
    assert validate_resolution_for_task(task, project_root=tmp_path)["resolution"] == "consensus"


def test_disagreement_requires_third_party_and_reason(tmp_path):
    task = _project(tmp_path)
    first = _submit(task, tmp_path, "reviewer_a", 12000)
    second = _submit(task, tmp_path, "reviewer_b", 11000)
    pair = compare_annotations(first, second, project_root=tmp_path)
    assert pair.disagreement_fields == ("expected_amount_fen",)
    with pytest.raises(ValueError, match="第三名仲裁者"):
        resolve_annotations(first, second, task, project_root=tmp_path)
    with pytest.raises(ValueError, match="第三名仲裁者"):
        resolve_annotations(first, second, task, project_root=tmp_path,
                            adjudicator_id="reviewer_a",
                            final_judgment=Judgment(True, 12000, "A"), rationale="复算")
    resolution = resolve_annotations(
        first, second, task, project_root=tmp_path,
        adjudicator_id="reviewer_c", final_judgment=Judgment(True, 12000, "A"),
        rationale="逐行复算两笔 A 店订单，净额为 12000 分",
    )
    _promote_status(task)
    assert validate_resolution_for_task(task, project_root=tmp_path)["resolution"] == "adjudicated"
    assert resolution.stat().st_mode & 0o777 == 0o600


def test_changed_original_annotation_invalidates_resolution(tmp_path):
    task = _project(tmp_path)
    first = _submit(task, tmp_path, "reviewer_a", 12000)
    second = _submit(task, tmp_path, "reviewer_b", 12000)
    resolve_annotations(first, second, task, project_root=tmp_path)
    _promote_status(task)
    first.write_text(first.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="内容已变化"):
        validate_resolution_for_task(task, project_root=tmp_path)


def test_wrong_consensus_cannot_promote_existing_oracle(tmp_path):
    task = _project(tmp_path)
    first = _submit(task, tmp_path, "reviewer_a", 11000)
    second = _submit(task, tmp_path, "reviewer_b", 11000)
    resolve_annotations(first, second, task, project_root=tmp_path)
    _promote_status(task)
    with pytest.raises(ValueError, match="Oracle 不一致"):
        validate_resolution_for_task(task, project_root=tmp_path)
    data = json.loads(task.read_text(encoding="utf-8"))
    data["oracle"]["expected_amount_fen"] = 11000
    task.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="参考解不一致"):
        validate_resolution_for_task(task, project_root=tmp_path)


def test_binary_kappa_requires_multiple_comparable_tasks():
    pairs = [
        PairComparison("task_001", "a" * 64, "b" * 64, ("reviewer_a", "reviewer_b"),
                       Judgment(True, 12000, "A"), Judgment(True, 12000, "A"), ()),
        PairComparison("task_002", "c" * 64, "d" * 64, ("reviewer_a", "reviewer_b"),
                       Judgment(False, None, None), Judgment(False, None, None), ()),
    ]
    report = summarize_agreement(pairs)
    assert report.exact_match_rate == 1
    assert report.solvable_kappa == 1
    assert report.field_match_rates["expected_amount_fen"] == 1


def test_amount_agreement_is_not_applicable_for_unsolvable_pairs():
    pair = PairComparison(
        "task_001", "a" * 64, "b" * 64, ("reviewer_a", "reviewer_b"),
        Judgment(False, None, None), Judgment(False, None, None), (),
    )
    report = summarize_agreement([pair])
    assert report.field_match_rates["solvable"] == 1
    assert report.field_match_rates["expected_amount_fen"] is None
