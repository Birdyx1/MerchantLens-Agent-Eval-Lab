"""对 negative_input_probe 的 pending_review 结果做 LLM 语义复核（教师代写）。"""

import asyncio
import json
from pathlib import Path

from merchant_agent.agent.deepseek_responses_model import DeepSeekResponsesModel
from merchant_agent.evaluation.base_admission_live import _config
from merchant_agent.evaluation.negative_input import NegativeInputCase
from merchant_agent.evaluation.negative_semantic_judge import judge_negative_input_semantics

ROOT = Path(__file__).resolve().parents[3]
PROBE_ID = "692d58ce42a4492a90e6789bd6d1a1e4"
PROBE = ROOT / "runs" / "negative_input_probe" / PROBE_ID / "results.json"
CASES = ROOT / "fixtures/negative_input_candidates.json"


async def main() -> Path:
    """只对硬约束通过（pending_review）的样本做语义裁判，不改写硬约束结果。"""
    results = json.loads(PROBE.read_text(encoding="utf-8"))
    cases = {item["case_id"]: NegativeInputCase(**item)
             for item in json.loads(CASES.read_text(encoding="utf-8"))}
    key, model_name = _config()
    model = DeepSeekResponsesModel(model_name, key)
    judged = []
    for item in results["items"]:
        if item.get("overall_verdict") != "pending_review":
            continue
        case = cases[item["case_id"]]
        verdict = await judge_negative_input_semantics(case, item.get("final_answer"), model=model)
        judged.append({**item, "semantic": verdict})
        print(f"{item['case_id']}: {verdict['verdict']} — {verdict['reason'][:80]}")
    output = PROBE.parent / "semantic.json"
    output.write_text(json.dumps(judged, ensure_ascii=False, indent=2), encoding="utf-8")
    return output


if __name__ == "__main__":
    print(f"语义复核记录：{asyncio.run(main())}")
