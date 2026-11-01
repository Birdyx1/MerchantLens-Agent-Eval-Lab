from dataclasses import dataclass


@dataclass
class PythonRunResult:
    status: str
    stdout: str
    stderr: str
    exit_code: int | None
    duration_ms: int
    stdout_truncated: bool
    stderr_truncated: bool
    oom_killed: bool | None = None
