import io
import subprocess
from unittest.mock import Mock

import pytest

from merchant_agent.tools.python_sandbox import python_runner as runner


@pytest.fixture(autouse=True)
def isolated_journal(tmp_path, monkeypatch):
    # 每个测试使用独立的容器日志，避免并发和历史记录干扰。
    monkeypatch.setenv("MERCHANT_SANDBOX_JOURNAL", str(tmp_path / "journal.sqlite"))


def test_stream_retains_only_limit():
    buffer = runner._LimitedBuffer(4)
    buffer.drain(io.BytesIO(b"abcdefgh"))
    assert buffer.data == b"abcd"
    assert buffer.truncated is True


def test_cleanup_failure_cannot_report_success(monkeypatch):
    container_id = "a" * 64
    process = Mock(stdout=io.BytesIO(b"ok\n"), stderr=io.BytesIO(b""))
    run = Mock(side_effect=[
        Mock(stdout=container_id),
        Mock(stdout='{"Status":"exited","ExitCode":0,"Error":""}'),
    ])
    monkeypatch.setattr(runner, "inspect_python_image", Mock())
    monkeypatch.setattr(runner.subprocess, "run", run)
    monkeypatch.setattr(runner.subprocess, "Popen", Mock(return_value=process))
    monkeypatch.setattr(runner, "remove_container", Mock(side_effect=subprocess.TimeoutExpired("docker", 5)))

    result = runner.run_python("print('ok')", 1)
    assert result.status == "infrastructure_error"
    assert "容器清理失败" in result.stderr
    assert len(runner.container_journal.pending()) == 1


def test_create_timeout_reports_uncertain_container(monkeypatch):
    remove = Mock()
    monkeypatch.setattr(runner, "inspect_python_image", Mock())
    monkeypatch.setattr(runner, "generate_container_name", Mock(return_value="merchant-eval-" + "a" * 32))
    monkeypatch.setattr(runner.subprocess, "run", Mock(side_effect=subprocess.TimeoutExpired("docker", 5)))
    monkeypatch.setattr(runner, "remove_container", remove)

    result = runner.run_python("print(1)", 1)
    assert result.status == "infrastructure_error"
    assert "创建结果未知" in result.stderr
    assert "merchant-eval-" in result.stderr
    remove.assert_not_called()
    assert len(runner.container_journal.pending()) == 1


def test_reconcile_retains_unknown_then_removes_verified_container(monkeypatch):
    name, token, container_id = "merchant-eval-" + "a" * 32, "b" * 32, "c" * 64
    runner.container_journal.record(name, token)
    monkeypatch.setattr(runner.time, "time", Mock(return_value=10**12))
    monkeypatch.setattr(runner, "_find_owned_container", Mock(side_effect=RuntimeError("unknown")))
    assert runner.reconcile_pending() == [(name, "unresolved")]
    assert len(runner.container_journal.pending()) == 1

    remove, verify = Mock(), Mock()
    monkeypatch.setattr(runner, "_find_owned_container", Mock(return_value=container_id))
    monkeypatch.setattr(runner, "remove_container", remove)
    monkeypatch.setattr(runner, "_verify_absent", verify)
    assert runner.reconcile_pending() == [(name, "removed")]
    remove.assert_called_once_with(container_id)
    verify.assert_called_once_with(container_id)
    assert runner.container_journal.pending() == []


@pytest.mark.parametrize("value", [0, -1, True])
def test_reconcile_rejects_unsafe_age(value):
    with pytest.raises(ValueError):
        runner.reconcile_pending(min_age_seconds=value)


def test_recovery_rejects_mismatched_label(monkeypatch):
    monkeypatch.setattr(runner.subprocess, "run", Mock(return_value=Mock(stdout="a" * 64 + " wrong")))
    with pytest.raises(RuntimeError):
        runner._find_owned_container("merchant-eval-" + "b" * 32, "c" * 32)


def test_cleanup_verification_rejects_existing_container(monkeypatch):
    monkeypatch.setattr(runner.subprocess, "run", Mock(return_value=Mock(stdout="a" * 64)))
    with pytest.raises(RuntimeError):
        runner._verify_absent("a" * 64)
