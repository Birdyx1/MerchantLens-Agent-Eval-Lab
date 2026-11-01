from merchant_agent.tools.python_sandbox.python_request import validate_python_request


def build_docker_args(code: str, timeout_seconds: int) -> list[str]:
    validate_python_request(code, timeout_seconds)
    return [
        "docker",
        "run",
        "--rm",
        "--network", "none",
        "--memory", "128m",
        "--memory-swap", "128m",
        "--cpus", "0.5",
        "--pids-limit", "64",
        "--read-only",
        "--cap-drop", "ALL",
        "--user", "65534:65534",
        "--pull", "never",
        "python:3.13-alpine",
        "python",
        "-I",
        "-c",
        code,
    ]


def build_docker_create_args(code: str, timeout_seconds: int) -> list[str]:
    """
    构造 docker create 的参数列表，用于先创建容器、后启动的流程。
    输入校验沿用 validate_python_request，无效请求的 ValueError 向外传播。
    与 build_docker_args 的隔离选项、镜像和代码参数一致，但去掉 --rm，
    以便由执行器显式记录容器 ID 并在超时路径中清理。
    本函数只构造列表，不调用 subprocess。
    :param code: 待执行的 Python 源码
    :param timeout_seconds: 超时秒数，仅做校验
    :return: docker create 命令参数列表
    """
    validate_python_request(code, timeout_seconds)
    return [
        "docker",
        "create",
        "--network", "none",
        "--memory", "128m",
        "--memory-swap", "128m",
        "--cpus", "0.5",
        "--pids-limit", "64",
        "--read-only",
        "--cap-drop", "ALL",
        "--user", "65534:65534",
        "--pull", "never",
        "python:3.13-alpine",
        "python",
        "-I",
        "-c",
        code,
    ]
