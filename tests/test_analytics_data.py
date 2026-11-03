import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_analytics_csv_shape():
    path = ROOT / "fixtures/business_data/analytics_orders.csv"
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    assert len(rows) >= 1000
    assert {r["store_id"] for r in rows} == {f"S{i}" for i in range(1, 9)}
    assert {r["order_date"][:7] for r in rows} == {"2026-10"}
    assert all(r["category"] in {"饮品", "主食", "零售"} for r in rows)
    assert all(r["channel"] in {"堂食", "外卖", "自提"} for r in rows)
    assert all(int(r["paid_fen"]) > 0 for r in rows)
