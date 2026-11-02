"""从冻结业务数据计算确定性的标注参考值。"""

import csv
from pathlib import Path


def store_net_from_fixture(path: Path, store_id: str) -> int | None:
    """按已支付减已退款的口径复算指定门店净收入，单位分。"""
    total = 0
    found = False
    with path.open(encoding="utf-8", newline="") as source:
        for row in csv.DictReader(source):
            if row["store_id"] == store_id:
                found = True
                total += int(row["paid_fen"]) - int(row["refunded_fen"])
    return total if found else None
