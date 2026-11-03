"""下载固定版本的公开基准，先冻结子集再运行模型；大文件留在 runs。"""

import hashlib
import json
import random
import zipfile
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[3]
CACHE = ROOT / "runs/public_benchmarks/sources"
MANIFEST = ROOT / "fixtures/public_benchmarks/pilot_v1.json"
BFCL_COMMIT = "6ea57973c7a6097fd7c5915698c54c17c5b1b6c8"
BIRD_COMMIT = "1c49a375e76c471e218564da3f4617513d33e371"
BIRD_HF_COMMIT = "5b256b5a9c17478f06ed6912612e9a14d17065c8"
BFCL_PREFIX = "berkeley-function-call-leaderboard/bfcl_eval/"
ZIP_URL = "https://bird-bench.oss-cn-beijing.aliyuncs.com/minidev.zip"
ZIP_ETAG = '"7BEB6DAB11E65F0FDE563E644A1EA319"'
ZIP_SIZE = 800943648
CATEGORIES = ("simple_python", "multiple", "parallel", "irrelevance")
DATABASES = ("california_schools", "student_club", "thrombosis_prediction", "toxicology", "superhero")
SEED = 20261103


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_digest(value) -> str:
    return digest(json.dumps(value, sort_keys=True, ensure_ascii=False).encode())


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def fetch(url: str, target: Path) -> None:
    if target.is_file():
        return
    response = requests.get(url, timeout=120)
    response.raise_for_status()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(response.content)


class RemoteZip:
    """只取 ZIP 目录及指定数据库，拒绝服务端忽略 Range 后返回整个压缩包。"""

    def __init__(self):
        self.pos = 0

    def seek(self, offset, whence=0):
        self.pos = offset if whence == 0 else self.pos + offset if whence == 1 else ZIP_SIZE + offset
        return self.pos

    def tell(self):
        return self.pos

    def seekable(self):
        return True

    def read(self, n=-1):
        n = ZIP_SIZE - self.pos if n < 0 else n
        if not n:
            return b""
        headers = {"Range": f"bytes={self.pos}-{self.pos+n-1}", "If-Match": ZIP_ETAG}
        with requests.get(ZIP_URL, headers=headers, timeout=120, stream=True) as response:
            response.raise_for_status()
            if response.status_code != 206 or response.headers.get("ETag") != ZIP_ETAG:
                raise ValueError("数据库压缩包版本变化或服务器不支持范围读取")
            data = response.content
        if len(data) != n:
            raise ValueError("数据库压缩包范围读取不完整")
        self.pos += len(data)
        return data


def source_specs() -> list[tuple[str, Path]]:
    specs = []
    base = f"https://raw.githubusercontent.com/ShishirPatil/gorilla/{BFCL_COMMIT}/"
    for category in CATEGORIES:
        for folder in (["data"] if category == "irrelevance" else ["data", "data/possible_answer"]):
            path = f"{BFCL_PREFIX}{folder}/BFCL_v4_{category}.json"
            specs.append((base + path, CACHE / "bfcl" / path))
    for path in ["LICENSE", BFCL_PREFIX + "eval_checker/ast_eval/ast_checker.py"]:
        specs.append((base + path, CACHE / "bfcl" / path))
    base = f"https://raw.githubusercontent.com/bird-bench/mini_dev/{BIRD_COMMIT}/"
    for path in ["README.md", "evaluation/evaluation_ex.py"]:
        specs.append((base + path, CACHE / "bird" / path))
    base = f"https://huggingface.co/datasets/birdsql/bird_mini_dev/resolve/{BIRD_HF_COMMIT}/"
    for path in ["data/mini_dev_sqlite.jsonl", "data/manifest.json", "README.md"]:
        specs.append((base + path, CACHE / "bird_hf" / path))
    return specs


def database_path(db_id: str) -> Path:
    if db_id not in DATABASES:
        raise ValueError("数据库不在冻结清单中")
    return CACHE / "bird_databases" / db_id / f"{db_id}.sqlite"


def freeze_subset() -> dict:
    """固定随机种子；BFCL 每类别 5 题，BIRD 每数据库按难度轮转抽取 4 题。"""
    if MANIFEST.exists():
        raise FileExistsError("实验清单已冻结；复现请使用 restore，不得覆盖重抽")
    specs = source_specs()
    for url, path in specs:
        fetch(url, path)
    with zipfile.ZipFile(RemoteZip()) as archive:
        for db_id in DATABASES:
            path = database_path(db_id)
            member = f"minidev/MINIDEV/dev_databases/{db_id}/{db_id}.sqlite"
            if not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(archive.read(member))
            specs.append((ZIP_URL + "#" + member, path))
    selected = []
    for category in CATEGORIES:
        rows = load_jsonl(CACHE / "bfcl" / f"{BFCL_PREFIX}data/BFCL_v4_{category}.json")
        answers = {} if category == "irrelevance" else {
            row["id"]: row["ground_truth"] for row in load_jsonl(
                CACHE / "bfcl" / f"{BFCL_PREFIX}data/possible_answer/BFCL_v4_{category}.json")}
        for row in random.Random(f"{SEED}:{category}").sample(sorted(rows, key=lambda r: r["id"]), 5):
            selected.append({"benchmark": "bfcl", "id": row["id"], "category": category,
                             "input": {"question": row["question"], "function": row["function"]},
                             "oracle": answers.get(row["id"], [])})
    rows = load_jsonl(CACHE / "bird_hf/data/mini_dev_sqlite.jsonl")
    for db_id in DATABASES:
        groups = {}
        for difficulty in ("simple", "moderate", "challenging"):
            group = sorted((r for r in rows if r["db_id"] == db_id and r["difficulty"] == difficulty),
                           key=lambda r: r["question_id"])
            random.Random(f"{SEED}:{db_id}:{difficulty}").shuffle(group)
            groups[difficulty] = group
        chosen = []
        while len(chosen) < 4:
            for group in groups.values():
                if group and len(chosen) < 4:
                    chosen.append(group.pop())
            if not any(groups.values()) and len(chosen) < 4:
                raise ValueError("数据库题量不足")
        for row in chosen:
            selected.append({"benchmark": "bird", "id": f"bird_{row['question_id']}",
                             "db_id": db_id, "difficulty": row["difficulty"],
                             "input": {"question": row["question"], "evidence": row["evidence"]},
                             "oracle": row["SQL"]})
    manifest = {
        "version": "1.0", "seed": SEED, "repeats": 3,
        "scope": "固定子集与项目 JSON prompting 适配；非官方全量榜单分数",
        "bfcl_commit": BFCL_COMMIT, "bird_scorer_commit": BIRD_COMMIT,
        "bird_data_commit": BIRD_HF_COMMIT, "zip_etag": ZIP_ETAG,
        "sampling": "BFCL 四类别各随机 5 题；BIRD 五库各 4 题，按 simple/moderate/challenging 轮转抽样；均在模型运行前固定",
        "sources": [{"url": url, "path": str(path.relative_to(ROOT)), "sha256": digest(path.read_bytes())}
                    for url, path in specs],
        "cases": selected,
    }
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST.open("x", encoding="utf-8") as output:
        json.dump(manifest, output, ensure_ascii=False, indent=2)
        output.write("\n")
    return manifest


def verify_manifest(manifest: dict, *, restore=False) -> None:
    """复现时重新下载缺失文件；任何已有文件的哈希不匹配都拒绝继续。"""
    for source in manifest["sources"]:
        path = (ROOT / source["path"]).resolve()
        if not path.is_relative_to(CACHE.resolve()):
            raise ValueError("源文件路径越界")
        if not path.exists() and restore:
            url, marker, member = source["url"].partition("#")
            if marker:
                with zipfile.ZipFile(RemoteZip()) as archive:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(archive.read(member))
            else:
                fetch(url, path)
        if not path.is_file() or digest(path.read_bytes()) != source["sha256"]:
            raise ValueError(f"来源文件缺失或哈希变化：{source['path']}")
