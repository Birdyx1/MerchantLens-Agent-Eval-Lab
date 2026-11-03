"""新增业务边界草稿与负样例候选必须可加载且不可冒充正式集合。"""

import json
from pathlib import Path

from merchant_agent.evaluation.negative_input import NegativeInputCase
from merchant_agent.evaluation.agreement import validate_resolution_for_task
from merchant_agent.evaluation.reference import store_net_from_fixture
from merchant_agent.evaluation.rubric import load_task_rubric
from merchant_agent.evaluation.task import load_eval_task


ROOT = Path(__file__).resolve().parents[1]


def test_coverage_tasks_have_distinct_business_edges_and_are_drafts():
    paths = sorted((ROOT / "fixtures/eval_task_coverage").glob("*.json"))
    assert len(paths) == 5
    amounts = {}
    for path in paths:
        task = load_eval_task(path, project_root=ROOT)
        load_task_rubric(task, project_root=ROOT)
        assert task.label_status in {"draft", "adjudicated"}
        if task.label_status == "adjudicated":
            validate_resolution_for_task(path, project_root=ROOT)
        assert task.provenance_kind == "synthetic"
        store = task.required_tool_arguments["store_id"]
        assert task.expected_amount_fen == store_net_from_fixture(task.fixture_path, store)
        amounts[store] = task.expected_amount_fen
    assert amounts["N"] == 0
    assert amounts["P"] > max(amounts["L"], amounts["M"])
    assert "Q" in amounts
    assert load_eval_task(ROOT / "fixtures/eval_task_coverage/coverage_store_net_n_001.json",
                          project_root=ROOT).label_status == "draft"


def test_negative_input_candidates_are_only_unreviewed_contracts():
    data = json.loads((ROOT / "fixtures/negative_input_candidates.json").read_text(encoding="utf-8"))
    cases = [NegativeInputCase(**item) for item in data]
    assert len(cases) == 4
    assert len({case.case_id for case in cases}) == len(cases)
    assert {case.category for case in cases} == {"ambiguous", "dirty_input"}
