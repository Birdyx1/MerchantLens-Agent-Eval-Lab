import json
import re
import sqlite3
import subprocess
import threading
import time
import uuid

from merchant_agent.tools.python_sandbox.python_command import build_docker_create_args
from merchant_agent.tools.python_sandbox.python_result import PythonRunResult
from merchant_agent.tools.python_sandbox import container_journal


def inspect_python_image() -> str:
    """
    检查本地固定镜像 python:3.13-alpine 是否存在，并返回其镜像 ID。
    使用参数列表调用 docker image inspect，不使用 shell=True；
    捕获文本输出，最多等待 5 秒，非零退出码转为异常。
    命令不存在、检查失败或超时时，异常直接传给调用方。
    :return: 去掉首尾空白的镜像 ID，形如 sha256:...
    """
    completed = subprocess.run(
        [
            "docker",
            "image",
            "inspect",
            "--format",
            "{{.Id}}",
            "python:3.13-alpine",
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=5,
    )
    return completed.stdout.strip()

def remove_container(container_id: str) -> None:
    """
    删除指定的 Docker 容器。
    先用正则校验 container_id 必须是 64 位小写十六进制字符串，
    格式错误时抛出 ValueError，且不调用 Docker。
    格式正确时，用参数列表调用 docker rm --force 删除该容器。
    使用 check=True、capture_output=True、text=True、timeout=5；
    命令失败或超时的异常向上传递。
    :param container_id: 64 位小写十六进制容器 ID
    :return: None
    """
    if not isinstance(container_id, str) or re.fullmatch(r"[0-9a-f]{64}", container_id) is None:
        raise ValueError("container_id 必须是 64 位小写十六进制字符串")

    subprocess.run(
        [
            "docker",
            "rm",
            "--force",
            container_id,
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=5,
    )


def parse_container_id(stdout: str) -> str:
    """
    解析 docker create 的标准输出，取出容器 ID。
    先校验输入是字符串，再去除首尾空白；
    仅当结果恰好为 64 位小写十六进制字符串时才返回该 ID。
    其他情况一律抛 RuntimeError，错误消息为固定文字，不拼接原始输出，
    以避免外部输出中的代码、控制字符或敏感信息进入错误消息。
    本函数不调用 Docker，也不调用 subprocess。
    :param stdout: docker create 命令的标准输出
    :return: 校验通过的 64 位小写十六进制容器 ID
    """
    if not isinstance(stdout, str):
        raise RuntimeError("容器 ID 输出格式无效")

    container_id = stdout.strip()
    if re.fullmatch(r"[0-9a-f]{64}", container_id) is None:
        raise RuntimeError("容器 ID 输出格式无效")

    return container_id


def generate_container_name() -> str:
    return f"merchant-eval-{uuid.uuid4().hex}"


class _LimitedBuffer:
    """Drain a binary stream while retaining at most limit bytes."""

    def __init__(self, limit: int) -> None:
        self.limit = limit
        self.data = bytearray()
        self.truncated = False
        self.error = False

    def drain(self, stream) -> None:
        try:
            while chunk := stream.read(4096):
                remaining = self.limit - len(self.data)
                self.data.extend(chunk[:remaining])
                if len(chunk) > remaining:
                    self.truncated = True
        except OSError:
            self.error = True
        finally:
            stream.close()

    def text(self) -> str:
        return bytes(self.data).decode("utf-8", errors="replace")


def _find_owned_container(name: str, token: str) -> str | None:
    """Resolve a generated name only if its ownership label matches."""
    completed = subprocess.run(
        ["docker", "inspect", "--format", '{{.Id}} {{index .Config.Labels "merchant-eval.token"}}', name],
        capture_output=True, text=True, timeout=5, check=True,
    )
    parts = completed.stdout.strip().split()
    if len(parts) != 2 or parts[1] != token:
        raise RuntimeError("容器归属校验失败")
    return parse_container_id(parts[0])


def _verify_absent(container_id: str) -> None:
    result = subprocess.run(
        ["docker", "ps", "--all", "--no-trunc", "--filter", f"id={container_id}", "--format", "{{.ID}}"],
        capture_output=True, text=True, check=True, timeout=5,
    )
    if result.stdout.strip():
        raise RuntimeError("容器删除后仍然存在")


def reconcile_pending(*, min_age_seconds: float = 300) -> list[tuple[str, str]]:
    """Reconcile old records; keep unlocated records because creation may finish late.

    Call only when runs older than min_age_seconds are no longer active. An
    operator or scheduled job must repeat this after Docker becomes available.
    """
    if isinstance(min_age_seconds, bool) or not isinstance(min_age_seconds, (int, float)) or min_age_seconds < 300:
        raise ValueError("min_age_seconds 必须不少于 300 秒")
    results = []
    for name, token, created_at in container_journal.pending():
        if time.time() - created_at < min_age_seconds:
            continue
        try:
            container_id = _find_owned_container(name, token)
            remove_container(container_id)
            _verify_absent(container_id)
            container_journal.forget(name, token)
            results.append((name, "removed"))
        except (OSError, subprocess.SubprocessError, RuntimeError):
            results.append((name, "unresolved"))
    return results


def run_python(code: str, timeout_seconds: int, *, max_output_bytes: int = 65536) -> PythonRunResult:
    """Run Python in a restricted Docker container and return a structured result.

    The execution timeout applies to the started program; image checks, creation,
    inspection and cleanup each have their own control-plane timeout.
    """
    if (isinstance(max_output_bytes, bool) or not isinstance(max_output_bytes, int)
            or not 1 <= max_output_bytes <= 1048576):
        raise ValueError("max_output_bytes 必须是 1 到 1048576 的整数")
    args = build_docker_create_args(code, timeout_seconds)
    name = generate_container_name()
    token = uuid.uuid4().hex
    args[2:2] = ["--name", name, "--label", f"merchant-eval.token={token}"]
    started = time.monotonic()
    out, err = _LimitedBuffer(max_output_bytes), _LimitedBuffer(max_output_bytes)
    status, exit_code = "infrastructure_error", None
    oom_killed = None
    diagnostic = ""
    container_id = None
    create_uncertain = False
    process = None
    threads = []
    recorded = False
    try:
        inspect_python_image()
        container_journal.record(name, token)
        recorded = True
        create_uncertain = True
        created = subprocess.run(args, capture_output=True, text=True, check=True, timeout=5)
        container_id = parse_container_id(created.stdout)
        create_uncertain = False
        process = subprocess.Popen(
            ["docker", "start", "--attach", container_id],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        threads = [threading.Thread(target=buffer.drain, args=(stream,), daemon=True)
                   for buffer, stream in ((out, process.stdout), (err, process.stderr))]
        for thread in threads:
            thread.start()
        try:
            process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            status = "timeout"
            process.kill()
            process.wait(timeout=5)
        else:
            state_result = subprocess.run(
                ["docker", "inspect", "--format", "{{json .State}}", container_id],
                capture_output=True, text=True, check=True, timeout=5,
            )
            state = json.loads(state_result.stdout)
            if state.get("Status") != "exited" or state.get("Error") or not isinstance(state.get("ExitCode"), int):
                raise RuntimeError("无法确定容器执行结果")
            exit_code = state["ExitCode"]
            oom_killed = state.get("OOMKilled") if isinstance(state.get("OOMKilled"), bool) else None
            status = "succeeded" if exit_code == 0 else "program_error"
    except subprocess.CalledProcessError:
        diagnostic = "Docker 命令失败"
    except (OSError, subprocess.TimeoutExpired, RuntimeError, ValueError, AttributeError, sqlite3.Error) as exc:
        diagnostic = f"Docker 执行失败：{type(exc).__name__}"
    finally:
        if container_id is None and create_uncertain:
            try:
                container_id = _find_owned_container(name, token)
            except (OSError, subprocess.SubprocessError, RuntimeError):
                diagnostic = "创建结果未知；需要按名称和标签核查可能遗留的容器"
            # Retain a correlation key in the returned result for later investigation.
            if diagnostic:
                diagnostic += f"（名称：{name}，标签：{token}）"
        if container_id is not None:
            try:
                remove_container(container_id)
                _verify_absent(container_id)
                if recorded:
                    container_journal.forget(name, token)
            except (OSError, subprocess.SubprocessError, RuntimeError, sqlite3.Error) as exc:
                status = "infrastructure_error"
                diagnostic = f"容器清理失败：{type(exc).__name__}（ID：{container_id}）"
        for thread in threads:
            thread.join(timeout=5)
            if thread.is_alive():
                status = "infrastructure_error"
                diagnostic = "输出读取线程未结束"
        if out.error or err.error:
            diagnostic = "输出读取失败"
    if diagnostic:
        status = "infrastructure_error"
    stderr = err.text()
    if diagnostic:
        stderr = (stderr + "\n" + diagnostic).lstrip("\n")
    return PythonRunResult(status, out.text(), stderr, exit_code,
                           int((time.monotonic() - started) * 1000),
                           out.truncated, err.truncated, oom_killed)
