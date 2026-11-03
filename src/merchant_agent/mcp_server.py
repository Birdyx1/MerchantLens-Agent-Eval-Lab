from collections.abc import Callable

from mcp.server import MCPServer

from merchant_agent.tools.python_sandbox.python_result import PythonRunResult
from merchant_agent.tools.search.search_provider import SearchProvider
from merchant_agent.tools.search.search_snapshot import SearchSnapshot, make_search_snapshot
from merchant_agent.tools.sql import sql_query
from merchant_agent.tools.sql.run_sql import run_sql as run_sql_query


def create_server(
    db_path: str,
    search_provider: SearchProvider | None = None,
    python_executor: Callable[[str, int], PythonRunResult] | None = None,
) -> MCPServer:
    """
    创建名为 merchant-tools 的 MCP 服务，并注册门店净收入查询工具。

    数据库路径属于部署配置，在此固定并闭包捕获，不作为工具参数暴露；
    模型只能提供 store_id，无法指定数据库文件。本函数只构造服务对象，
    不启动传输、不监听端口。
    搜索服务由调用方注入：测试用 FakeSearchProvider，真实运行用
    TavilySearchProvider；不传时不注册 search_web，SQL 工具照常工作。
    Python 执行器同样由调用方注入；未注入时不暴露 execute_python。
    :param db_path: SQLite 数据库路径，由调用方在创建服务时确定
    :param search_provider: 可选的搜索服务实现，不作为工具参数暴露
    :param python_executor: 可选的受限 Python 执行函数，不作为工具参数暴露
    :return: 已注册相应工具的 MCP 服务对象
    """
    server = MCPServer(name="merchant-tools")

    @server.tool()
    def get_store_net(store_id: str) -> int | None:
        """查询指定门店的净收入，单位为分；门店不存在时返回空值。"""
        return sql_query.get_store_net(db_path, store_id)

    @server.tool()
    def get_store_order_count(store_id: str) -> int | None:
        """查询指定门店的订单数；门店不存在时返回空值。"""
        return sql_query.get_store_order_count(db_path, store_id)

    @server.tool()
    def get_store_refund_rate(store_id: str) -> float | None:
        """查询指定门店的退款率（已退款金额/已支付金额，0 到 1 的小数）；门店不存在时返回空值。"""
        return sql_query.get_store_refund_rate(db_path, store_id)

    @server.tool()
    def get_store_aov(store_id: str) -> int | None:
        """查询指定门店的客单价（已支付金额/订单数，单位为分，向下取整）；门店不存在时返回空值。"""
        return sql_query.get_store_aov(db_path, store_id)

    @server.tool()
    def get_store_paid_total(store_id: str) -> int | None:
        """查询指定门店的已支付总额，单位为分；门店不存在时返回空值。"""
        return sql_query.get_store_paid_total(db_path, store_id)

    @server.tool()
    def get_store_refunded_total(store_id: str) -> int | None:
        """查询指定门店的已退款总额，单位为分；门店不存在时返回空值。"""
        return sql_query.get_store_refunded_total(db_path, store_id)

    @server.tool()
    def get_store_refunded_order_count(store_id: str) -> int | None:
        """查询指定门店发生过退款的订单数；门店不存在时返回空值。"""
        return sql_query.get_store_refunded_order_count(db_path, store_id)

    if search_provider is not None:

        @server.tool()
        def search_web(query: str, limit: int) -> SearchSnapshot:
            """检索网页，返回查询词与检索结果快照，供后续核验证据。"""
            results = search_provider.search(query, limit)
            return make_search_snapshot(query, results)

    if python_executor is not None:

        @server.tool()
        def execute_python(code: str, timeout_seconds: int) -> PythonRunResult:
            """在受限容器中执行 Python 代码并返回结构化结果。"""
            return python_executor(code, timeout_seconds)

    @server.tool()
    def run_sql(query: str) -> dict:
        """执行只读 SQL 查询，返回列与行；仅允许 SELECT/WITH。"""
        return run_sql_query(db_path, query)

    return server
