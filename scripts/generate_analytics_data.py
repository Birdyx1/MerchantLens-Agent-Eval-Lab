"""生成确定性的中等规模分析数据集（8 门店 × 31 天 × 每店每天 5–7 单）。

固定 seed，保证可复算；生成结果落盘为冻结快照。
"""

import csv
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUSINESS = ROOT / "fixtures" / "business_data"

CATEGORIES = ["饮品", "主食", "零售"]
CHANNELS = ["堂食", "外卖", "自提"]
STORES = [
    ("S1", "一号店", "华东", "上海"),
    ("S2", "二号店", "华东", "杭州"),
    ("S3", "三号店", "华南", "广州"),
    ("S4", "四号店", "华南", "深圳"),
    ("S5", "五号店", "华北", "北京"),
    ("S6", "六号店", "华北", "天津"),
    ("S7", "七号店", "华东", "南京"),
    ("S8", "八号店", "华中", "武汉"),
]
SEED = 20261103


def main() -> None:
    rng = random.Random(SEED)
    rows = []
    order_no = 1
    for store_id, _, _, _ in STORES:
        for day in range(1, 32):
            date = f"2026-10-{day:02d}"
            for _ in range(rng.randint(5, 7)):
                paid = rng.randint(1000, 20000)
                refunded = rng.randint(0, paid // 3)
                rows.append((
                    f"A{order_no:05d}", store_id, date,
                    rng.choice(CATEGORIES), rng.choice(CHANNELS), paid, refunded,
                ))
                order_no += 1
    with (BUSINESS / "analytics_orders.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["order_id", "store_id", "order_date", "category",
                         "channel", "paid_fen", "refunded_fen"])
        writer.writerows(rows)
    with (BUSINESS / "stores.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["store_id", "store_name", "region", "city"])
        writer.writerows(STORES)
    print(f"orders={len(rows)} stores={len(STORES)}")


if __name__ == "__main__":
    main()
