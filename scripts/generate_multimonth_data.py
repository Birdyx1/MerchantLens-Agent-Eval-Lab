"""生成跨月分析数据集：9 月正常、10 月零售品类金额减半，用于时间归因题。

固定 seed，保证可复算；生成结果落盘为冻结快照。
"""

import csv
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "fixtures" / "business_data" / "analytics_orders_2m.csv"

CATEGORIES = ["饮品", "主食", "零售"]
CHANNELS = ["堂食", "外卖", "自提"]
STORES = [f"S{i}" for i in range(1, 9)]
SEED = 20261103


def main() -> None:
    rng = random.Random(SEED)
    rows = []
    order_no = 1
    for month in ("2026-09", "2026-10"):
        for store_id in STORES:
            for day in range(1, 31):
                date = f"{month}-{day:02d}"
                for _ in range(rng.randint(5, 7)):
                    category = rng.choice(CATEGORIES)
                    channel = rng.choice(CHANNELS)
                    paid = rng.randint(1000, 20000)
                    if month == "2026-10" and category == "零售":
                        paid = max(100, paid // 2)
                    refunded = 0 if rng.random() < 0.85 else rng.randint(1, paid // 3)
                    rows.append((
                        f"A{order_no:05d}", store_id, date, category, channel, paid, refunded,
                    ))
                    order_no += 1
    with OUT.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["order_id", "store_id", "order_date", "category",
                         "channel", "paid_fen", "refunded_fen"])
        writer.writerows(rows)
    print(f"rows={len(rows)}")


if __name__ == "__main__":
    main()
