#!/usr/bin/env python3
"""Main entry point for bmri-monitoring-automation."""

import csv
import ipaddress
import logging
import queue
import sys
from pathlib import Path
from threading import Thread

from rich.console import Console
from rich.progress import track

from config.argument_parser import ArgumentParser
from config.contexts import logging_context
from helper import logging as logging_helper
from helper.initializer import create_env, initialize, isallexists
from helper.misc import split_equally
from helper.print_info import info_request
from libs.device_comm import iterate_connection
from libs.file_creation import create_ssh_config
from models.env import EnvironmentsVariables
from models.main import Devices

env_vars = EnvironmentsVariables()


def main() -> None:
    """Ignore this, just a placeholder for main function."""
    log = logging.getLogger("mandiri-mona")

    # Printing Info if Requested
    if len(args.list) > 0:
        info_request(requests=args.list, console=console, env=env_vars)
        log.debug(f"Information for {args.list} displayed as requested.")
        return

    # Read Firewall Credentials from CSV and Assign to Devices Model
    devices_creds: list[Devices] = []
    with open(file=env_vars.file_paths.fw_creds, mode="r") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            devices_creds.append(
                Devices(
                    device_type=row.get("device_type", ""),
                    ip=ipaddress.IPv4Address(row.get("ip", "")),
                    username=row.get("username", ""),
                    password=row.get("password", ""),
                    hostname=row.get("hostname", None),
                    monitored=row.get("monitored", "False").lower() == "true",
                )
            )
    log.debug(f"Loaded {len(devices_creds)} firewall credentials from CSV.")
    for tracking in track(
        create_ssh_config(file_path=env_vars.file_paths.sshd_config, devices=devices_creds),
        description="Creating SSH Config...",
    ):
        current, total = tracking
        log.debug(f"Processed {current}/{total} devices for SSH config.")

    # Split Devices into Chunks for Multithreading
    chucked_devices: list[list[Devices]] = split_equally(list=devices_creds, n=env_vars.conn.num_of_threads)

    # Start Threads for Device Processing
    threads: list[Thread] = []
    for idx, chunk in enumerate(chucked_devices):
        log.debug(f"Started thread {idx + 1} for {len(chunk)} devices")
        thread = Thread(
            target=iterate_connection,
            args=(chunk, env_vars),
            name=f"DeviceThread-{idx + 1}",
        )
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

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

    log_q: queue.Queue = queue.Queue(maxsize=-1)
    with logging_context(
        settings=env_vars.logging,
        console=console,
        log_queue=log_q,
        level=env_vars.log_level,
    ) as log_listener:
        logging_helper.worker_logger(
            log_queue=log_q,
            log_level=env_vars.log_level,
        )
        log = logging.getLogger("mandiri-mona")
        log.info("Starting Mandiri MONA Application")

        try:
            main()
        except Exception as e:
            log.exception(f"An unhandled exception occurred: {e}", exc_info=True)
        finally:
            log.info("Mandiri MONA Finished Execution\n")
