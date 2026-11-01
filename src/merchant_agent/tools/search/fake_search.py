from merchant_agent.tools.search.search_result import SearchResult


class FakeSearchProvider:
    """
    基于固定模拟数据的搜索服务实现，用于测试与评测。

    与 SearchProvider 协议兼容：无需显式继承，只要提供签名一致的 search 方法，
    即可被类型检查器视为接口实现。匹配规则只是测试约定，不代表真实搜索质量。
    """

    def __init__(self, results: list[SearchResult]) -> None:
        self._results = list(results)

    def search(self, query: str, limit: int) -> list[SearchResult]:
        """
        在标题或摘要中查找查询词，忽略大小写，保持原顺序。

        :param query: 查询词；去除首尾空白后必须非空
        :param limit: 最多返回条数；必须是 1 到 10 的整数，不接受布尔值
        :return: 匹配的搜索结果列表，最多 limit 条；无匹配时返回空列表
        """
        if not isinstance(query, str):
            raise ValueError("query 必须是字符串")
        normalized = query.strip().casefold()
        if not normalized:
            raise ValueError("query 必须是去除首尾空白后非空的字符串")

        if isinstance(limit, bool) or not isinstance(limit, int):
            raise ValueError("limit 必须是 1～10 的整数，且不能是布尔值")
        if not 1 <= limit <= 10:
            raise ValueError("limit 必须是 1～10 的整数")

        matches = [
            result
            for result in self._results
            if normalized in result.title.casefold()
            or normalized in result.snippet.casefold()
        ]
        return matches[:limit]
