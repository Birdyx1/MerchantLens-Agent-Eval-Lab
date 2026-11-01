from datetime import datetime, timezone

from merchant_agent.tools.search.search_result import SearchResult
from merchant_agent.tools.search.tavily_client import request_tavily_payload
from merchant_agent.tools.search.tavily_parser import parse_tavily_results


class TavilySearchProvider:
    """
    Tavily 搜索服务适配层，与 SearchProvider 协议兼容。

    调用方只依赖 search(query, limit)，无需知道 Tavily 的请求格式和字段名。
    请求与解析失败时异常向上传递，不转换为空列表，
    以便调用方区分"没有搜索结果"和"工具出错"。
    """

    def search(self, query: str, limit: int) -> list[SearchResult]:
        """
        执行一次 Tavily 网页搜索并返回统一格式的结果列表。

        :param query: 查询词
        :param limit: 期望返回的结果条数
        :return: 按原顺序生成的 SearchResult 列表；无结果时为空列表
        """
        payload = request_tavily_payload(query, limit)
        retrieved_at = datetime.now(timezone.utc).isoformat()
        return parse_tavily_results(payload, retrieved_at)