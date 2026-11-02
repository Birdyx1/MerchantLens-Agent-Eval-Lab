from mcp import Client

from merchant_agent.mcp_server import create_server


async def list_tool_names(db_path: str) -> list[str]:
    """
    通过进程内 MCP 客户端发现服务端注册的工具名称。

    服务由 create_server 按 db_path 构造，再交给 Client 走完整的
    initialize → tools/list 协议流程，不监听端口。本函数只做工具发现，
    不调用任何工具，因此不会触发 SQL 查询。
    :param db_path: SQLite 数据库路径，仅用于构造服务，不作为工具参数
    :return: 服务端暴露的工具名称列表
    """
    server = create_server(db_path)
    async with Client(server) as client:
        result = await client.list_tools()
        return [tool.name for tool in result.tools]


async def call_store_net(db_path: str, store_id: str) -> int | None:
    """
    通过进程内 MCP 客户端调用 get_store_net 工具查询门店净收入。

    走完整的 tools/call 协议流程，而不是直接调用服务端函数。
    工具执行失败时抛 RuntimeError，不返回 0 或空值，避免把错误伪装成结果。
    :param db_path: SQLite 数据库路径，仅用于构造服务，不作为工具参数
    :param store_id: 门店 ID，唯一由模型控制的业务输入
    :return: 门店净收入（单位分）；门店不存在时返回 None
    """
    server = create_server(db_path)
    async with Client(server) as client:
        result = await client.call_tool("get_store_net", {"store_id": store_id})

    if result.is_error:
        raise RuntimeError("get_store_net 工具调用失败")

    return result.structured_content["result"]