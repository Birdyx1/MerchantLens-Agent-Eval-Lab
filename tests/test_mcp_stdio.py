import asyncio
import sqlite3
from unittest.mock import Mock

import pytest

from merchant_agent import mcp_stdio
from merchant_agent.mcp_stdio_smoke import discover_stdio_tools, smoke_stdio


@pytest.mark.parametrize("key, flag, expected_search, expected_python", [
    ("", "0", False, False),
    ("discovery-only", "0", True, False),
    ("discovery-only", "1", True, True),
])
def test_configuration_matrix(monkeypatch, key, flag, expected_search, expected_python):
    monkeypatch.setenv("MERCHANT_DB_PATH", "/tmp/example.sqlite")
    monkeypatch.setenv("TAVILY_API_KEY", key)
    monkeypatch.setenv("MERCHANT_ENABLE_PYTHON", flag)
    create = Mock()
    monkeypatch.setattr(mcp_stdio, "create_server", create)

    mcp_stdio.main()

    kwargs = create.call_args.kwargs
    assert (kwargs["search_provider"] is not None) == expected_search
    assert (kwargs["python_executor"] is not None) == expected_python
    create.return_value.run.assert_called_once_with()


def test_invalid_flag_does_not_start_server(monkeypatch):
    monkeypatch.setenv("MERCHANT_DB_PATH", "/tmp/example.sqlite")
    monkeypatch.setenv("MERCHANT_ENABLE_PYTHON", "yes")
    create = Mock()
    monkeypatch.setattr(mcp_stdio, "create_server", create)

    with pytest.raises(ValueError):
        mcp_stdio.main()
    create.assert_not_called()


def test_missing_database_does_not_start_server(monkeypatch):
    monkeypatch.delenv("MERCHANT_DB_PATH", raising=False)
    create = Mock()
    monkeypatch.setattr(mcp_stdio, "create_server", create)

    with pytest.raises(RuntimeError):
        mcp_stdio.main()
    create.assert_not_called()


def test_real_subprocess_tool_discovery_and_sql_call(tmp_path):
    db_path = str(tmp_path / "orders.sqlite")
    with sqlite3.connect(db_path) as db:
        db.execute("CREATE TABLE orders (order_id TEXT, store_id TEXT, paid_fen INTEGER, refunded_fen INTEGER)")
        db.execute("INSERT INTO orders VALUES ('1', 'A', 15000, 3000)")

    sql_tools = {"get_store_net", "get_store_order_count", "get_store_refund_rate",
                 "get_store_aov", "get_store_paid_total", "get_store_refunded_total",
                 "get_store_refunded_order_count", "run_sql"}
    for search, python, names in [
        (False, False, sql_tools),
        (True, False, sql_tools | {"search_web"}),
        (True, True, sql_tools | {"search_web", "execute_python"}),
    ]:
        assert asyncio.run(discover_stdio_tools(
            db_path, enable_search=search, enable_python=python)) == names
    assert asyncio.run(smoke_stdio(db_path)) == 12000
