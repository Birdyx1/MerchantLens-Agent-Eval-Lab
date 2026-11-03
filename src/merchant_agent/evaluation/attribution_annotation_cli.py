"""归因题盲标入口：展示材料（不含 Oracle）、独立提交关键事实答案。

两位真人应分别运行 show/submit，各自使用不同 reviewer_id，不互相看答案。
提交记录独占创建（不可覆盖），保存在 Git 忽略的 runs/attribution_annotations/。
"""

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from merchant_agent.evaluation.task import load_eval_task

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def make_packet(task_path: Path) -> dict:
    """标注者可见材料：题面 + 数据文件路径 + 计算提示，不含关键事实答案。"""
    task = load_eval_task(task_path, project_root=PROJECT_ROOT)
    return {
        "task_id": task.task_id,
        "task_type": task.task_type,
        "user_request": task.user_request,
        "fixture_path": str(task.fixture_path),
        "instruction": "请直接读取 CSV 独立计算答案，不要参考 Task 文件或其他人的结果。",
    }


def submit(task_path: Path, *, reviewer_id: str, answers: list[str],
           evidence_note: str) -> Path:
    """保存一名标注者的独立答案；同一人对同一题不可覆盖。"""
    task = load_eval_task(task_path, project_root=PROJECT_ROOT)
    if not reviewer_id.strip():
        raise ValueError("标注者 ID 不能为空")
    if not answers or any(not str(item).strip() for item in answers):
        raise ValueError("答案不能为空")
    record = {
        "task_id": task.task_id,
        "reviewer_id": reviewer_id,
        "answers": [str(item).strip() for item in answers],
        "evidence_note": evidence_note,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
    }
    folder = PROJECT_ROOT / "runs/attribution_annotations" / task.task_id
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    destination = folder / f"{reviewer_id}.json"
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as output:
        json.dump(record, output, ensure_ascii=False, indent=2)
        output.write("\n")
    return destination


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="归因题双人独立盲标入口")
    commands = parser.add_subparsers(dest="command", required=True)
    show = commands.add_parser("show", help="查看盲标材料（不含答案）")
    show.add_argument("task_path", type=Path)
    submit_parser = commands.add_parser("submit", help="提交独立答案")
    submit_parser.add_argument("task_path", type=Path)
    submit_parser.add_argument("--reviewer-id", required=True)
    submit_parser.add_argument("--answer", action="append", required=True,
                               help="关键事实关键词，可多次传入，如 --answer 零售 --answer 堂食")
    submit_parser.add_argument("--evidence-note", required=True)
    args = parser.parse_args(argv)
    task_path = args.task_path.resolve()
    if args.command == "show":
        print(json.dumps(make_packet(task_path), ensure_ascii=False, indent=2))
        return
    path = submit(task_path, reviewer_id=args.reviewer_id,
                  answers=args.answer, evidence_note=args.evidence_note)
    print(f"标注已保存：{path}")


if __name__ == "__main__":
    main()
