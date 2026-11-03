"""公开基准子集实验：prepare / verify / run / report，不读取或污染 Holdout。"""

import argparse
import asyncio
import hashlib
import json
import math
import random
import sqlite3
import statistics
import time
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from merchant_agent.agent.deepseek_responses_model import DeepSeekResponsesModel
from merchant_agent.agent.siliconflow_chat_model import SiliconFlowChatModel
from merchant_agent.evaluation.base_admission_live import _config as deepseek_config
from merchant_agent.evaluation.benchmark_data import (
    MANIFEST, ROOT, database_path, digest, freeze_subset, json_digest, verify_manifest,
)
from merchant_agent.evaluation.live_multi_tool_selection import _glm_config
from merchant_agent.evaluation.public_benchmark import (
    BFCL_PROMPT, DIRECT_PROMPT, REACT_PROMPT, bfcl_checker, bfcl_messages,
    bird_checker, bird_messages, parse_json, run_readonly_sql, score_bfcl, sql_preview,
)

MAX_OUTPUT = 2048
MAX_TURNS = 5
TOKEN_BUDGET = 24000
TIMEOUT = 90.0


def now():
    return datetime.now(timezone.utc).isoformat()


def save(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(path)


def load_manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def build_schedule(manifest: dict) -> list[dict]:
    slots = []
    for case in manifest["cases"]:
        cells = [("deepseek", "json_prompt"), ("glm", "json_prompt")] if case["benchmark"] == "bfcl" else [
            ("deepseek", "direct"), ("deepseek", "react")]
        for repeat in range(manifest["repeats"]):
            slots.extend({"benchmark": case["benchmark"], "case_id": case["id"],
                          "model": model, "arm": arm, "repeat": repeat}
                         for model, arm in cells)
    random.Random(manifest["seed"]).shuffle(slots)
    return [{"index": index, **slot} for index, slot in enumerate(slots)]


def source_fingerprints() -> dict:
    paths = ["evaluation/benchmark_data.py", "evaluation/public_benchmark.py",
             "evaluation/public_benchmark_cli.py", "agent/openai_responses_model.py",
             "agent/deepseek_responses_model.py", "agent/siliconflow_chat_model.py"]
    return {path: digest((ROOT / "src/merchant_agent" / path).read_bytes()) for path in paths}


def preflight(manifest: dict) -> dict:
    verify_manifest(manifest)
    checker = bird_checker()
    gold = {}
    for case in manifest["cases"]:
        if case["benchmark"] == "bird":
            result = run_readonly_sql(database_path(case["db_id"]), case["oracle"])
            if checker(result["rows"], result["rows"]) != 1:
                raise ValueError("官方 SQL 自检未通过")
            gold[case["id"]] = result
    bfcl_checker()
    return gold


async def run_attempt(slot, case, model, gold, checker, traces: Path):
    row = {**slot, "started_at": now(), "status": "running", "passed": False,
           "input_tokens": 0, "output_tokens": 0, "model_calls": 0, "tool_calls": 0,
           "failure_type": None, "trace": [], "returned_model_ids": []}
    started = time.monotonic()
    messages = bfcl_messages(case) if slot["benchmark"] == "bfcl" else bird_messages(case, slot["arm"])
    row["input_sha256"] = json_digest(messages)
    row["category"] = case.get("category", case.get("difficulty"))
    if "db_id" in case:
        row["db_id"] = case["db_id"]
    row["initial_messages"] = messages.copy()
    save(traces / f"{slot['index']:04d}.json", row)
    try:
        final_sql = None
        for turn in range(1 if slot["arm"] != "react" else MAX_TURNS):
            if time.monotonic() - started > 180:
                row["failure_type"] = "trial_timeout"
                break
            row["model_calls"] += 1
            call_start = time.monotonic()
            response = await model.generate(messages)
            row["input_tokens"] += response.input_tokens
            row["output_tokens"] += response.output_tokens
            row["returned_model_ids"].append(response.model_id)
            row["trace"].append({"type": "model", "turn": turn, "output": response.text,
                                 "input_tokens": response.input_tokens, "output_tokens": response.output_tokens,
                                 "elapsed_seconds": time.monotonic() - call_start})
            save(traces / f"{slot['index']:04d}.json", row)
            if slot["benchmark"] == "bfcl":
                row.update(score_bfcl(case, response.text, checker))
                break
            if row["input_tokens"] + row["output_tokens"] > TOKEN_BUDGET:
                row["failure_type"] = "token_budget"
                break
            try:
                decision = parse_json(response.text)
                if not isinstance(decision, dict) or not isinstance(decision.get("sql"), str):
                    raise ValueError("missing SQL")
                if slot["arm"] == "direct":
                    if set(decision) != {"sql"}:
                        raise ValueError("unexpected fields")
                    final_sql = decision["sql"]
                    break
                if set(decision) != {"action", "sql"} or decision["action"] not in {"query", "finish"}:
                    raise ValueError("invalid action")
                if decision["action"] == "finish":
                    final_sql = decision["sql"]
                    break
            except (ValueError, TypeError):
                row["failure_type"] = "format_error"
                break
            row["tool_calls"] += 1
            try:
                result = await asyncio.to_thread(run_readonly_sql, database_path(case["db_id"]), decision["sql"])
                observation = sql_preview(result)
            except (ValueError, sqlite3.Error) as error:
                observation = {"error_type": type(error).__name__, "error": str(error)}
            row["trace"].append({"type": "tool", "sql": decision["sql"], "observation": observation})
            messages.extend([{"role": "assistant", "content": response.text},
                             {"role": "tool", "content": json.dumps(observation, ensure_ascii=False)}])
            save(traces / f"{slot['index']:04d}.json", row)
        if slot["benchmark"] == "bird":
            row["final_sql"] = final_sql
            if final_sql is not None:
                try:
                    result = await asyncio.to_thread(run_readonly_sql, database_path(case["db_id"]), final_sql)
                    row["passed"] = bool(checker(result["rows"], gold["rows"]))
                    row["failure_type"] = None if row["passed"] else "execution_mismatch"
                    row["result"] = sql_preview(result)
                except (ValueError, sqlite3.Error) as error:
                    row["failure_type"] = "sql_timeout" if "interrupted" in str(error) else "sql_execution_error"
                    row["sql_error"] = str(error)
            elif row["failure_type"] is None:
                row["failure_type"] = "step_budget"
        row["status"] = "scored"
    except Exception as error:
        row["status"] = "error"
        row["failure_type"] = "api_error" if hasattr(error, "response") or isinstance(error, (TimeoutError, ConnectionError)) else "model_or_runner_error"
        row["error_type"] = type(error).__name__
        response = getattr(error, "response", None)
        row["http_status"] = getattr(response, "status_code", None)
    finally:
        row["elapsed_seconds"] = time.monotonic() - started
        row["ended_at"] = now()
        save(traces / f"{slot['index']:04d}.json", row)
    return row


def summarize(rows: list[dict], repeats: int) -> list[dict]:
    cells = defaultdict(list)
    for row in rows:
        cells[(row["benchmark"], row["model"], row["arm"])].append(row)
    summaries = []
    for (benchmark, model, arm), items in sorted(cells.items()):
        grouped = defaultdict(list)
        categories = defaultdict(list)
        for row in items:
            grouped[row["case_id"]].append(row)
            categories[row["category"]].append(row)
        complete = all(len(v) == repeats and {r["repeat"] for r in v} == set(range(repeats)) for v in grouped.values())
        summaries.append({
            "benchmark": benchmark, "model": model, "arm": arm, "trials": len(items),
            "tasks": len(grouped), "successes": sum(r["passed"] for r in items),
            "success_rate": sum(r["passed"] for r in items) / len(items),
            "complete_repeats": complete,
            "all_repeats_success_rate": sum(all(r["passed"] for r in v) for v in grouped.values()) / len(grouped) if complete else None,
            "at_least_one_success_rate": sum(any(r["passed"] for r in v) for v in grouped.values()) / len(grouped) if complete else None,
            "mean_latency_seconds": statistics.mean(r["elapsed_seconds"] for r in items),
            "p95_latency_seconds": sorted(r["elapsed_seconds"] for r in items)[math.ceil(.95 * len(items)) - 1],
            "mean_tokens": statistics.mean(r["input_tokens"] + r["output_tokens"] for r in items if r["status"] == "scored")
                           if any(r["status"] == "scored" for r in items) else None,
            "token_observed_trials": sum(r["status"] == "scored" for r in items),
            "mean_model_calls": statistics.mean(r["model_calls"] for r in items),
            "mean_tool_calls": statistics.mean(r["tool_calls"] for r in items),
            "failures": dict(Counter(r["failure_type"] for r in items if not r["passed"])),
            "categories": {key: {"trials": len(v), "successes": sum(r["passed"] for r in v)} for key, v in sorted(categories.items())},
        })
    return summaries


def paired_deltas(rows: list[dict], *, draws=2000, seed=20261103) -> dict:
    """按题目配对，再按题目 Bootstrap；不把重复运行当独立题目。"""
    output = {}
    for benchmark, left, right in [("bfcl", ("deepseek", "json_prompt"), ("glm", "json_prompt")),
                                    ("bird", ("deepseek", "direct"), ("deepseek", "react"))]:
        cells = defaultdict(dict)
        for row in rows:
            if row["benchmark"] == benchmark:
                cells[(row["model"], row["arm"])][(row["case_id"], row["repeat"])] = row["passed"]
        if not cells[left] or cells[left].keys() != cells[right].keys():
            continue
        by_task = defaultdict(list)
        for (case_id, repeat), passed in cells[left].items():
            by_task[case_id].append(int(cells[right][case_id, repeat]) - int(passed))
        values = [statistics.mean(v) for _, v in sorted(by_task.items())]
        rng = random.Random(seed)
        samples = sorted(statistics.mean(rng.choices(values, k=len(values))) for _ in range(draws))
        output[benchmark] = {"left": "/".join(left), "right": "/".join(right),
                             "right_minus_left": statistics.mean(values),
                             "task_bootstrap_95_interval": [samples[int(.025*(draws-1))], samples[int(.975*(draws-1))]],
                             "tasks": len(values), "seed": seed, "draws": draws}
    return output


def build_report(record: dict, rows: list[dict]) -> str:
    summaries = summarize(rows, record["repeats"]) if rows else []
    lines = ["# BFCL / BIRD 固定子集实验", "", f"运行状态：**{record['status']}**；Run ID：`{record['run_id']}`。", "",
             "这是公开基准子集上的项目适配实验，不能与官方全量排行榜直接比较。BFCL 使用统一 JSON prompting，未使用官方模型 handler 或原生 function calling。BIRD 使用官方 EX 函数（结果行集合完全相等），不增加浮点容差或列名判据。", "",
             "## 冻结协议", "", f"- 清单 SHA256：`{record['manifest_sha256']}`。",
             f"- 每个单元每题重复 {record['repeats']} 次；总计划 {len(record['schedule'])} 个 Trial，已记录 {len(rows)} 个。",
             "- BFCL：simple_python / multiple / parallel / irrelevance 各 5 题，两个模型使用相同题目与提示。",
             "- BIRD：5 个 SQLite 数据库各 4 题；同一 DeepSeek 模型对比 direct / react。公开 evidence 和完整 Schema 均提供，参考 SQL 从不进入模型上下文。",
             f"- temperature=0；每次输出上限 {MAX_OUTPUT}；API 超时 {TIMEOUT:g}s；ReAct 最多 {MAX_TURNS} 次模型调用，累计输入输出预算 {TOKEN_BUDGET}。无自动重试，不删除失败 Trial。",
             "- BIRD 数据库只读；工具预览最多 20 行，但 EX 在完整结果上执行。最终评分查询不算 Agent 工具调用。",
             "- BFCL 原官方 Python checker 函数体保持不变，仅隔离无关 SDK 和 Java/JS 导入；irrelevance 以空调用数组判定。",
             "", "## 结果", "", "| 基准 | 模型 / 配置 | 成功 / Trial | 成功率 | 每题三次均成功 | 平均耗时 s | P95 s | 平均 Token | 模型调用 | 工具调用 |",
             "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for summary in summaries:
        reliability = f"{summary['all_repeats_success_rate']:.1%}" if summary["all_repeats_success_rate"] is not None else "未完成"
        tokens = f"{summary['mean_tokens']:.0f}" if summary['mean_tokens'] is not None else "未知"
        lines.append(f"| {summary['benchmark']} | {summary['model']} / {summary['arm']} | {summary['successes']}/{summary['trials']} | {summary['success_rate']:.1%} | {reliability} | {summary['mean_latency_seconds']:.2f} | {summary['p95_latency_seconds']:.2f} | {tokens} | {summary['mean_model_calls']:.2f} | {summary['mean_tool_calls']:.2f} |")
    lines.extend(["", "## 实际模型标识", "", "```json", json.dumps(record["models"], ensure_ascii=False, indent=2), "```", "", "## 失败分型与分层结果", ""])
    for summary in summaries:
        lines.extend([f"### {summary['benchmark']} / {summary['model']} / {summary['arm']}", "", "```json",
                      json.dumps({"failures": summary["failures"], "categories": summary["categories"],
                                  "token_observed_trials": summary["token_observed_trials"]}, ensure_ascii=False, indent=2), "```", ""])
    lines.extend(["## 配对差值", "", "按题目配对 Bootstrap，区间仅描述当前固定子集的不确定性，不能外推总体。", "", "```json", json.dumps(paired_deltas(rows), ensure_ascii=False, indent=2), "```", "",
                  "## 逐题记录", "", "| 基准 | ID | 模型 / 配置 | 重复 | 通过 | 失败类型 |", "|---|---|---|---:|---|---|"])
    for row in sorted(rows, key=lambda r: (r["benchmark"], r["case_id"], r["model"], r["arm"], r["repeat"])):
        lines.append(f"| {row['benchmark']} | {row['case_id']} | {row['model']} / {row['arm']} | {row['repeat']} | {row['passed']} | {row['failure_type'] or '—'} |")
    lines.extend(["", "## 解释边界", "", "- 20 题/基准，非全量、非随机生产流量，不宣称排行榜成绩或总体显著提升。",
                  "- 三次全成功率是此子集的经验一致性指标，不是对真实成功概率的精确估计。",
                  "- 错误与超时纳入总体成功率分母；未知/失败请求的 Token 用量不可观测，不能当真实零成本。",
                  "- ReAct 比 direct 获得更多调用与工具访问，差异是整体配置差异，不能归因于某一句提示或模型能力。",
                  "- BIRD 仅选五个较小数据库，存在数据库选择偏差；BFCL 只含四种单轮类别，不代表多轮或 Agentic 总分。",
                  "- 此实验使用公开开发题，与项目密封 Holdout 无关；未进行真人双标，不将模型输出视为人工标签。", ""])
    return "\n".join(lines)


async def run_experiment() -> Path:
    manifest = load_manifest()
    gold = preflight(manifest)
    dk, dn = deepseek_config()
    gk, gn = _glm_config()
    models = {
        "deepseek": DeepSeekResponsesModel(dn, dk, timeout_seconds=TIMEOUT, temperature=0.0, max_output_tokens=MAX_OUTPUT),
        "glm": SiliconFlowChatModel(gn, gk, timeout_seconds=TIMEOUT, temperature=0.0,
                                   enable_thinking=False, max_output_tokens=MAX_OUTPUT),
    }
    directory = ROOT / "runs/public_benchmarks" / uuid.uuid4().hex
    directory.mkdir(parents=True, exist_ok=False, mode=0o700)
    schedule = build_schedule(manifest)
    record = {"run_id": directory.name, "status": "running", "started_at": now(),
              "manifest_path": str(MANIFEST.relative_to(ROOT)), "manifest_sha256": digest(MANIFEST.read_bytes()),
              "repeats": manifest["repeats"], "seed": manifest["seed"], "schedule": schedule,
              "models": {"deepseek": {"requested": dn, "interface": "responses", "enable_thinking": "provider default"},
                         "glm": {"requested": gn, "interface": "chat_completions", "enable_thinking": False}},
              "parameters": {"temperature": 0.0, "max_output_tokens": MAX_OUTPUT,
                             "max_react_turns": MAX_TURNS, "token_budget": TOKEN_BUDGET, "api_timeout": TIMEOUT},
              "source_fingerprints": source_fingerprints(),
              "prompt_sha256": {k: digest(v.encode()) for k, v in {"bfcl": BFCL_PROMPT, "direct": DIRECT_PROMPT, "react": REACT_PROMPT}.items()},
              "holdout_used": False, "automatic_retries": 0, "concurrency": 4}
    save(directory / "experiment.json", record)
    cases = {case["id"]: case for case in manifest["cases"]}
    checkers = {"bfcl": bfcl_checker(), "bird": bird_checker()}
    semaphore = asyncio.Semaphore(4)
    rows = []

    async def worker(slot):
        async with semaphore:
            row = await run_attempt(slot, cases[slot["case_id"]], models[slot["model"]],
                                    gold.get(slot["case_id"]), checkers[slot["benchmark"]], directory / "trials")
            rows.append(row)
            save(directory / "results.json", sorted(rows, key=lambda r: r["index"]))
            if len(rows) % 10 == 0 or len(rows) == len(schedule):
                print(f"Trial {len(rows)}/{len(schedule)}，通过 {sum(r['passed'] for r in rows)}", flush=True)

    print(f"Run: {directory}", flush=True)
    try:
        await asyncio.gather(*(worker(slot) for slot in schedule))
        verify_manifest(manifest)
        if source_fingerprints() != record["source_fingerprints"]:
            raise ValueError("运行过程中实验源码发生变化")
        record["status"] = "completed"
    except BaseException as error:
        record["status"] = "failed"
        record["error_type"] = type(error).__name__
        raise
    finally:
        record["ended_at"] = now()
        record["completed_trials"] = len(rows)
        record["summary"] = summarize(rows, manifest["repeats"]) if rows else []
        record["paired_deltas"] = paired_deltas(rows)
        for key in record["models"]:
            record["models"][key]["returned"] = sorted({name for row in rows if row["model"] == key for name in row["returned_model_ids"]})
        save(directory / "experiment.json", record)
        (directory / "report.md").write_text(build_report(record, rows), encoding="utf-8")
    return directory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare", "verify", "restore", "run", "report"])
    parser.add_argument("--run-dir", type=Path)
    args = parser.parse_args()
    if args.command == "prepare":
        manifest = freeze_subset()
        preflight(manifest)
        print(f"已冻结并验证：{MANIFEST}")
    elif args.command in {"verify", "restore"}:
        manifest = load_manifest()
        verify_manifest(manifest, restore=args.command == "restore")
        preflight(manifest)
        print("全部来源哈希及 20 道 BIRD 官方 SQL 自检通过")
    elif args.command == "run":
        print(asyncio.run(run_experiment()))
    else:
        if args.run_dir is None:
            parser.error("report 需要 --run-dir")
        record = json.loads((args.run_dir / "experiment.json").read_text())
        rows = json.loads((args.run_dir / "results.json").read_text())
        (args.run_dir / "report.md").write_text(build_report(record, rows), encoding="utf-8")
        print(args.run_dir / "report.md")


if __name__ == "__main__":
    main()
