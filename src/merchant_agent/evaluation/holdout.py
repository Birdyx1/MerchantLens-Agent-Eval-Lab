"""预留集隔离与评测流量控制面。"""

import fcntl
import os
import uuid
from dataclasses import dataclass
from pathlib import Path

from merchant_agent.evaluation.agreement import validate_resolution_for_task
from merchant_agent.evaluation.rubric import load_task_rubric
from merchant_agent.evaluation.task import load_eval_task, task_exposure_sha256


@dataclass(frozen=True, slots=True)
class EvalDispatch:
    """模型输入与评测元数据分别传递；调用方不得将 metadata 拼进提示词。"""

    agent_input: str
    metadata: dict[str, str]


class HoldoutStore:
    """Holdout 位于常规四集合之外，使用同一把入库锁。"""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root.resolve()
        self.tasks_dir = self.project_root / "holdout" / "tasks"
        self.tasks_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.registry_dir = self.project_root / "eval_sets"
        self.registry_dir.mkdir(parents=True, exist_ok=True)

    def register(self, source_path: Path) -> Path:
        """只收已仲裁策划题，并拒绝与任何常规集合复用 ID 或题面。"""
        raw = source_path.read_bytes()
        lock_fd = os.open(self.registry_dir / ".registry.lock", os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            staging = self.tasks_dir / f".staging-{uuid.uuid4().hex}"
            fd = os.open(staging, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            try:
                with os.fdopen(fd, "wb") as output:
                    output.write(raw)
                    output.flush()
                    os.fsync(output.fileno())
                task = load_eval_task(staging, project_root=self.project_root)
                load_task_rubric(task, project_root=self.project_root)
                if task.label_status != "adjudicated" or task.provenance_kind not in {"synthetic", "human_curated"}:
                    raise ValueError("Holdout 只接受已仲裁的策划样本")
                validate_resolution_for_task(staging, project_root=self.project_root)
                target = self.tasks_dir / f"{task.task_id}.json"
                all_paths = list(self.registry_dir.glob("*/tasks/*.json")) + list(self.tasks_dir.glob("*.json"))
                if any(path.stem == task.task_id for path in all_paths):
                    raise FileExistsError("Task ID 已存在于评测资产中")
                exposure = task_exposure_sha256(staging)
                if any(task_exposure_sha256(path) == exposure for path in all_paths):
                    raise ValueError("题面已存在于评测资产中")
                os.link(staging, target)
                return target
            finally:
                staging.unlink(missing_ok=True)
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)


def prepare_eval_dispatch(task_path: Path, *, project_root: Path, run_id: str) -> EvalDispatch:
    """评测标记仅供运行器记录与隔离，模型只看到 Task 用户请求。"""
    task = load_eval_task(task_path, project_root=project_root)
    root = project_root.resolve()
    path = task_path.resolve()
    holdout_dir = root / "holdout" / "tasks"
    if path.is_relative_to(holdout_dir):
        split = "holdout"
    elif path.is_relative_to(root / "eval_sets"):
        split = path.relative_to(root / "eval_sets").parts[0]
        if split not in {"golden", "regression", "badcase", "negative"}:
            raise ValueError("未知评测集合")
    else:
        raise ValueError("Task 不在已登记评测集合中")
    return EvalDispatch(task.agent_input(), {"traffic_type": "evaluation", "split": split, "task_id": task.task_id, "run_id": run_id})


def reject_eval_prompts_in_fewshot(prompts: list[str], *, project_root: Path) -> None:
    """拒绝把已登记评测题面直接当作 few-shot 示例。"""
    root = project_root.resolve()
    paths = list((root / "eval_sets").glob("*/tasks/*.json"))
    paths.extend((root / "holdout" / "tasks").glob("*.json"))
    registered = {load_eval_task(path, project_root=root).agent_input().strip() for path in paths}
    if any(prompt.strip() in registered for prompt in prompts):
        raise ValueError("few-shot 示例命中已登记评测题面")
