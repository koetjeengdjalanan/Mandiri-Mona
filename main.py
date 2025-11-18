"""Main entry point for bmri-monitoring-automation."""

import logging
import queue
import sys
from pathlib import Path

from rich.console import Console

from config.argument_parser import ArgumentParser
from helper import logging as logging_helper
from helper.initializer import create_env, initialize, isallexists
from helper.print_info import info_request
from models.env import EnvironmentsVariables

env_vars = EnvironmentsVariables()


def main():
    """Ignore this, just a placeholder for main function."""
    log = logging.getLogger("mandiri-mona")
    # console.print(args)

    # Printing Info if Requested
    if len(args.list) > 0:
        info_request(requests=args.list, console=console, env=env_vars)
        log.debug(f"Information for {args.list} displayed as requested.")
        return 0

    print("Hello from bmri-monitoring-automation!")


if __name__ == "__main__":
    # Preparing Console
    console = Console()

    # Parsing Arguments
    parser = ArgumentParser()
    args = parser.parse()
    env_vars.debug_mode = args.debug
    env_vars.log_level = args.log_level if not args.debug else "DEBUG"
    env_vars.verbose = args.verbose

    try:
        env_file = Path("./.env").absolute()
        if not env_file.exists():
            create_env()
            raise FileNotFoundError(".env file created, please review it and restart the application.")
        if env_file.stat().st_size == 0:
            create_env()
            raise ValueError(".env file is empty, please populate it and restart the application.")
    except Exception as e:
        print(f"Error with .env file: {e}", file=sys.stderr)
        sys.exit(1)

    # Initializing Files and Directories
    if args.init:
        missing_items = []
        checks = [
            (env_vars.file_paths.fw_creds, "file"),
            (env_vars.file_paths.sshd_config, "file"),
            (env_vars.logging.log_file_path.parent, "dir"),
            (env_vars.file_paths.output_dir, "dir"),
        ]
        results = isallexists(checks)
        for idx, (exists, is_type, error) in enumerate(results):
            path, type_str = checks[idx]
            if not exists or not is_type:
                if error:
                    console.print(f"[red]Error accessing {path}:[/red] {error}")
                else:
                    missing_items.append(path.name)
        if len(missing_items) > 0:
            for path in initialize(missing_items):
                console.print(f"[green]Created Paths:[/green] {path}")
        else:
            console.print("[yellow]All required files and directories already exist.[/yellow]")
        sys.exit(0)

    # TODO: Create a Context Manager!
    log_q = queue.Queue(maxsize=-1)
    listener = logging_helper.listener(log_q, env_vars.logging, console=console, level=env_vars.log_level)
    listener.start()

    logging_helper.worker_logger(log_q, log_level=env_vars.log_level)
    log = logging.getLogger("mandiri-mona")
    log.info("Starting Mandiri MONA Application")

    try:
        main()
    finally:
        log.info("Mandiri MONA Finished Execution")
        listener.stop()
