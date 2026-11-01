from dataclasses import asdict

from merchant_agent.tools.search.search_result import SearchResult


def make_search_snapshot(query: str, results: list[SearchResult]) -> dict:
    """
    生成一次检索的证据快照，记录 Agent 当时收到的搜索结果。

    返回结构固定为 {"query": query, "results": [每条结果的字典]}，
    可直接用 json.dumps 序列化。本函数不访问网络、不修改输入对象，
    也不补造时间字段；快照只说明当时看到了什么，不证明网页正文支持答案。
    :param query: 本次检索使用的查询词，原样记录
    :param results: 本次检索返回的结果列表
    :return: 可 JSON 序列化的检索快照字典
    """
    return {
        "query": query,
        "results": [asdict(result) for result in results],
    }
