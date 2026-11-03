"""把 8.1a / 8.2 / 8.3 的真实运行结果汇总，跑安全一票否决门禁（教师代写）。"""

import json
from pathlib import Path

from merchant_agent.evaluation.safety_gate import safety_gate

ROOT = Path(__file__).resolve().parents[3]
NEG_DIR = ROOT / "runs" / "negative_input_probe" / "692d58ce42a4492a90e6789bd6d1a1e4"
INJ = ROOT / "runs" / "prompt_injection_probe" / "15cd6395bfbf4339b70703f9cd0933b7" / "results.json"
DAN = ROOT / "runs" / "dangerous_action_probe" / "b36b563415c347ba8dbd49fd8a2162f6" / "results.json"


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> dict:
    items = []
    negative = _load(NEG_DIR / "results.json")["items"]
    semantic = {row["case_id"]: row.get("semantic")
                for row in _load(NEG_DIR / "semantic.json")}
    for row in negative:
        item = {**row, "source": "8.1a"}
        if semantic.get(row["case_id"]):
            item["semantic"] = semantic[row["case_id"]]
        items.append(item)
    items += [{**row, "source": "8.2"} for row in _load(INJ)["items"]]
    items += [{**row, "source": "8.3"} for row in _load(DAN)["items"]]
    result = safety_gate(items)
    result["by_source"] = {source: sum(1 for item in items if item["source"] == source)
                           for source in ("8.1a", "8.2", "8.3")}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


if __name__ == "__main__":
    main()
