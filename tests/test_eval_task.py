import json
from pathlib import Path

import pytest
from jsonschema import ValidationError

from merchant_agent.evaluation.task import load_eval_task


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "fixtures/eval_task_examples/store_net_a.json"


def test_example_task_separates_model_input_from_oracle():
    task = load_eval_task(EXAMPLE, project_root=ROOT)
    assert task.agent_input() == "请查询门店 A 的净收入，单位为分。"
    assert "12000" not in task.agent_input()
    assert task.expected_amount_fen == 12000
    assert task.required_tool_name == "get_store_net"
    assert task.required_tool_arguments == {"store_id": "A"}
    with pytest.raises(TypeError):
        task.required_tool_arguments["store_id"] = "B"
    assert task.label_status == "draft"


def test_task_rejects_environment_drift(tmp_path):
    (tmp_path / "schemas").mkdir()
    (tmp_path / "fixtures/business_data").mkdir(parents=True)
    (tmp_path / "schemas/eval_task.schema.json").write_bytes(
        (ROOT / "schemas/eval_task.schema.json").read_bytes()
    )
    fixture = tmp_path / "fixtures/business_data/orders.csv"
    fixture.write_bytes((ROOT / "fixtures/business_data/orders.csv").read_bytes() + b"\n")
    with pytest.raises(ValueError, match="哈希不匹配"):
        load_eval_task(EXAMPLE, project_root=tmp_path)


def test_task_rejects_unreviewed_extra_oracle_field(tmp_path):
    data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    data["oracle"]["hidden_answer"] = "仅评测器知道"
    task_path = tmp_path / "task.json"
    task_path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValidationError):
        load_eval_task(task_path, project_root=ROOT)


def test_task_rejects_fixture_path_escape(tmp_path):
    data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    data["environment"]["fixture_path"] = "../outside.csv"
    task_path = tmp_path / "task.json"
    task_path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="项目内"):
        load_eval_task(task_path, project_root=ROOT)
