import json
import os

import requests

TAVILY_SEARCH_URL = "https://api.tavily.com/search"
MAX_RESPONSE_BYTES = 1024 * 1024


def request_tavily_payload(query: str, limit: int) -> dict:
    """
    校验输入、读取 Tavily API Key 并发送 POST 请求，分块读取响应并限制大小。
    非法输入抛 ValueError；缺少 Key 时抛 RuntimeError 且不发请求。
    本步暂不解析 JSON；Key 只进入请求头，不打印、不进错误消息、不出现在 URL 中。
    :param query: 查询词，去除首尾空白后必须非空
    :param limit: 结果条数，1～10 的整数且不能是布尔值
    :return: 解析后的原始 JSON 字典
    """
    if not isinstance(query, str):
        raise ValueError("query 必须是字符串")
    normalized = query.strip()
    if not normalized:
        raise ValueError("query 必须是去除首尾空白后非空的字符串")

    if isinstance(limit, bool) or not isinstance(limit, int):
        raise ValueError("limit 必须是 1～10 的整数，且不能是布尔值")
    if not 1 <= limit <= 10:
        raise ValueError("limit 必须是 1～10 的整数")

    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key or not api_key.strip():
        raise RuntimeError("缺少 TAVILY_API_KEY 环境变量，未发送请求")
    api_key = api_key.strip()

    payload = {
        "query": normalized,
        "max_results": limit,
        "search_depth": "basic",
        "auto_parameters": False,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    body = bytearray()

    try:
        with requests.post(
            TAVILY_SEARCH_URL,
            headers=headers,
            json=payload,
            timeout=5,
            allow_redirects=False,
            stream=True,
        ) as response:
            if not 200 <= response.status_code <= 299:
                raise RuntimeError("Tavily 搜索请求失败：HTTP 状态码不在 200～299 范围")

            for chunk in response.iter_content(chunk_size=8192):
                if len(body) + len(chunk) > MAX_RESPONSE_BYTES:
                    raise RuntimeError("Tavily 搜索响应超过 1 MiB 上限")
                body.extend(chunk)
    except requests.exceptions.RequestException:
        raise RuntimeError("Tavily 搜索请求失败：网络错误或超时") from None

    try:
        parsed = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise RuntimeError("Tavily 搜索响应不是合法 JSON") from None

    if not isinstance(parsed, dict):
        raise RuntimeError("Tavily 搜索响应顶层不是字典")

    return parsed