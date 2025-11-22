#!/usr/bin/env python3
"""Main entry point for bmri-monitoring-automation."""

import csv
import ipaddress
import logging
import queue
import sys
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from pathlib import Path

from rich.console import Console
from rich.progress import track

from config.argument_parser import ArgumentParser
from config.contexts import logging_context
from helper import logging as logging_helper
from helper.initializer import create_env, initialize, isallexists
from helper.print_info import info_request
from libs.device_comm import connect_ssh
from libs.file_creation import create_ssh_config, update_fw_creds
from models.env import EnvironmentsVariables
from models.main import Devices

env_vars = EnvironmentsVariables()


def main() -> None:
    """Main function and entry point to execute the monitoring automation."""
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

    # Process Devices with ThreadPoolExecutor for Better Concurrency
    all_processed_devices: list[Devices] = []
    failed_devices: list[tuple[str, str]] = []

    log.info(f"Starting device processing with {env_vars.conn.num_of_threads} worker threads")
    with ThreadPoolExecutor(max_workers=env_vars.conn.num_of_threads, thread_name_prefix="Mona_SSH-agent") as executor:
        # Submit individual device connections instead of chunks for better load balancing
        future_to_device: dict[Future, Devices] = {
            executor.submit(connect_ssh, device, env_vars): device for device in devices_creds
        }

        completed = 0
        total = len(devices_creds)

        for future in as_completed(future_to_device):
            device = future_to_device[future]
            completed += 1
            try:
                dev, res = future.result()
                # Write output with thread-safe file handling
                output_file = env_vars.file_paths.output_dir.joinpath(f"{dev.hostname}.log")
                with open(output_file, "a") as f:
                    f.write(res)
                all_processed_devices.append(dev)
                log.info(f"Completed processing for device {dev.hostname} ({completed}/{total})")
            except Exception as e:
                failed_devices.append((str(device.hostname or device.ip), str(e)))
                log.error(f"Failed processing for device {device.hostname or device.ip} ({completed}/{total}): {e}")

    # Summary report
    log.info(f"Processing complete: {len(all_processed_devices)}/{total} devices succeeded")
    if failed_devices:
        log.warning(f"Failed devices ({len(failed_devices)}): {', '.join([d[0] for d in failed_devices])}")
    update_fw_creds(file_path=env_vars.file_paths.fw_creds, devices=all_processed_devices)

    log.debug("Main function execution completed.")


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
