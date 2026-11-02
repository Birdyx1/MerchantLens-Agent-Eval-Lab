import json
from dataclasses import asdict
from pathlib import Path

import pytest
from jsonschema import ValidationError

from merchant_agent.evaluation.annotation import make_annotation_packet, submit_task_annotation
from merchant_agent.evaluation.annotation_cli import main


ROOT = Path(__file__).resolve().parents[1]
TASK_PATH = ROOT / "fixtures/eval_task_examples/store_net_a.json"


def _submit(tmp_path, reviewer_id, **judgment):
    return submit_task_annotation(
        TASK_PATH, project_root=ROOT, reviewer_id=reviewer_id,
        records_root=tmp_path / "annotations", **judgment,
    )


def test_blind_packet_excludes_existing_oracle_and_rubric():
    packet = make_annotation_packet(TASK_PATH, project_root=ROOT)
    visible = asdict(packet)
    assert visible["user_request"] == "请查询门店 A 的净收入，单位为分。"
    assert packet.fixture_path.is_file()
    assert "expected_amount_fen" not in visible
    assert "rubric_id" not in visible
    assert "12000" not in str(visible)


def test_cli_show_exposes_only_blind_packet(capsys):
    main(["show", str(TASK_PATH)])
    visible = capsys.readouterr().out
    assert "门店 A" in visible
    assert "12000" not in visible
    assert "rubric_id" not in visible


def test_two_simulated_reviewers_submit_separate_private_records(tmp_path):
    first = _submit(tmp_path, "reviewer_a", solvable=True, expected_amount_fen=12000,
                    store_id="A", evidence_note="按模拟订单逐行计算")
    second = _submit(tmp_path, "reviewer_b", solvable=True, expected_amount_fen=11000,
                     store_id="A", evidence_note="独立复核时得到另一金额")
    assert first != second
    assert first.parent == second.parent
    assert first.parent.stat().st_mode & 0o777 == 0o700
    assert first.stat().st_mode & 0o777 == 0o600
    first_record = json.loads(first.read_text(encoding="utf-8"))
    second_record = json.loads(second.read_text(encoding="utf-8"))
    assert first_record["task_sha256"] == second_record["task_sha256"]
    assert first_record["judgment"]["expected_amount_fen"] == 12000
    assert second_record["judgment"]["expected_amount_fen"] == 11000
    with pytest.raises(FileExistsError):
        _submit(tmp_path, "reviewer_a", solvable=True, expected_amount_fen=12000,
                store_id="A", evidence_note="试图覆盖原始记录")


def test_unsolvable_annotation_must_not_invent_reference_value(tmp_path):
    with pytest.raises(ValidationError):
        _submit(tmp_path, "reviewer_a", solvable=False, expected_amount_fen=12000,
                store_id="A", evidence_note="题目无法解答")
    assert not (tmp_path / "annotations").exists()


def test_reviewer_id_cannot_escape_private_directory(tmp_path):
    with pytest.raises(ValueError, match="标注者 ID"):
        _submit(tmp_path, "../other", solvable=True, expected_amount_fen=12000,
                store_id="A", evidence_note="合法证据")
