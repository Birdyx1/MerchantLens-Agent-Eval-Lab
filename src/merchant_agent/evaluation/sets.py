"""四类评测集的物理目录与入库边界。"""

import fcntl
import os
import re
import uuid
from enum import StrEnum
from pathlib import Path

from merchant_agent.evaluation.task import EvalTask, load_eval_task
from merchant_agent.evaluation.rubric import load_task_rubric
from merchant_agent.evaluation.agreement import validate_resolution_for_task


class EvalCollection(StrEnum):
    """四个互不混用的评测集合。"""

    GOLDEN = "golden"
    REGRESSION = "regression"
    BADCASE = "badcase"
    NEGATIVE = "negative"


class EvalSetStore:
    """以项目目录为边界入库；所有集合共享一次写锁和 ID 检查。"""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root.resolve()
        self.base_dir = self.project_root / "eval_sets"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        for collection in EvalCollection:
            (self.base_dir / collection.value / "tasks").mkdir(parents=True, exist_ok=True)

    def task_path(self, collection: EvalCollection, task_id: str) -> Path:
        """只构造集合内路径，拒绝 ID 引发的路径逃逸。"""
        if not isinstance(collection, EvalCollection) or not re.fullmatch(r"[a-z][a-z0-9_-]{2,63}", task_id):
            raise ValueError("集合或 Task ID 无效")
        return self.base_dir / collection.value / "tasks" / f"{task_id}.json"

    def register(self, source_path: Path, collection: EvalCollection) -> Path:
        """验证来源与标注状态后，原子地新增 Task；已有 ID 不覆盖。"""
        if not isinstance(collection, EvalCollection):
            raise ValueError("未知评测集合")
        raw = source_path.read_bytes()
        lock_fd = os.open(self.base_dir / ".registry.lock", os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            staging = self.base_dir / collection.value / "tasks" / f".staging-{uuid.uuid4().hex}"
            fd = os.open(staging, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            try:
                with os.fdopen(fd, "wb") as output:
                    fd = -1
                    output.write(raw)
                    output.flush()
                    os.fsync(output.fileno())
                # 对写好的快照做校验，避免源文件在读取后变化造成入库竞态。
                task = load_eval_task(staging, project_root=self.project_root)
                load_task_rubric(task, project_root=self.project_root)
                self._check_policy(task, collection)
                if collection != EvalCollection.BADCASE:
                    validate_resolution_for_task(staging, project_root=self.project_root)
                if any(self.task_path(item, task.task_id).exists() for item in EvalCollection):
                    raise FileExistsError("Task ID 已存在于评测集合中")
                target = self.task_path(collection, task.task_id)
                # 硬链接只在内容完整后发布；目标已存在时不会覆盖。
                os.link(staging, target)
                return target
            finally:
                if fd != -1:
                    os.close(fd)
                staging.unlink(missing_ok=True)
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)

    @staticmethod
    def _check_policy(task: EvalTask, collection: EvalCollection) -> None:
        """按集合用途限制来源；Schema 有效不等于有入库资格。"""
        source = task.provenance_kind
        if collection in {EvalCollection.GOLDEN, EvalCollection.REGRESSION}:
            if task.label_status != "adjudicated" or source not in {"synthetic", "human_curated"}:
                raise ValueError("Golden 与 Regression 只接受已仲裁的策划样本")
        elif collection == EvalCollection.BADCASE:
            if source != "production_badcase":
                raise ValueError("Badcase 只接受线上回流来源")
        elif collection == EvalCollection.NEGATIVE:
            if source != "adversarial" or task.label_status != "adjudicated":
                raise ValueError("Negative 只接受已仲裁的对抗样本")
