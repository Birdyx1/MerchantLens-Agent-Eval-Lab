"""实验复现：记录数据哈希与命令，并校验实验是否可复现。"""

import hashlib
from datetime import datetime, timezone
from pathlib import Path


def sha256_file(path: Path) -> str:
    """流式计算文件哈希，避免一次性读入大文件。"""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(*, experiment: str, data_files: list[Path],
                   commands: list[str], project_root: Path) -> dict:
    """记录实验的数据哈希与复现命令；路径统一存相对于项目根的相对路径。"""
    data = {}
    for path in data_files:
        relative = str(Path(path).resolve().relative_to(project_root.resolve()))
        data[relative] = sha256_file(Path(path))
    return {
        "schema_version": "1.0",
        "experiment": experiment,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "data": data,
        "commands": list(commands),
    }


def verify_manifest(manifest: dict, *, project_root: Path) -> dict:
    """逐文件校验哈希；任何缺失或不一致都判为不可复现。"""
    mismatches = []
    for relative, expected in manifest.get("data", {}).items():
        path = project_root / relative
        if not path.is_file():
            mismatches.append({"path": relative, "reason": "missing"})
        elif sha256_file(path) != expected:
            mismatches.append({"path": relative, "reason": "hash_mismatch"})
    return {
        "reproducible": not mismatches,
        "checked": len(manifest.get("data", {})),
        "mismatches": mismatches,
    }
