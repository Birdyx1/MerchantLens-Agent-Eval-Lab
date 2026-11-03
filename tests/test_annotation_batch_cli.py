"""批量向导跳过已标注题，且不向终端泄露 Oracle 或其他人记录。"""

import json
from pathlib import Path

from merchant_agent.evaluation.annotation_batch_cli import run_annotation_session


ROOT = Path(__file__).resolve().parents[1]


def test_batch_annotation_saves_one_and_skips_existing(tmp_path):
    paths = [ROOT / "fixtures/eval_task_coverage/coverage_store_net_p_001.json",
             ROOT / "fixtures/eval_task_coverage/coverage_store_net_q_001.json"]
    answers = iter(["", "1", "P", "本人逐行核算", "", "2", "Q", "本人逐行核算"])
    output = []
    first = run_annotation_session(paths, reviewer_id="reviewer_test", project_root=ROOT,
                                   records_root=tmp_path, input_fn=lambda _: next(answers),
                                   output_fn=output.append)
    second = run_annotation_session(paths, reviewer_id="reviewer_test", project_root=ROOT,
                                    records_root=tmp_path, input_fn=lambda _: (_ for _ in ()).throw(
                                        AssertionError("已标注题不能再次提问")), output_fn=output.append)
    assert first == {"saved": 2, "skipped": 0}
    assert second == {"saved": 0, "skipped": 2}
    assert "expected_amount_fen" not in "\n".join(output)
    for path in paths:
        record = json.loads((tmp_path / path.stem / "reviewer_test.json").read_text())
        assert record["reviewer_id"] == "reviewer_test"
