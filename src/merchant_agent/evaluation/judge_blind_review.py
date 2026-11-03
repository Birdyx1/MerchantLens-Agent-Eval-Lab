"""真实 Judge 结果的人工盲审入口；标注时不展示模型分数和理由。"""

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


def review_session(result_path: Path, *, reviewer_id: str, project_root: Path = ROOT,
                   input_fn: Callable[[str], str] = input,
                   output_fn: Callable[[str], None] = print) -> dict:
    """逐条盲评并独立落盘；已提交的记录不能覆盖。"""
    root = project_root.resolve()
    source = result_path.resolve()
    if not source.is_relative_to(root / "runs/judge_pilot"):
        raise ValueError("只接受项目内真实 Judge 试点记录")
    if not re.fullmatch(r"[a-z][a-z0-9_-]{2,63}", reviewer_id):
        raise ValueError("标注者 ID 无效")
    result_bytes = source.read_bytes()
    result = json.loads(result_bytes)
    if result.get("status") != "completed" or not result.get("results"):
        raise ValueError("裁判试点尚未完成")
    rubric_bytes = (root / RUBRIC_PATH).read_bytes()
    if hashlib.sha256(rubric_bytes).hexdigest() != result["rubric_sha256"]:
        raise ValueError("Rubric 已变化，不能继续盲审")
    rubric = json.loads(rubric_bytes)
    output_fn(f"评分维度：{rubric['question']}")
    for score, definition in sorted(rubric["scores"].items()):
        output_fn(f"{score} 分：{definition}")
    output_fn("请独立评分；不要打开 Judge 结果、其他人的记录或 Code 分数。")

    destination = root / "runs" / "judge_reviews" / source.parent.name / reviewer_id
    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    saved = skipped = 0
    for item in result["results"]:
        trial_id = item["trial_id"]
        target = destination / f"{trial_id}.json"
        if target.exists():
            skipped += 1
            continue
        trial_path = root / "runs" / "trials" / trial_id / "trial.json"
        trial_bytes = trial_path.read_bytes()
        if hashlib.sha256(trial_bytes).hexdigest() != item["trial_sha256"]:
            raise ValueError(f"Trial 摘要不符：{trial_id}")
        trial = json.loads(trial_bytes)
        if trial["task_id"] != item["task_id"]:
            raise ValueError("Trial 与试点任务身份不一致")
        output_fn(f"\n题目：{item['task_id']}\n回答：{trial['final_answer']}")
        raw_score = input_fn("清晰度分数 [0/1/2]：").strip()
        if raw_score not in {"0", "1", "2"}:
            raise ValueError("分数只能是 0、1、2")
        reason = input_fn("评分理由：").strip()
        if not reason:
            raise ValueError("评分理由不能为空")
        record = {"trial_id": trial_id, "task_id": item["task_id"],
                  "trial_sha256": item["trial_sha256"], "rubric_sha256": result["rubric_sha256"],
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
    return {"saved": saved, "skipped": skipped, "record_directory": str(destination)}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="真实 Judge 结果人工盲审")
    parser.add_argument("--reviewer-id", required=True)
    parser.add_argument("result_path", type=Path)
    args = parser.parse_args(argv)
    print(review_session(args.result_path, reviewer_id=args.reviewer_id))


if __name__ == "__main__":
    main()
