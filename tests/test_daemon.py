"""Unit tests for daemon module."""

import os
import signal
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from libs.daemon import DaemonManager, GracefulShutdown


class TestDaemonManager:
    """Test suite for DaemonManager class."""

    @pytest.fixture
    def temp_pid_file(self):
        """Create a temporary PID file for testing."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pid") as f:
            pid_file = Path(f.name)
        yield pid_file
        # Cleanup
        if pid_file.exists():
            pid_file.unlink()

    def test_init(self, temp_pid_file):
        """Test DaemonManager initialization."""
        manager = DaemonManager(temp_pid_file)
        assert manager.pid_file == temp_pid_file

    def test_write_pid_file(self, temp_pid_file):
        """Test writing PID to file."""
        manager = DaemonManager(temp_pid_file)
        manager.write_pid_file()

        assert temp_pid_file.exists()
        with open(temp_pid_file, "r") as f:
            pid = int(f.read().strip())
        assert pid == os.getpid()

    def test_get_pid_valid(self, temp_pid_file):
        """Test getting valid PID from file."""
        manager = DaemonManager(temp_pid_file)
        test_pid = 12345
        with open(temp_pid_file, "w") as f:
            f.write(str(test_pid))

        assert manager.get_pid() == test_pid

    def test_get_pid_no_file(self, temp_pid_file):
        """Test getting PID when file doesn't exist."""
        manager = DaemonManager(temp_pid_file)
        assert manager.get_pid() is None

    def test_get_pid_invalid_content(self, temp_pid_file):
        """Test getting PID with invalid file content."""
        manager = DaemonManager(temp_pid_file)
        with open(temp_pid_file, "w") as f:
            f.write("invalid")

        assert manager.get_pid() is None

    def test_remove_pid_file(self, temp_pid_file):
        """Test removing PID file."""
        manager = DaemonManager(temp_pid_file)
        manager.write_pid_file()
        assert temp_pid_file.exists()

        manager.remove_pid_file()
        assert not temp_pid_file.exists()

    def test_remove_pid_file_not_exists(self, temp_pid_file):
        """Test removing PID file when it doesn't exist."""
        manager = DaemonManager(temp_pid_file)
        # Should not raise an error
        manager.remove_pid_file()

    def test_is_running_no_pid_file(self, temp_pid_file):
        """Test is_running when PID file doesn't exist."""
        manager = DaemonManager(temp_pid_file)
        assert not manager.is_running()

    def test_is_running_current_process(self, temp_pid_file):
        """Test is_running with current process PID."""
        manager = DaemonManager(temp_pid_file)
        manager.write_pid_file()
        assert manager.is_running()

    def test_is_running_nonexistent_process(self, temp_pid_file):
        """Test is_running with non-existent process PID."""
        manager = DaemonManager(temp_pid_file)
        # Use a PID that's unlikely to exist
        with open(temp_pid_file, "w") as f:
            f.write("999999")

        assert not manager.is_running()
        # PID file should be cleaned up
        assert not temp_pid_file.exists()

    @patch("os.kill")
    @patch("time.sleep")
    def test_stop_daemon_graceful(self, mock_sleep, mock_kill, temp_pid_file):
        """Test graceful daemon stop."""
        manager = DaemonManager(temp_pid_file)
        test_pid = 12345
        with open(temp_pid_file, "w") as f:
            f.write(str(test_pid))

        # Simulate process terminating after SIGTERM
        call_count = [0]

        def kill_side_effect(pid, sig):
            call_count[0] += 1
            if sig == signal.SIGTERM:
                # SIGTERM sent, next check will fail
                return
            # After SIGTERM, process check should raise OSError
            if call_count[0] > 2:
                raise OSError("No such process")

        mock_kill.side_effect = kill_side_effect

        result = manager.stop_daemon()
        assert result is True
        # Verify SIGTERM was sent
        sigterm_calls = [call for call in mock_kill.call_args_list if call[0][1] == signal.SIGTERM]
        assert len(sigterm_calls) >= 1

    def test_stop_daemon_no_process(self, temp_pid_file):
        """Test stopping daemon when no process is running."""
        manager = DaemonManager(temp_pid_file)
        assert not manager.stop_daemon()

    def test_get_status_not_running(self, temp_pid_file):
        """Test get_status when daemon is not running."""
        manager = DaemonManager(temp_pid_file)
        status = manager.get_status()
        assert status["running"] is False
        assert status["pid"] is None

    def test_get_status_running(self, temp_pid_file):
        """Test get_status when daemon is running."""
        manager = DaemonManager(temp_pid_file)
        manager.write_pid_file()
        status = manager.get_status()
        assert status["running"] is True
        assert status["pid"] == os.getpid()


class TestGracefulShutdown:
    """Test suite for GracefulShutdown class."""

    def test_init(self):
        """Test GracefulShutdown initialization."""
        handler = GracefulShutdown()
        assert handler.shutdown_flag is False

    def test_should_continue_initial(self):
        """Test should_continue initial state."""
        handler = GracefulShutdown()
        assert handler.should_continue() is True

    def test_signal_handler(self):
        """Test signal handler sets shutdown flag."""
        handler = GracefulShutdown()
        handler._shutdown_signal_handler(signal.SIGTERM, None)
        assert handler.shutdown_flag is True
        assert handler.should_continue() is False

    def test_context_manager(self):
        """Test GracefulShutdown as context manager."""
        with GracefulShutdown() as handler:
            assert handler.shutdown_flag is False
            assert handler.should_continue() is True

    @patch("signal.signal")
    def test_context_manager_sets_handlers(self, mock_signal):
        """Test context manager sets signal handlers."""
        with GracefulShutdown():
            # Verify signal handlers were set
            calls = mock_signal.call_args_list
            assert len(calls) >= 2
            # Check that SIGTERM and SIGINT were registered
            signals_registered = [call[0][0] for call in calls[:2]]
            assert signal.SIGTERM in signals_registered
            assert signal.SIGINT in signals_registered

    @patch("signal.signal")
    def test_context_manager_restores_handlers(self, mock_signal):
        """Test context manager restores signal handlers on exit."""
        with GracefulShutdown():
            pass

        # Verify signal handlers were restored
        calls = mock_signal.call_args_list
        # Should have calls for setting and then restoring
        assert len(calls) >= 4
        # Last two calls should restore to SIG_DFL
        assert calls[-2][0][1] == signal.SIG_DFL
        assert calls[-1][0][1] == signal.SIG_DFL


class TestDaemonize:
    """Test suite for daemonize function."""

    @patch("sys.stdin")
    @patch("sys.stdout")
    @patch("sys.stderr")
    @patch("os.fork")
    @patch("os.setsid")
    @patch("os.umask")
    @patch("sys.exit")
    @patch("os.dup2")
    @patch("builtins.open")
    def test_daemonize_first_fork_parent(
        self, mock_open, mock_dup2, mock_exit, mock_umask, mock_setsid, mock_fork, mock_stderr, mock_stdout, mock_stdin
    ):
        """Test daemonize first fork parent process exit."""
        from libs.daemon import daemonize

        # Mock file descriptors
        mock_stdin.fileno.return_value = 0
        mock_stdout.fileno.return_value = 1
        mock_stdout.flush = MagicMock()
        mock_stderr.fileno.return_value = 2
        mock_stderr.flush = MagicMock()

        # First fork returns parent PID - make exit actually stop execution
        mock_fork.return_value = 1
        mock_exit.side_effect = SystemExit(0)

        with pytest.raises(SystemExit):
            daemonize()

        # Parent should exit
        mock_exit.assert_called_once_with(0)

    @patch("sys.stdin")
    @patch("sys.stdout")
    @patch("sys.stderr")
    @patch("os.fork")
    @patch("os.setsid")
    @patch("os.umask")
    @patch("sys.exit")
    @patch("os.dup2")
    @patch("builtins.open")
    def test_daemonize_second_fork_parent(
        self, mock_open, mock_dup2, mock_exit, mock_umask, mock_setsid, mock_fork, mock_stderr, mock_stdout, mock_stdin
    ):
        """Test daemonize second fork parent process exit."""
        from libs.daemon import daemonize

        # Mock file descriptors
        mock_stdin.fileno.return_value = 0
        mock_stdout.fileno.return_value = 1
        mock_stderr.fileno.return_value = 2

        # Mock open to return file-like objects
        mock_file = MagicMock()
        mock_file.fileno.return_value = 3
        mock_open.return_value.__enter__.return_value = mock_file

        # First fork returns child (0), second fork returns parent PID
        mock_fork.side_effect = [0, 1]

        daemonize()

        # Second parent should exit
        assert mock_exit.call_count == 1
        mock_exit.assert_called_with(0)

    @patch("sys.stdin")
    @patch("sys.stdout")
    @patch("sys.stderr")
    @patch("os.fork")
    @patch("os.setsid")
    @patch("os.umask")
    @patch("sys.exit")
    @patch("os.dup2")
    @patch("builtins.open")
    def test_daemonize_first_fork_error(
        self, mock_open, mock_dup2, mock_exit, mock_umask, mock_setsid, mock_fork, mock_stderr, mock_stdout, mock_stdin
    ):
        """Test daemonize handles first fork error."""
        from libs.daemon import daemonize

        # Mock file descriptors
        mock_stdin.fileno.return_value = 0
        mock_stdout.fileno.return_value = 1
        mock_stdout.flush = MagicMock()
        mock_stderr.fileno.return_value = 2
        mock_stderr.flush = MagicMock()

        # First fork raises OSError - make exit actually stop execution
        mock_fork.side_effect = OSError("Fork failed")
        mock_exit.side_effect = SystemExit(1)

        with pytest.raises(SystemExit):
            daemonize()

        # Should exit with error
        mock_exit.assert_called_once_with(1)

    @patch("sys.stdin")
    @patch("sys.stdout")
    @patch("sys.stderr")
    @patch("os.fork")
    @patch("os.setsid")
    @patch("os.umask")
    @patch("sys.exit")
    @patch("os.dup2")
    @patch("builtins.open")
    def test_daemonize_second_fork_error(
        self, mock_open, mock_dup2, mock_exit, mock_umask, mock_setsid, mock_fork, mock_stderr, mock_stdout, mock_stdin
    ):
        """Test daemonize handles second fork error."""
        from libs.daemon import daemonize

        # Mock file descriptors
        mock_stdin.fileno.return_value = 0
        mock_stdout.fileno.return_value = 1
        mock_stderr.fileno.return_value = 2

        # Mock open to return file-like objects
        mock_file = MagicMock()
        mock_file.fileno.return_value = 3
        mock_open.return_value.__enter__.return_value = mock_file

        # First fork succeeds, second fork fails
        mock_fork.side_effect = [0, OSError("Second fork failed")]

        daemonize()

        # Should exit with error
        mock_exit.assert_called_once_with(1)

    @patch("os.fork")
    @patch("os.setsid")
    @patch("os.umask")
    @patch("sys.exit")
    @patch("os.dup2")
    @patch("sys.stdin")
    @patch("sys.stdout")
    @patch("sys.stderr")
    @patch("builtins.open")
    def test_daemonize_preserves_working_directory(
        self, mock_open, mock_stderr, mock_stdout, mock_stdin, mock_dup2, mock_exit, mock_umask, mock_setsid, mock_fork
    ):
        """Test daemonize preserves working directory."""
        from libs.daemon import daemonize

        # Both forks return child (0) to reach daemon code
        mock_fork.side_effect = [0, 0]

        # Mock file descriptors
        mock_stdin.fileno.return_value = 0
        mock_stdout.fileno.return_value = 1
        mock_stderr.fileno.return_value = 2

        # Mock open to return file-like objects
        mock_file = MagicMock()
        mock_file.fileno.return_value = 3
        mock_open.return_value.__enter__.return_value = mock_file

        with patch("os.chdir") as mock_chdir:
            daemonize()

            # Verify chdir was NOT called (preserving working directory)
            mock_chdir.assert_not_called()
