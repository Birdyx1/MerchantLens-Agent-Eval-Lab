"""非法终端字符不能留下半写入盲审记录。"""

import shutil
from pathlib import Path

from merchant_agent.evaluation.judge_challenge_review import review_challenges


ROOT = Path(__file__).resolve().parents[1]


def test_bad_input_is_reprompted_without_partial_record(tmp_path: Path) -> None:
    fixture = tmp_path / "fixtures/judge_clarity_challenges_v1.json"
    fixture.parent.mkdir(parents=True)
    shutil.copyfile(ROOT / "fixtures/judge_clarity_challenges_v1.json", fixture)
    rubric = tmp_path / "rubrics/judge_clarity_v1.json"
    rubric.parent.mkdir(parents=True)
    shutil.copyfile(ROOT / "rubrics/judge_clarity_v1.json", rubric)
    answers = iter(("误贴文本", "0", "\ud800", "没有结论",
                    "0", "金额矛盾", "1", "缺少单位", "1", "缺少门店",
                    "2", "完整", "2", "完整且换算一致"))
    output = []
    result = review_challenges(reviewer_id="reviewer_one", project_root=tmp_path,
                               input_fn=lambda _prompt: next(answers), output_fn=output.append)
    assert result["saved"] == 6
    assert len(list((tmp_path / "runs/judge_challenge_reviews").rglob("*.json"))) == 6
    assert any("请输入单个数字" in line for line in output)
    assert any("无法编码" in line for line in output)
