import sqlite3
from pathlib import Path

def get_store_net(db_path:str,store_id:str)->int | None:
    uri = Path(db_path).resolve().as_uri() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    try:
        cursor = connection.execute(
            "SELECT SUM(paid_fen - refunded_fen) FROM orders WHERE store_id = ?",
            (store_id,),
        )
        row = cursor.fetchone()
        return row[0] if row is not None else None
    finally:
        connection.close()
