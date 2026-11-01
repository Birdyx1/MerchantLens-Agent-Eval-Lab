import io
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from merchant_agent.tools.python_sandbox import python_runner as runner


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        env = patch.dict('os.environ', {'MERCHANT_SANDBOX_JOURNAL': self.directory.name + '/journal.sqlite'})
        env.start()
        self.addCleanup(env.stop)

    def test_stream_retains_only_limit(self):
        buffer = runner._LimitedBuffer(4)
        buffer.drain(io.BytesIO(b"abcdefgh"))
        self.assertEqual(buffer.data, b"abcd")
        self.assertTrue(buffer.truncated)

    def test_cleanup_failure_cannot_report_success(self):
        container_id = "a" * 64
        process = Mock(stdout=io.BytesIO(b"ok\n"), stderr=io.BytesIO(b""))
        with (patch.object(runner, "inspect_python_image"),
              patch.object(runner.subprocess, "run", side_effect=[
                  Mock(stdout=container_id),
                  Mock(stdout='{"Status":"exited","ExitCode":0,"Error":""}'),
              ]),
              patch.object(runner.subprocess, "Popen", return_value=process),
              patch.object(runner, "remove_container", side_effect=subprocess.TimeoutExpired("docker", 5))):
            result = runner.run_python("print('ok')", 1)
        self.assertEqual(result.status, "infrastructure_error")
        self.assertIn("容器清理失败", result.stderr)
        self.assertEqual(len(runner.container_journal.pending()), 1)

    def test_create_timeout_reports_uncertain_container(self):
        with (patch.object(runner, "inspect_python_image"),
              patch.object(runner, "generate_container_name", return_value="merchant-eval-" + "a" * 32),
              patch.object(runner.subprocess, "run", side_effect=subprocess.TimeoutExpired("docker", 5)),
              patch.object(runner, "remove_container") as remove):
            result = runner.run_python("print(1)", 1)
        self.assertEqual(result.status, "infrastructure_error")
        self.assertIn("创建结果未知", result.stderr)
        self.assertIn("merchant-eval-", result.stderr)
        remove.assert_not_called()
        self.assertEqual(len(runner.container_journal.pending()), 1)

    def test_reconcile_retains_unknown_then_removes_verified_container(self):
        name, token, container_id = 'merchant-eval-' + 'a' * 32, 'b' * 32, 'c' * 64
        runner.container_journal.record(name, token)
        with patch.object(runner.time, 'time', return_value=10**12):
            with patch.object(runner, '_find_owned_container', side_effect=RuntimeError('unknown')):
                self.assertEqual(runner.reconcile_pending(), [(name, 'unresolved')])
            self.assertEqual(len(runner.container_journal.pending()), 1)
            with (patch.object(runner, '_find_owned_container', return_value=container_id),
                  patch.object(runner, 'remove_container') as remove,
                  patch.object(runner, '_verify_absent') as verify):
                self.assertEqual(runner.reconcile_pending(), [(name, 'removed')])
                remove.assert_called_once_with(container_id)
                verify.assert_called_once_with(container_id)
            self.assertEqual(runner.container_journal.pending(), [])

    def test_reconcile_rejects_unsafe_age(self):
        for value in (0, -1, True):
            with self.assertRaises(ValueError):
                runner.reconcile_pending(min_age_seconds=value)

    def test_recovery_rejects_mismatched_label(self):
        with patch.object(runner.subprocess, 'run', return_value=Mock(stdout='a' * 64 + ' wrong')):
            with self.assertRaises(RuntimeError):
                runner._find_owned_container('merchant-eval-' + 'b' * 32, 'c' * 32)

    def test_cleanup_verification_rejects_existing_container(self):
        with patch.object(runner.subprocess, 'run', return_value=Mock(stdout='a' * 64)):
            with self.assertRaises(RuntimeError):
                runner._verify_absent('a' * 64)


if __name__ == "__main__":
    unittest.main()
