"""Daemon module for running as a background service with persistent SSH connections."""

import logging
import os
import signal
import sys
import time
from pathlib import Path
from typing import NoReturn

LOGGER = logging.getLogger("mandiri-mona.daemon")


class DaemonManager:
    """
    Manages daemon process lifecycle including PID file handling and process control.

    This class provides functionality to start, stop, and check the status of a
    daemon process using PID file management.

    Attributes:
        pid_file (Path): Path to the PID file for the daemon process.
    """

    def __init__(self, pid_file: Path) -> None:
        """
        Initialize the DaemonManager with a specified PID file path.

        Args:
            pid_file (Path): Path where the PID file will be stored.
        """
        self.pid_file = pid_file

    def get_pid(self) -> int | None:
        """
        Read and return the PID from the PID file.

        Returns:
            int | None: The process ID if PID file exists and is valid, None otherwise.
        """
        try:
            if self.pid_file.exists():
                with open(self.pid_file, "r") as f:
                    pid = int(f.read().strip())
                    return pid
        except (ValueError, IOError) as e:
            LOGGER.error(f"Error reading PID file: {e}")
        return None

    def is_running(self) -> bool:
        """
        Check if the daemon process is currently running.

        Returns:
            bool: True if the daemon is running, False otherwise.
        """
        pid = self.get_pid()
        if pid is None:
            return False

        try:
            # Send signal 0 to check if process exists without actually signaling it
            os.kill(pid, 0)
            return True
        except OSError:
            # Process doesn't exist, clean up stale PID file
            LOGGER.warning(f"Found stale PID file for PID {pid}, removing it")
            self.remove_pid_file()
            return False

    def write_pid_file(self) -> None:
        """
        Write the current process ID to the PID file.

        Raises:
            IOError: If the PID file cannot be written.
        """
        try:
            self.pid_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.pid_file, "w") as f:
                f.write(str(os.getpid()))
            LOGGER.info(f"PID file created: {self.pid_file}")
        except IOError as e:
            LOGGER.error(f"Failed to write PID file: {e}")
            raise

    def remove_pid_file(self) -> None:
        """Remove the PID file if it exists."""
        try:
            if self.pid_file.exists():
                self.pid_file.unlink()
                LOGGER.info(f"PID file removed: {self.pid_file}")
        except IOError as e:
            LOGGER.error(f"Failed to remove PID file: {e}")

    def stop_daemon(self) -> bool:
        """
        Stop the running daemon process.

        Returns:
            bool: True if daemon was stopped successfully, False otherwise.
        """
        pid = self.get_pid()
        if pid is None:
            LOGGER.info("No daemon process is running")
            return False

        try:
            LOGGER.info(f"Stopping daemon process (PID: {pid})")
            os.kill(pid, signal.SIGTERM)

            # Wait for process to terminate (max 10 seconds)
            for _ in range(10):
                time.sleep(1)
                try:
                    os.kill(pid, 0)
                except OSError:
                    # Process no longer exists
                    self.remove_pid_file()
                    LOGGER.info("Daemon stopped successfully")
                    return True

            # Force kill if still running
            LOGGER.warning("Daemon did not stop gracefully, forcing termination")
            os.kill(pid, signal.SIGKILL)
            self.remove_pid_file()
            return True

        except OSError as e:
            LOGGER.error(f"Failed to stop daemon: {e}")
            return False

    def reload_daemon(self) -> bool:
        """
        Send reload signal (SIGHUP) to the running daemon process.

        Returns:
            bool: True if reload signal was sent successfully, False otherwise.
        """
        pid = self.get_pid()
        if pid is None:
            LOGGER.info("No daemon process is running")
            return False

        try:
            LOGGER.info(f"Sending reload signal to daemon process (PID: {pid})")
            os.kill(pid, signal.SIGHUP)
            LOGGER.info("Reload signal sent successfully")
            return True
        except OSError as e:
            LOGGER.error(f"Failed to send reload signal to daemon: {e}")
            return False

    def get_status(self) -> dict[str, str | int | None]:
        """
        Get the current status of the daemon.

        Returns:
            dict: A dictionary containing status information including:
                - running (bool): Whether the daemon is running
                - pid (int | None): The process ID if running
        """
        pid = self.get_pid()
        running = self.is_running()

        return {
            "running": running,
            "pid": pid if running else None,
        }


def daemonize() -> None:
    """
    Daemonize the current process by forking and detaching from the terminal.

    This function performs the standard Unix double-fork to create a daemon process
    that runs independently of the controlling terminal.

    Note: The working directory is preserved to maintain access to relative paths
    used throughout the application.

    Raises:
        OSError: If the fork operation fails.
    """
    try:
        # First fork
        pid = os.fork()
        if pid > 0:
            # Exit parent process
            sys.exit(0)
    except OSError as e:
        LOGGER.error(f"First fork failed: {e}")
        sys.exit(1)

    # Decouple from parent environment
    # Note: We intentionally do NOT change directory to preserve relative paths
    os.setsid()
    os.umask(0)

    try:
        # Second fork
        pid = os.fork()
        if pid > 0:
            # Exit second parent process
            sys.exit(0)
    except OSError as e:
        LOGGER.error(f"Second fork failed: {e}")
        sys.exit(1)

    # Redirect standard file descriptors
    sys.stdout.flush()
    sys.stderr.flush()
    with open(os.devnull, "r") as devnull_r, open(os.devnull, "a+") as devnull_w:
        os.dup2(devnull_r.fileno(), sys.stdin.fileno())
        os.dup2(devnull_w.fileno(), sys.stdout.fileno())
        os.dup2(devnull_w.fileno(), sys.stderr.fileno())


class GracefulShutdown:
    """
    Context manager for handling graceful shutdown on signal reception.

    This class sets up signal handlers for SIGTERM, SIGINT, and SIGHUP to enable
    graceful shutdown and configuration reload of the daemon process.

    Attributes:
        shutdown_flag (bool): Flag indicating whether shutdown has been requested.
        reload_flag (bool): Flag indicating whether configuration reload has been requested.
    """

    def __init__(self) -> None:
        """Initialize the GracefulShutdown handler."""
        self.shutdown_flag = False
        self.reload_flag = False

    def __enter__(self) -> "GracefulShutdown":
        """
        Set up signal handlers when entering the context.

        Returns:
            GracefulShutdown: The instance itself.
        """
        signal.signal(signal.SIGTERM, self._shutdown_signal_handler)
        signal.signal(signal.SIGINT, self._shutdown_signal_handler)
        signal.signal(signal.SIGHUP, self._reload_signal_handler)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Clean up signal handlers when exiting the context."""
        signal.signal(signal.SIGTERM, signal.SIG_DFL)
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        signal.signal(signal.SIGHUP, signal.SIG_DFL)

    def _shutdown_signal_handler(self, signum: int, frame) -> None:
        """
        Handle shutdown signals (SIGTERM, SIGINT).

        Args:
            signum (int): The signal number.
            frame: The current stack frame.
        """
        LOGGER.info(f"Received signal {signum}, initiating graceful shutdown")
        self.shutdown_flag = True

    def _reload_signal_handler(self, signum: int, frame) -> None:
        """
        Handle reload signal (SIGHUP).

        Args:
            signum (int): The signal number.
            frame: The current stack frame.
        """
        LOGGER.info(f"Received signal {signum}, initiating configuration reload")
        self.reload_flag = True

    def should_continue(self) -> bool:
        """
        Check if the process should continue running.

        Returns:
            bool: True if the process should continue, False if shutdown requested.
        """
        return not self.shutdown_flag

    def should_reload(self) -> bool:
        """
        Check if configuration reload has been requested.

        Returns:
            bool: True if reload has been requested, False otherwise.
        """
        return self.reload_flag

    def reset_reload_flag(self) -> None:
        """Reset the reload flag after handling the reload."""
        self.reload_flag = False
