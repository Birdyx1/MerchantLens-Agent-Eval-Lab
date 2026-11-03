"""负样例盲标命令入口：展示题面或提交一份独立标签。"""

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from merchant_agent.evaluation.negative_annotation import submit_negative_annotation
from merchant_agent.evaluation.negative_task import make_negative_packet


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="负样例 Task 独立盲标")
    commands = parser.add_subparsers(dest="command", required=True)
    show = commands.add_parser("show")
    show.add_argument("task_path", type=Path)
    submit = commands.add_parser("submit")
    submit.add_argument("task_path", type=Path)
    submit.add_argument("--reviewer-id", required=True)
    submit.add_argument("--category", choices=["ambiguous", "dirty_input"], required=True)
    submit.add_argument("--expected-behavior", choices=["clarify", "reject"], required=True)
    submit.add_argument("--forbidden-tool", action="append", required=True,
                        choices=["get_store_net", "search_web", "execute_python"])
    submit.add_argument("--evidence-note", required=True)
    args = parser.parse_args(argv)
    path = args.task_path.resolve()
    if args.command == "show":
        packet = asdict(make_negative_packet(path, project_root=PROJECT_ROOT))
        packet["fixture_path"] = str(packet["fixture_path"])
        print(json.dumps(packet, ensure_ascii=False, indent=2))
        return
    destination = submit_negative_annotation(
        path, project_root=PROJECT_ROOT, reviewer_id=args.reviewer_id,
        category=args.category, expected_behavior=args.expected_behavior,
        forbidden_tools=args.forbidden_tool, evidence_note=args.evidence_note,
    )
    print(f"负样例标注已保存：{destination}")


if __name__ == "__main__":
    main()
