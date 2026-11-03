import pytest

from merchant_agent.agent.planning import parse_planning_decision, valid_tool_arguments


STORE_ID_TOOLS = ["get_store_net", "get_store_order_count", "get_store_refund_rate",
                  "get_store_aov", "get_store_paid_total", "get_store_refunded_total",
                  "get_store_refunded_order_count"]


@pytest.mark.parametrize("name", STORE_ID_TOOLS)
def test_store_id_tools_accept_single_store_id(name):
    assert valid_tool_arguments(name, {"store_id": "A"}) is True


@pytest.mark.parametrize("name", STORE_ID_TOOLS)
def test_store_id_tools_reject_extra_or_missing_keys(name):
    assert valid_tool_arguments(name, {"store_id": "A", "db_path": "/etc/passwd"}) is False
    assert valid_tool_arguments(name, {}) is False
    assert valid_tool_arguments(name, {"store_id": ""}) is False


def test_unknown_tool_is_rejected():
    assert valid_tool_arguments("drop_table", {"store_id": "A"}) is False


def test_parse_planning_decision_accepts_new_metric_tool():
    text = ('{"plan":["查询门店订单数"],"action":{"type":"tool",'
            '"name":"get_store_order_count","arguments":{"store_id":"A"}}}')
    decision = parse_planning_decision(text)
    assert decision.tool_name == "get_store_order_count"
    assert decision.tool_arguments == {"store_id": "A"}


def test_parse_planning_decision_rejects_bad_metric_arguments():
    text = ('{"plan":["查询门店订单数"],"action":{"type":"tool",'
            '"name":"get_store_order_count","arguments":{"store_id":1}}}')
    with pytest.raises(ValueError):
        parse_planning_decision(text)
