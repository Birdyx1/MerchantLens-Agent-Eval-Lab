"""供真实标注者查看盲标材料并提交独立参考标签。"""

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from merchant_agent.evaluation.annotation import make_annotation_packet, submit_task_annotation


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def main(argv: list[str] | None = None) -> None:
    """展示材料或提交标注；不向终端展示 Task Oracle。"""
    parser = argparse.ArgumentParser(description="Task 双人独立标注入口")
    commands = parser.add_subparsers(dest="command", required=True)
    show = commands.add_parser("show", help="查看盲标材料")
    show.add_argument("task_path", type=Path)
    submit = commands.add_parser("submit", help="提交一份独立标注")
    submit.add_argument("task_path", type=Path)
    submit.add_argument("--reviewer-id", required=True)
    submit.add_argument("--amount-fen", type=int)
    submit.add_argument("--store-id")
    submit.add_argument("--unsolvable", action="store_true")
    submit.add_argument("--evidence-note", required=True)
    args = parser.parse_args(argv)
    task_path = args.task_path.resolve()
    if args.command == "show":
        packet = asdict(make_annotation_packet(task_path, project_root=PROJECT_ROOT))
        packet["fixture_path"] = str(packet["fixture_path"])
        print(json.dumps(packet, ensure_ascii=False, indent=2))
        return
    path = submit_task_annotation(
        task_path, project_root=PROJECT_ROOT, reviewer_id=args.reviewer_id,
        solvable=not args.unsolvable, expected_amount_fen=args.amount_fen,
        store_id=args.store_id, evidence_note=args.evidence_note,
    )
    print(f"标注已保存：{path}")


if __name__ == "__main__":
    main()
