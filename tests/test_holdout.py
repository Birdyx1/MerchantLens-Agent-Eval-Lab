import json
from pathlib import Path

import pytest

from merchant_agent.evaluation.agreement import resolve_annotations
from merchant_agent.evaluation.annotation import submit_task_annotation
from merchant_agent.evaluation.holdout import HoldoutStore, prepare_eval_dispatch, reject_eval_prompts_in_fewshot
from merchant_agent.evaluation.sets import EvalCollection, EvalSetStore


ROOT = Path(__file__).resolve().parents[1]


def _project(tmp_path):
    for relative in (
        "schemas/eval_task.schema.json", "schemas/rubric.schema.json",
        "schemas/task_annotation.schema.json", "schemas/adjudication.schema.json",
        "rubrics/store_net_v1.json", "fixtures/business_data/orders.csv",
    ):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / relative).read_bytes())
    return HoldoutStore(tmp_path)


def _source(tmp_path, task_id="holdout_001", request=None):
    data = json.loads((ROOT / "fixtures/eval_task_examples/store_net_a.json").read_text())
    data["task_id"] = task_id
    data["label_status"] = "adjudicated"
    if request is not None:
        data["input"]["user_request"] = request
    source = tmp_path / f"{task_id}.json"
    source.write_text(json.dumps(data, ensure_ascii=False))
    for reviewer in ("simulated_a", "simulated_b"):
        submit_task_annotation(source, project_root=tmp_path, reviewer_id=reviewer,
                               solvable=True, expected_amount_fen=12000, store_id="A",
                               evidence_note="测试模拟身份")
    a = tmp_path / "runs/annotations" / task_id / "simulated_a.json"
    b = tmp_path / "runs/annotations" / task_id / "simulated_b.json"
    resolve_annotations(a, b, source, project_root=tmp_path)
    return source


def test_holdout_is_separate_and_dispatch_marker_is_control_only(tmp_path):
    store = _project(tmp_path)
    target = store.register(_source(tmp_path))
    assert target.is_relative_to(tmp_path / "holdout/tasks")
    assert target.stat().st_mode & 0o777 == 0o600
    dispatch = prepare_eval_dispatch(target, project_root=tmp_path, run_id="run_001")
    assert dispatch.metadata["split"] == "holdout"
    assert dispatch.metadata["traffic_type"] == "evaluation"
    assert "evaluation" not in dispatch.agent_input
    with pytest.raises(ValueError, match="few-shot"):
        reject_eval_prompts_in_fewshot([dispatch.agent_input], project_root=tmp_path)


def test_reject_duplicate_question_across_holdout_and_regular_sets(tmp_path):
    store = _project(tmp_path)
    source = _source(tmp_path)
    store.register(source)
    regular = EvalSetStore(tmp_path)
    duplicated = _source(tmp_path, task_id="golden_001")
    with pytest.raises(ValueError, match="题面"):
        regular.register(duplicated, EvalCollection.GOLDEN)


def test_holdout_rejects_existing_regular_question(tmp_path):
    store = _project(tmp_path)
    regular = EvalSetStore(tmp_path)
    regular.register(_source(tmp_path, task_id="golden_001"), EvalCollection.GOLDEN)
    with pytest.raises(ValueError, match="题面"):
        store.register(_source(tmp_path, task_id="holdout_001"))


def test_fewshot_check_accepts_unregistered_prompt(tmp_path):
    _project(tmp_path)
    reject_eval_prompts_in_fewshot(["业务说明示例，不是评测题"], project_root=tmp_path)
