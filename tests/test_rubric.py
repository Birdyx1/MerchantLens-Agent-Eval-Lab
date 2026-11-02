import json
from pathlib import Path

import pytest

from merchant_agent.evaluation.rubric import load_rubric, load_task_rubric
from merchant_agent.evaluation.task import load_eval_task


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "fixtures/eval_task_examples/store_net_a.json"
RUBRIC = ROOT / "rubrics/store_net_v1.json"


def test_task_uses_frozen_three_check_rubric():
    task = load_eval_task(EXAMPLE, project_root=ROOT)
    rubric = load_task_rubric(task, project_root=ROOT)
    assert rubric.rubric_id == task.rubric_id
    assert rubric.task_type == task.task_type
    assert {item.check_key for item in rubric.criteria} == {
        "answer_amount_equals_oracle", "required_tool_call", "answer_matches_tool_result"
    }
    assert {item.dimension for item in rubric.criteria} == {"result", "trajectory"}
    assert all(item.missing_evidence == "fail" for item in rubric.criteria)


def test_task_rejects_silent_rubric_change(tmp_path):
    (tmp_path / "rubrics").mkdir()
    path = tmp_path / "rubrics/store_net_v1.json"
    path.write_bytes(RUBRIC.read_bytes() + b"\n")
    task = load_eval_task(EXAMPLE, project_root=ROOT)
    with pytest.raises(ValueError, match="哈希不匹配"):
        load_task_rubric(task, project_root=tmp_path)


@pytest.mark.parametrize("mutate", ["duplicate", "wrong_evidence", "same_examples"])
def test_rubric_rejects_unreviewable_criteria(tmp_path, mutate):
    (tmp_path / "schemas").mkdir()
    (tmp_path / "schemas/rubric.schema.json").write_bytes(
        (ROOT / "schemas/rubric.schema.json").read_bytes()
    )
    data = json.loads(RUBRIC.read_text(encoding="utf-8"))
    if mutate == "duplicate":
        data["criteria"][1]["check_key"] = data["criteria"][0]["check_key"]
    elif mutate == "wrong_evidence":
        data["criteria"][1]["evidence_sources"] = ["trial.final_answer"]
    else:
        data["criteria"][1]["fail_example"] = data["criteria"][1]["pass_example"]
    path = tmp_path / "store_net_v1.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError):
        load_rubric(path, project_root=tmp_path)
