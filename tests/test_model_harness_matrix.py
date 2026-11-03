"""四格对照必须完整、同题，并识别交互效应。"""

import copy

import pytest

from merchant_agent.evaluation.model_harness_matrix import compare_model_harness_matrix


def _batch(model, harness, outcomes):
    return {
        "batch_id": f"{model}-{harness}", "collection": "golden", "status": "completed",
        "model_version": model, "harness_version": harness, "repeats": 2,
        "manifest": [{"task_id": "task-a", "path": "a.json", "sha256": "x"}],
        "items": [{"task_id": "task-a", "repeat_index": index,
                   "trial_id": f"{model}-{harness}-{index}", "score": {"passed": outcome},
                   "metrics": {"overall_success": outcome}}
                  for index, outcome in enumerate(outcomes)],
    }


def _matrix():
    return [_batch("m0", "h0", [False, False]), _batch("m1", "h0", [True, False]),
            _batch("m0", "h1", [False, True]), _batch("m1", "h1", [True, True])]


def test_matrix_reports_model_harness_and_interaction_deltas():
    report = compare_model_harness_matrix(_matrix(), models=("m0", "m1"), harnesses=("h0", "h1"))
    assert [cell["success_rate"] for cell in report["cells"]] == [0.0, 0.5, 0.5, 1.0]
    assert report["model_delta_by_harness"] == {"h0": 0.5, "h1": 0.5}
    assert report["interaction_delta"] == 0.0


@pytest.mark.parametrize("mutation", ["missing_cell", "duplicate_cell", "changed_manifest", "missing_trial"])
def test_matrix_rejects_incomplete_or_unpaired_experiment(mutation):
    batches = _matrix()
    if mutation == "missing_cell":
        batches.pop()
    elif mutation == "duplicate_cell":
        batches[-1] = copy.deepcopy(batches[0])
    elif mutation == "changed_manifest":
        batches[-1]["manifest"][0]["sha256"] = "changed"
    else:
        batches[-1]["items"].pop()
    with pytest.raises(ValueError):
        compare_model_harness_matrix(batches, models=("m0", "m1"), harnesses=("h0", "h1"))
