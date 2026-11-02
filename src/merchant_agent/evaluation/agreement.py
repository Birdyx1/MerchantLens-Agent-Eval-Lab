"""独立标注的一致性检查与显式仲裁。"""

import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import MappingProxyType
from collections.abc import Mapping

from jsonschema import Draft202012Validator, FormatChecker

from merchant_agent.evaluation.task import load_eval_task, task_content_sha256


FIELDS = ("solvable", "expected_amount_fen", "store_id")


@dataclass(frozen=True, slots=True)
class Judgment:
    """一名标注者对参考真值的结构化判断。"""

    solvable: bool
    expected_amount_fen: int | None
    store_id: str | None


@dataclass(frozen=True, slots=True)
class PairComparison:
    """同一题目两份标注的逐字段比较。"""

    task_id: str
    task_sha256: str
    fixture_sha256: str
    reviewer_ids: tuple[str, str]
    left: Judgment
    right: Judgment
    disagreement_fields: tuple[str, ...]

    @property
    def exact_match(self) -> bool:
        return not self.disagreement_fields


@dataclass(frozen=True, slots=True)
class AgreementReport:
    """一批任务的原始一致率；Kappa 不可定义时返回空值。"""

    task_count: int
    exact_match_rate: float
    field_match_rates: Mapping[str, float]
    solvable_kappa: float | None


def _load_annotation(path: Path, project_root: Path) -> dict:
    schema = json.loads((project_root / "schemas/task_annotation.schema.json").read_text(encoding="utf-8"))
    record = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(record)
    return record


def compare_annotations(first_path: Path, second_path: Path, *, project_root: Path) -> PairComparison:
    """先核对题目和环境版本，再比较判断字段；理由差异保留在原记录。"""
    records = sorted(
        (_load_annotation(first_path, project_root), _load_annotation(second_path, project_root)),
        key=lambda item: item["reviewer_id"],
    )
    left, right = records
    if left["reviewer_id"] == right["reviewer_id"]:
        raise ValueError("双人标注必须来自不同 reviewer_id")
    for key in ("task_id", "task_sha256", "fixture_sha256"):
        if left[key] != right[key]:
            raise ValueError("两份标注对应的 Task 或环境版本不同")
    judgments = [Judgment(
        solvable=record["judgment"]["solvable"],
        expected_amount_fen=record["judgment"]["expected_amount_fen"],
        store_id=record["judgment"]["store_id"],
    ) for record in records]
    # 证据说明属于审计材料，不计入真值标签的精确一致率。
    differences = tuple(field for field in FIELDS
                        if getattr(judgments[0], field) != getattr(judgments[1], field))
    return PairComparison(
        task_id=left["task_id"], task_sha256=left["task_sha256"],
        fixture_sha256=left["fixture_sha256"],
        reviewer_ids=(left["reviewer_id"], right["reviewer_id"]),
        left=judgments[0], right=judgments[1], disagreement_fields=differences,
    )


def summarize_agreement(pairs: list[PairComparison]) -> AgreementReport:
    """报告精确一致率及可计算时的二分类可解性 Cohen Kappa。"""
    if not pairs or len({pair.task_id for pair in pairs}) != len(pairs):
        raise ValueError("一致性报告需要非空、Task ID 不重复的配对")
    count = len(pairs)
    field_rates = {
        field: sum(getattr(pair.left, field) == getattr(pair.right, field)
                   for pair in pairs) / count for field in FIELDS
    }
    kappa = None
    if count >= 2 and len({pair.reviewer_ids for pair in pairs}) == 1:
        observed = field_rates["solvable"]
        left_true = sum(pair.left.solvable for pair in pairs) / count
        right_true = sum(pair.right.solvable for pair in pairs) / count
        chance = left_true * right_true + (1 - left_true) * (1 - right_true)
        if chance < 1:
            kappa = (observed - chance) / (1 - chance)
    return AgreementReport(
        task_count=count,
        exact_match_rate=sum(pair.exact_match for pair in pairs) / count,
        field_match_rates=MappingProxyType(field_rates),
        solvable_kappa=kappa,
    )


def resolve_annotations(
    first_path: Path,
    second_path: Path,
    task_path: Path,
    *,
    project_root: Path,
    adjudicator_id: str | None = None,
    final_judgment: Judgment | None = None,
    rationale: str | None = None,
    records_root: Path | None = None,
) -> Path:
    """一致时形成共识记录；分歧时要求独立仲裁者和明确理由。"""
    pair = compare_annotations(first_path, second_path, project_root=project_root)
    task = load_eval_task(task_path, project_root=project_root)
    if pair.task_id != task.task_id or pair.task_sha256 != task_content_sha256(task_path):
        raise ValueError("标注与当前 Task 内容不匹配")
    if pair.fixture_sha256 != hashlib.sha256(task.fixture_path.read_bytes()).hexdigest():
        raise ValueError("标注与当前环境快照不匹配")
    if pair.exact_match:
        if adjudicator_id is not None or final_judgment is not None or rationale is not None:
            raise ValueError("一致的标注无需人工覆盖")
        chosen = pair.left
        resolution = "consensus"
        rationale_text = "两份独立标注的结构化判断一致"
    else:
        if (not isinstance(adjudicator_id, str)
                or not re.fullmatch(r"[a-z][a-z0-9_-]{2,63}", adjudicator_id)
                or adjudicator_id in pair.reviewer_ids
                or not isinstance(final_judgment, Judgment)
                or not isinstance(rationale, str) or not rationale.strip()):
            raise ValueError("分歧必须由第三名仲裁者给出最终判断和理由")
        chosen = final_judgment
        resolution = "adjudicated"
        rationale_text = rationale.strip()
    source_hashes = {
        record["reviewer_id"]: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (first_path, second_path)
        for record in (_load_annotation(path, project_root),)
    }
    record = {
        "schema_version": "1.0", "task_id": pair.task_id,
        "task_sha256": pair.task_sha256, "fixture_sha256": pair.fixture_sha256,
        "reviewer_ids": list(pair.reviewer_ids),
        "source_annotation_sha256": source_hashes,
        "resolution": resolution, "adjudicator_id": adjudicator_id,
        "final_judgment": {
            "solvable": chosen.solvable,
            "expected_amount_fen": chosen.expected_amount_fen,
            "store_id": chosen.store_id,
        },
        "rationale": rationale_text,
        "decided_at": datetime.now(timezone.utc).isoformat(),
    }
    schema = json.loads((project_root / "schemas/adjudication.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(record)
    root = records_root or project_root / "runs/adjudications"
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    root.chmod(0o700)
    destination = root / f"{pair.task_id}.json"
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            fd = -1
            json.dump(record, output, ensure_ascii=False, sort_keys=True)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
    except BaseException:
        if fd != -1:
            os.close(fd)
        destination.unlink(missing_ok=True)
        raise
    return destination


def validate_resolution_for_task(
    task_path: Path,
    *,
    project_root: Path,
    records_root: Path | None = None,
    annotations_root: Path | None = None,
) -> dict:
    """入库前核对仲裁记录、两份原始标注和当前 Oracle。"""
    task = load_eval_task(task_path, project_root=project_root)
    if task.label_status != "adjudicated":
        raise ValueError("Task 尚未标记为已仲裁")
    root = records_root or project_root / "runs/adjudications"
    path = root / f"{task.task_id}.json"
    if not path.is_file():
        raise ValueError("缺少双人标注的仲裁记录")
    record = json.loads(path.read_text(encoding="utf-8"))
    schema = json.loads((project_root / "schemas/adjudication.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(record)
    if (record["task_id"] != task.task_id
            or record["task_sha256"] != task_content_sha256(task_path)
            or record["fixture_sha256"] != hashlib.sha256(task.fixture_path.read_bytes()).hexdigest()):
        raise ValueError("仲裁记录与当前 Task 或环境不匹配")
    source_root = annotations_root or project_root / "runs/annotations"
    first, second = (source_root / task.task_id / f"{reviewer}.json"
                     for reviewer in record["reviewer_ids"])
    if not first.is_file() or not second.is_file():
        raise ValueError("缺少仲裁引用的原始标注")
    pair = compare_annotations(first, second, project_root=project_root)
    if (pair.task_sha256 != record["task_sha256"]
            or pair.fixture_sha256 != record["fixture_sha256"]
            or list(pair.reviewer_ids) != record["reviewer_ids"]):
        raise ValueError("仲裁引用的标注身份或版本不匹配")
    if any(hashlib.sha256(path.read_bytes()).hexdigest()
           != record["source_annotation_sha256"].get(reviewer)
           for reviewer, path in ((pair.reviewer_ids[0], first), (pair.reviewer_ids[1], second))):
        raise ValueError("原始标注内容已变化")
    if record["resolution"] == "consensus":
        if not pair.exact_match or record["adjudicator_id"] is not None:
            raise ValueError("共识记录与原始标注不符")
        final = pair.left
    else:
        arbiter = record["adjudicator_id"]
        if pair.exact_match or not isinstance(arbiter, str) or arbiter in pair.reviewer_ids:
            raise ValueError("分歧仲裁身份或原始分歧无效")
        final = Judgment(**record["final_judgment"])
    if record["final_judgment"] != {
        "solvable": final.solvable,
        "expected_amount_fen": final.expected_amount_fen,
        "store_id": final.store_id,
    }:
        raise ValueError("最终判断与原始共识不一致")
    if (not final.solvable or final.expected_amount_fen != task.expected_amount_fen
            or final.store_id != task.required_tool_arguments["store_id"]):
        raise ValueError("仲裁真值与 Task Oracle 不一致；应修订并重新标注 Task")
    return record
