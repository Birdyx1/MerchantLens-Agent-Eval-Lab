from merchant_agent.tools.search.search_result import SearchResult

PROVIDER_NAME = "tavily"


def parse_tavily_results(payload: dict, retrieved_at: str) -> list[SearchResult]:
    """
    把 Tavily 的原始响应转换为项目自己的 SearchResult 列表。

    约定 payload 为已解析的字典，retrieved_at 由调用方提供，本函数不校验其格式。
    结构错误抛 ValueError，不返回空列表，以便调用方区分"没有结果"和"解析失败"。
    :param payload: Tavily 搜索接口返回的原始字典
    :param retrieved_at: 检索时间文本，原样写入每条结果
    :return: 按原顺序生成的 SearchResult 列表；无结果时为空列表
    """
    if not isinstance(payload, dict):
        raise ValueError("payload 必须是字典")

    results = payload.get("results")
    if not isinstance(results, list):
        raise ValueError("payload 缺少 results 列表")

    parsed: list[SearchResult] = []
    for index, item in enumerate(results):
        if not isinstance(item, dict):
            raise ValueError(f"results 第 {index} 项不是字典")

        title = item.get("title")
        if not isinstance(title, str) or not title.strip():
            raise ValueError(f"results 第 {index} 项的 title 必须是非空字符串")

        url = item.get("url")
        if not isinstance(url, str) or not url.strip():
            raise ValueError(f"results 第 {index} 项的 url 必须是非空字符串")

        content = item.get("content", "")
        if not isinstance(content, str):
            raise ValueError(f"results 第 {index} 项的 content 必须是字符串")

        parsed.append(
            SearchResult(
                title=title,
                url=url,
                snippet=content,
                retrieved_at=retrieved_at,
                provider=PROVIDER_NAME,
            )
        )

    return parsed