def limit_output(text: str, max_bytes: int) -> tuple[str, bool]:
    """
要求保留不超过上限的最长完整字符前缀，不能产生乱码。`max_bytes` 为 0、负数、浮点数或布尔值时，抛出 ValueError。

提示：先用 text.encode("utf-8") 得到字节；截断时注意可能切到一个中文字符或 emoji 的中间

    :param text:
    :param max_bytes:
    :return:
    """

    if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes <= 0:
        raise ValueError("max_bytes 必须是大于 0 的整数，且不能是布尔值")

    encoded_text = text.encode("utf-8")
    if len(encoded_text) <= max_bytes:
        return text, False

    truncated_text = encoded_text[:max_bytes].decode("utf-8", errors="ignore")

    return truncated_text, True