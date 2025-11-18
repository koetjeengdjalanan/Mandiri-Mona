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
        super().add_argument("--version", action="version", version="mandiri-mona 0.1.0")
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
            default=[],
        )

    def error(self, message: str) -> None:
        """Override default error method to print custom message and exit."""
        sys.stderr.write(f"Error: {message}\n")
        self.print_help()
        sys.exit(2)

    def parse(self) -> argparse.Namespace:
        """Parse command line arguments."""
        return super().parse_args()
