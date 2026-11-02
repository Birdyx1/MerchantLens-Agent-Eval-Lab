import json
from pathlib import Path

import pytest

from merchant_agent.evaluation.sets import EvalCollection, EvalSetStore
from merchant_agent.evaluation.annotation import submit_task_annotation
from merchant_agent.evaluation.agreement import resolve_annotations


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "fixtures/eval_task_examples/store_net_a.json"


def _project(tmp_path):
    (tmp_path / "schemas").mkdir()
    (tmp_path / "schemas/eval_task.schema.json").write_bytes(
        (ROOT / "schemas/eval_task.schema.json").read_bytes()
    )
    (tmp_path / "schemas/rubric.schema.json").write_bytes(
        (ROOT / "schemas/rubric.schema.json").read_bytes()
    )
    for name in ("task_annotation", "adjudication"):
        (tmp_path / f"schemas/{name}.schema.json").write_bytes(
            (ROOT / f"schemas/{name}.schema.json").read_bytes()
        )
    (tmp_path / "rubrics").mkdir()
    (tmp_path / "rubrics/store_net_v1.json").write_bytes(
        (ROOT / "rubrics/store_net_v1.json").read_bytes()
    )
    fixture = tmp_path / "fixtures/business_data/orders.csv"
    fixture.parent.mkdir(parents=True)
    fixture.write_bytes((ROOT / "fixtures/business_data/orders.csv").read_bytes())
    return EvalSetStore(tmp_path)


def _source(tmp_path, **changes):
    data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    data.update(changes)
    source = tmp_path / f"source-{data['task_id']}.json"
    source.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return source


def _consensus(tmp_path, source):
    paths = []
    for reviewer in ("reviewer_a", "reviewer_b"):
        paths.append(submit_task_annotation(
            source, project_root=tmp_path, reviewer_id=reviewer,
            solvable=True, expected_amount_fen=12000, store_id="A",
            evidence_note="测试模拟标签，非真实人工标注",
        ))
    resolve_annotations(*paths, source, project_root=tmp_path)


def test_four_collections_have_separate_physical_directories(tmp_path):
    store = _project(tmp_path)
    paths = {store.task_path(collection, "sample_001").parent for collection in EvalCollection}
    assert len(paths) == 4
    assert all(path.is_dir() for path in paths)


def test_draft_cannot_enter_golden_and_no_partial_file_remains(tmp_path):
    store = _project(tmp_path)
    with pytest.raises(ValueError, match="已仲裁"):
        store.register(_source(tmp_path), EvalCollection.GOLDEN)
    assert list((tmp_path / "eval_sets/golden/tasks").iterdir()) == []


def test_status_flag_without_annotation_evidence_cannot_enter_golden(tmp_path):
    store = _project(tmp_path)
    with pytest.raises(ValueError, match="仲裁记录"):
        store.register(_source(tmp_path, label_status="adjudicated"), EvalCollection.GOLDEN)
    assert list((tmp_path / "eval_sets/golden/tasks").iterdir()) == []


def test_adjudicated_task_cannot_be_copied_across_sets(tmp_path):
    store = _project(tmp_path)
    source = _source(tmp_path, label_status="adjudicated")
    _consensus(tmp_path, source)
    target = store.register(source, EvalCollection.GOLDEN)
    assert target.is_file()
    assert target.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError, match="Task ID"):
        store.register(source, EvalCollection.REGRESSION)
    assert list((tmp_path / "eval_sets/regression/tasks").iterdir()) == []


def test_badcase_and_negative_enforce_provenance(tmp_path):
    store = _project(tmp_path)
    with pytest.raises(ValueError, match="线上回流"):
        store.register(_source(tmp_path), EvalCollection.BADCASE)
    badcase = _source(tmp_path, task_id="badcase_001", provenance={
        "kind": "production_badcase", "source_ref": "synthetic-test-record"
    })
    assert store.register(badcase, EvalCollection.BADCASE).is_file()
    with pytest.raises(ValueError, match="已仲裁"):
        store.register(badcase, EvalCollection.GOLDEN)

    with pytest.raises(ValueError, match="对抗"):
        store.register(_source(tmp_path), EvalCollection.NEGATIVE)
    negative = _source(tmp_path, task_id="negative_001", label_status="adjudicated",
                       provenance={"kind": "adversarial", "source_ref": "synthetic-test-record"})
    _consensus(tmp_path, negative)
    assert store.register(negative, EvalCollection.NEGATIVE).is_file()


def test_task_path_rejects_escape(tmp_path):
    store = _project(tmp_path)
    with pytest.raises(ValueError, match="Task ID"):
        store.task_path(EvalCollection.GOLDEN, "../escape")
