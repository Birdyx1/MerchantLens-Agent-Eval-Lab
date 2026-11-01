import typing

from merchant_agent.tools.search.search_result import SearchResult


class SearchProvider(typing.Protocol):
    """
    搜索服务的统一接口。
    不同搜索服务的调用方式可能不同，调用方只依赖本接口；
    实现类只需提供同名且签名兼容的 search 方法，即可被视为该接口的实现，
    无需显式继承。评测时可注入返回模拟结果的实现，避免依赖外部网络。
    """

    def search(self, query: str, limit: int) -> list[SearchResult]:
        """
        根据查询词返回搜索结果列表。
        :param query: 查询词
        :param limit: 期望返回的最大条数
        :return: 搜索结果列表；无结果时应为空列表而非 None
        """
        ...