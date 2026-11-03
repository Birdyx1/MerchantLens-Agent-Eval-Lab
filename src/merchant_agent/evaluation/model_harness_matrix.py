"""对四个完整批次做 Model × Harness 交叉对照。"""


def compare_model_harness_matrix(batches: list[dict], *,
                                 models: tuple[str, str],
                                 harnesses: tuple[str, str]) -> dict:
    """同题同重复轮次配对；差值只作描述统计，不自动宣称因果或显著性。"""
    if (len(batches) != 4 or len(set(models)) != 2 or len(set(harnesses)) != 2
            or any(not value for value in (*models, *harnesses))):
        raise ValueError("需要两个不同模型和两个不同 Harness 的四个批次")
    cells = {}
    reference = batches[0]
    expected_keys = {(item["task_id"], repeat)
                     for item in reference.get("manifest", [])
                     for repeat in range(reference.get("repeats", 0))}
    if not expected_keys:
        raise ValueError("实验任务清单不能为空")
    for batch in batches:
        if batch.get("status") != "completed":
            raise ValueError("只能比较已完成的批次")
        if any(batch.get(key) != reference.get(key) for key in ("collection", "manifest", "repeats")):
            raise ValueError("集合、Task 快照和重复次数必须相同")
        cell = (batch.get("model_version"), batch.get("harness_version"))
        if cell not in {(model, harness) for model in models for harness in harnesses} or cell in cells:
            raise ValueError("模型与 Harness 版本必须构成无重复的 2×2 矩阵")
        rows = {}
        for item in batch.get("items", []):
            key = (item.get("task_id"), item.get("repeat_index"))
            if (key in rows or key not in expected_keys or item.get("score") is None
                    or item.get("metrics") is None or not item.get("trial_id")):
                raise ValueError("批次存在重复、越界或缺失评分的 Trial")
            rows[key] = item
        if set(rows) != expected_keys:
            raise ValueError("四个批次必须覆盖相同的题目与重复轮次")
        cells[cell] = {"batch_id": batch["batch_id"], "rows": rows}
    if len(cells) != 4:
        raise ValueError("缺少 2×2 矩阵单元")

    def rate(cell: tuple[str, str]) -> float:
        rows = cells[cell]["rows"]
        return sum(bool(item["metrics"]["overall_success"]) for item in rows.values()) / len(rows)

    def diagnostic(cell: tuple[str, str]) -> dict:
        """过程、成本和安全单独展示；未知数据不充作零或通过。"""
        metrics = [item["metrics"] for item in cells[cell]["rows"].values()]
        def optional_rate(key: str) -> float | None:
            values = [row.get(key) for row in metrics]
            return sum(values) / len(values) if all(type(value) is bool for value in values) else None
        tokens = [row.get("total_tokens") for row in metrics]
        observed = [value for value in tokens if type(value) is int and value >= 0]
        safety = [row.get("safety_status", "unknown") for row in metrics]
        return {
            "result_success_rate": optional_rate("result_success"),
            "trajectory_success_rate": optional_rate("trajectory_success"),
            "mean_total_tokens": sum(observed) / len(observed) if observed else None,
            "token_observed": len(observed),
            "safety_gate": "fail" if "violation" in safety else (
                "pass" if all(value == "pass" for value in safety) else "unknown"),
        }

    m0, m1 = models
    h0, h1 = harnesses
    rates = {cell: rate(cell) for cell in cells}
    model_effect_at_h0 = rates[m1, h0] - rates[m0, h0]
    model_effect_at_h1 = rates[m1, h1] - rates[m0, h1]
    harness_effect_at_m0 = rates[m0, h1] - rates[m0, h0]
    harness_effect_at_m1 = rates[m1, h1] - rates[m1, h0]
    return {
        "collection": reference["collection"],
        "tasks": len(reference["manifest"]),
        "repeats": reference["repeats"],
        "cells": [{"model": model, "harness": harness,
                   "batch_id": cells[model, harness]["batch_id"],
                   "success_rate": rates[model, harness],
                   **diagnostic((model, harness))}
                  for model in models for harness in harnesses],
        "model_delta_by_harness": {h0: model_effect_at_h0, h1: model_effect_at_h1},
        "harness_delta_by_model": {m0: harness_effect_at_m0, m1: harness_effect_at_m1},
        "interaction_delta": model_effect_at_h1 - model_effect_at_h0,
        "interpretation": "描述性差值；需配对不确定性与真实样本复核后才能下能力结论",
    }
