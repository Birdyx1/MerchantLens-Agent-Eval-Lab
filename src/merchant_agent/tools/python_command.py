from merchant_agent.tools.python_request import validate_python_request


def build_docker_args(code: str, timeout_seconds: int) -> list[str]:
    validate_python_request(code, timeout_seconds)
    return [
        "docker",
        "run",
        "--rm",
        "--network", "none",
        "--memory", "128m",
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
