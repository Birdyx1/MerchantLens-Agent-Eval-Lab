"""按 Task 分组估计重复 Trial 的成功率与不确定性。"""

import math
import random
from collections import defaultdict
from statistics import NormalDist


def wilson_interval(successes: int, trials: int, *, confidence: float = 0.95) -> tuple[float, float]:
    """二项结果的 Wilson 区间；零次试验返回错误，避免虚构精度。"""
    if trials < 1 or not 0 <= successes <= trials or not 0 < confidence < 1:
        raise ValueError("成功数、试验数或置信水平无效")
    z = NormalDist().inv_cdf((1 + confidence) / 2)
    p = successes / trials
    denominator = 1 + z * z / trials
    center = (p + z * z / (2 * trials)) / denominator
    radius = z * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials)) / denominator
    return max(0.0, center - radius), min(1.0, center + radius)


def summarize_repeats(rows: list[dict], *, expected_repeats: int,
                      confidence: float = 0.95, bootstrap_draws: int = 2000,
                      seed: int = 0) -> dict:
    """先算每题重复成功率，再等权汇总；按 Task 重采样避免伪独立。"""
    if expected_repeats < 2 or bootstrap_draws < 100:
        raise ValueError("至少重复两次，Bootstrap 抽样至少 100 次")
    if not 0 < confidence < 1:
        raise ValueError("置信水平无效")
    grouped = defaultdict(list)
    seen_ids = set()
    for row in rows:
        if row["trial_id"] in seen_ids:
            raise ValueError("重复 Trial ID")
        seen_ids.add(row["trial_id"])
        if type(row["overall_success"]) is not bool:
            raise ValueError("成功标记必须为布尔值")
        grouped[row["task_id"]].append(row["overall_success"])
    if not grouped or any(len(values) != expected_repeats for values in grouped.values()):
        raise ValueError("每个 Task 必须具有相同的预设重复次数")
    per_task = []
    rates = []
    for task_id, values in sorted(grouped.items()):
        successes = sum(values)
        rate = successes / expected_repeats
        rates.append(rate)
        low, high = wilson_interval(successes, expected_repeats, confidence=confidence)
        per_task.append({"task_id": task_id, "trials": expected_repeats,
                         "successes": successes, "success_rate": rate,
                         "wilson_interval": [low, high]})
    macro_rate = sum(rates) / len(rates)
    # 只有一道 Task 时无法估计跨题变化，不能把重复运行当作独立任务。
    if len(rates) < 2:
        macro_interval = None
    else:
        rng = random.Random(seed)
        draws = sorted(sum(rng.choices(rates, k=len(rates))) / len(rates)
                       for _ in range(bootstrap_draws))
        alpha = (1 - confidence) / 2
        macro_interval = [draws[int(alpha * (bootstrap_draws - 1))],
                          draws[int((1 - alpha) * (bootstrap_draws - 1))]]
    return {"tasks": len(rates), "trials": len(rows), "expected_repeats": expected_repeats,
            "confidence": confidence, "per_task": per_task,
            "macro_success_rate": macro_rate,
            "macro_task_bootstrap_interval": macro_interval,
            "bootstrap_seed": seed if macro_interval is not None else None}
