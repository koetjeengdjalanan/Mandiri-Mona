"""Custom Argument Parser Module."""

import argparse
import sys


class ArgumentParser(argparse.ArgumentParser):
    """Custom Argument Parser with overridden error handling."""

    def __init__(self) -> None:
        desc: str = "Mandiri MONA(MONitoring Automation) - Network Device SSH Hardening Automation Tool"
        prog: str = "mandiri-mona"
        epil: str = "Copyright 2025 Mandiri MONA Contributors"
        super().__init__(description=desc, prog=prog, epilog=epil)
        super().add_argument("--version", action="version", version="mandiri-mona 0.2.0")
        super().add_argument("-v", "--verbose", action="store_true", help="Enable verbose output", default=False)
        super().add_argument("-d", "--debug", action="store_true", help="Enable debug mode", default=False)
        super().add_argument(
            "-i", "--init", action="store_true", help="Initialize required files and directories", default=False
        )
        super().add_argument(
            "--log-level",
            type=str,
            choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            help="Set the logging level",
            default="INFO",
        )
        super().add_argument(
            "-l",
            "--list",
            nargs="*",
            choices=["devices", "env", "all"],
            help="List of items to process",
            default=["all"],
        )
        super().add_argument(
            "--compatibility-mode", action="store_true", help="Enable compatibility mode", default=False
        )
        super().add_argument(
            "--daemon",
            action="store_true",
            help="Run as a background service with persistent SSH connections",
            default=False,
        )
        super().add_argument(
            "--interval",
            type=int,
            help="Interval in seconds between command executions (only for daemon mode, default: 300)",
            default=300,
        )
        super().add_argument(
            "--status",
            action="store_true",
            help="Check the status of the running daemon process",
            default=False,
        )
        super().add_argument(
            "--stop",
            action="store_true",
            help="Stop the running daemon process",
            default=False,
        )
        super().add_argument(
            "--reload",
            action="store_true",
            help="Reload configuration (re-read fw_creds.csv and .env) for the running daemon process",
            default=False,
        )

    def error(self, message: str):
        """Override default error method to print custom message and exit."""
        sys.stderr.write(f"Error: {message}\n")
        self.print_help()
        sys.exit(2)

    def parse(self) -> argparse.Namespace:
        """Parse command line arguments."""
        args = super().parse_args()

        # Validate daemon mode arguments
        if args.daemon and args.interval <= 0:
            self.error("Interval must be positive when running in daemon mode")
        if (args.status or args.stop or args.reload) and args.daemon:
            self.error("Cannot use --status, --stop, or --reload with --daemon flag")

        return args
