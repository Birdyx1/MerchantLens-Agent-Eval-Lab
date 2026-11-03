"""负样例草稿可加载，盲标包不泄露 Oracle，独立标签不可覆盖。"""

import json
from pathlib import Path

import pytest

from merchant_agent.evaluation.negative_annotation import submit_negative_annotation
from merchant_agent.evaluation.negative_annotation_cli import main
from merchant_agent.evaluation.negative_task import load_negative_task, make_negative_packet


ROOT = Path(__file__).resolve().parents[1]
TASKS = sorted((ROOT / "fixtures/negative_task_drafts").glob("*.json"))
CONTEXT = ROOT / "fixtures/negative_task_drafts/negative_context_store_101.json"


def test_negative_drafts_have_distinct_ids_and_blind_packets():
    assert len(TASKS) == 4
    ids = set()
    for path in TASKS:
        task = load_negative_task(path, project_root=ROOT)
        packet = make_negative_packet(path, project_root=ROOT)
        assert task.label_status == "draft"
        assert packet.task_id == task.task_id
        assert not hasattr(packet, "expected_behavior")
        assert not hasattr(packet, "forbidden_tools")
        ids.add(task.task_id)
    assert len(ids) == 4


def test_negative_cli_show_hides_oracle(capsys):
    main(["show", str(TASKS[0])])
    shown = json.loads(capsys.readouterr().out)
    assert set(shown) == {"task_id", "task_sha256", "user_request",
                          "fixture_path", "fixture_sha256"}


def test_negative_annotation_is_independent_and_immutable(tmp_path):
    kwargs = dict(project_root=ROOT, reviewer_id="reviewer_test", category="ambiguous",
                  expected_behavior="clarify", forbidden_tools=["get_store_net"],
                  evidence_note="门店指代缺失，查账前必须澄清", records_root=tmp_path)
    path = submit_negative_annotation(CONTEXT, **kwargs)
    record = json.loads(path.read_text(encoding="utf-8"))
    assert record["task_sha256"] == make_negative_packet(CONTEXT, project_root=ROOT).task_sha256
    with pytest.raises(FileExistsError):
        submit_negative_annotation(CONTEXT, **kwargs)
