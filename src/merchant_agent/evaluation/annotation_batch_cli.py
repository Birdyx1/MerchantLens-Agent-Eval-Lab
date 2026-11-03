"""逐题交互提交盲标，减少重复输入命令且不展示参考答案。"""

import argparse
import re
from collections.abc import Callable
from pathlib import Path

from merchant_agent.evaluation.annotation import make_annotation_packet, submit_task_annotation


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def run_annotation_session(
    task_paths: list[Path], *, reviewer_id: str, project_root: Path,
    records_root: Path | None = None, input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
) -> dict:
    """只呈现盲标包；已有记录跳过，提交后不可覆盖。"""
    root = project_root.resolve()
    if not re.fullmatch(r"[a-z][a-z0-9_-]{2,63}", reviewer_id):
        raise ValueError("标注者 ID 无效")
    paths = [path.resolve() for path in task_paths]
    if not paths or len(set(paths)) != len(paths) or any(not path.is_relative_to(root) for path in paths):
        raise ValueError("任务列表必须非空、无重复且位于项目目录内")
    packets = [make_annotation_packet(path, project_root=root) for path in paths]
    record_base = records_root or root / "runs/annotations"
    saved = 0
    skipped = 0
    for path, packet in zip(paths, packets):
        destination = record_base / packet.task_id / f"{reviewer_id}.json"
        if destination.exists():
            output_fn(f"已提交，跳过：{packet.task_id}")
            skipped += 1
            continue
        output_fn(f"\n题目：{packet.task_id}\n问题：{packet.user_request}\n订单文件：{packet.fixture_path}")
        output_fn("请自行查看订单文件并计算；不要打开 Task 草稿 JSON 或其他人的标注。")
        solvable_text = input_fn("是否可解？[Y/n]：").strip().lower()
        if solvable_text not in {"", "y", "n"}:
            raise ValueError("可解性只能填 y 或 n")
        solvable = solvable_text != "n"
        amount = None
        store_id = None
        if solvable:
            amount = int(input_fn("净收入（整数分）：").strip())
            store_id = input_fn("门店 ID：").strip()
        note = input_fn("证据说明：").strip()
        submit_task_annotation(
            path, project_root=root, reviewer_id=reviewer_id, solvable=solvable,
            expected_amount_fen=amount, store_id=store_id, evidence_note=note,
            records_root=record_base,
        )
        output_fn(f"已保存：{packet.task_id}")
        saved += 1
    return {"saved": saved, "skipped": skipped}


def main(argv: list[str] | None = None) -> None:
    """命令行入口；真人身份与独立性仍需流程保证。"""
    parser = argparse.ArgumentParser(description="批量独立盲标向导")
    parser.add_argument("--reviewer-id", required=True)
    parser.add_argument("task_paths", nargs="+", type=Path)
    args = parser.parse_args(argv)
    result = run_annotation_session(args.task_paths, reviewer_id=args.reviewer_id,
                                    project_root=PROJECT_ROOT)
    print(f"本次保存 {result['saved']} 题，跳过已提交 {result['skipped']} 题。")


if __name__ == "__main__":
    main()
