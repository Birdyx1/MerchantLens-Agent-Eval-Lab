"""人工构造边界挑战的独立盲审入口。"""

import argparse
import hashlib
import json
import os
import re
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from merchant_agent.evaluation.llm_judge import RUBRIC_PATH


ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "fixtures/judge_clarity_challenges_v1.json"


def review_challenges(*, reviewer_id: str, project_root: Path = ROOT,
                      input_fn: Callable[[str], str] = input,
                      output_fn: Callable[[str], None] = print) -> dict:
    """只展示回答和 Rubric，不展示设计分数或 Judge 分数。"""
    root = project_root.resolve()
    if not re.fullmatch(r"[a-z][a-z0-9_-]{2,63}", reviewer_id):
        raise ValueError("标注者 ID 无效")
    fixture_bytes = (root / "fixtures/judge_clarity_challenges_v1.json").read_bytes()
    fixture = json.loads(fixture_bytes)
    if fixture.get("fixture_id") != "judge_clarity_challenges_v1":
        raise ValueError("挑战集身份不一致")
    rubric_bytes = (root / RUBRIC_PATH).read_bytes()
    rubric = json.loads(rubric_bytes)
    output_fn(f"评分维度：{rubric['question']}")
    for score, definition in sorted(rubric["scores"].items()):
        output_fn(f"{score} 分：{definition}")
    output_fn("请独立评分；不要打开挑战集 JSON、Judge 结果或其他人的标注。")
    base = root / "runs/judge_challenge_reviews" / fixture["fixture_id"] / reviewer_id
    base.mkdir(parents=True, exist_ok=True, mode=0o700)
    saved = skipped = 0
    for case in fixture["cases"]:
        target = base / f"{case['case_id']}.json"
        if target.exists():
            try:
                existing = json.loads(target.read_text(encoding="utf-8"))
            except (UnicodeError, json.JSONDecodeError) as exc:
                raise ValueError(f"已有损坏的标注文件，请先人工核对：{target}") from exc
            if (existing.get("case_id") != case["case_id"]
                    or existing.get("reviewer_id") != reviewer_id):
                raise ValueError(f"已有标注身份不一致：{target}")
            skipped += 1
            continue
        output_fn(f"\n案例：{case['case_id']}\n回答：{case['answer']}")
        while True:
            raw_score = input_fn("清晰度分数 [0/1/2]：").strip()
            if raw_score in {"0", "1", "2"}:
                break
            output_fn("请输入单个数字 0、1 或 2；这条记录尚未保存。")
        while True:
            reason = input_fn("评分理由：").strip()
            if not reason:
                output_fn("评分理由不能为空，请重新输入。")
                continue
            try:
                reason.encode("utf-8")
            except UnicodeEncodeError:
                output_fn("理由含终端无法编码的字符，请重新输入。")
                continue
            break
        record = {"fixture_id": fixture["fixture_id"], "case_id": case["case_id"],
                  "fixture_sha256": hashlib.sha256(fixture_bytes).hexdigest(),
                  "rubric_sha256": hashlib.sha256(rubric_bytes).hexdigest(),
                  "reviewer_id": reviewer_id, "score": int(raw_score), "reason": reason,
                  "submitted_at": datetime.now(timezone.utc).isoformat()}
        try:
            payload = (json.dumps(record, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        except UnicodeEncodeError as exc:
            raise ValueError("输入含无法写入 UTF-8 的字符，请重新输入评分理由") from exc
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, "wb") as output:
                output.write(payload)
                output.flush()
                os.fsync(output.fileno())
        except BaseException:
            target.unlink(missing_ok=True)
            raise
        saved += 1
    return {"saved": saved, "skipped": skipped, "record_directory": str(base)}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="清晰度边界挑战独立盲审")
    parser.add_argument("--reviewer-id", required=True)
    args = parser.parse_args(argv)
    print(review_challenges(reviewer_id=args.reviewer_id))


if __name__ == "__main__":
    main()
