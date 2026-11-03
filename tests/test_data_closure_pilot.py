"""试点题必须可加载，且盲标包不暴露草稿 Oracle。"""

from pathlib import Path

from merchant_agent.evaluation.annotation import make_annotation_packet
from merchant_agent.evaluation.agreement import validate_resolution_for_task
from merchant_agent.evaluation.reference import store_net_from_fixture
from merchant_agent.evaluation.rubric import load_task_rubric
from merchant_agent.evaluation.task import load_eval_task


ROOT = Path(__file__).resolve().parents[1]


def test_pilot_tasks_are_valid_and_blind_packets_hide_oracle():
    paths = sorted((ROOT / "fixtures/eval_task_pilot").glob("*.json"))
    assert len(paths) == 4
    for path in paths:
        task = load_eval_task(path, project_root=ROOT)
        load_task_rubric(task, project_root=ROOT)
        packet = make_annotation_packet(path, project_root=ROOT)
        assert task.label_status in {"draft", "adjudicated"}
        if task.label_status == "adjudicated":
            validate_resolution_for_task(path, project_root=ROOT)
        assert task.provenance_kind == "synthetic"
        assert packet.task_id == task.task_id
        assert not hasattr(packet, "expected_amount_fen")
        assert task.expected_amount_fen == store_net_from_fixture(
            task.fixture_path, task.required_tool_arguments["store_id"]
        )
