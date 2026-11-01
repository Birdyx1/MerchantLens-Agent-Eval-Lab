def validate_python_request(code: str, timeout_seconds: int) -> None:
    """
    - code 必须是包含非空白内容的字符串。
    - timeout_seconds 必须是 1～5 的整数，包含 1 和 5，且不能是布尔值。
    - 无效输入抛出 ValueError；有效输入返回 None。
    - 本课不运行传入的代码。
    :param code: 
    :param timeout_seconds: 
    :return: 
    """
    if not isinstance(code, str) or not code.strip():
        raise ValueError("code 必须是包含非空白内容的字符串")
    if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, int):
        raise ValueError("timeout_seconds 必须是 1～5 的整数，且不能是布尔值")
    if not 1 <= timeout_seconds <= 5:
        raise ValueError("timeout_seconds 必须是 1～5 的整数")
    return None
