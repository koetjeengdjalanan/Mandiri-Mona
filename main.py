#!/data/mandiri-mona/.venv/bin/python3.12
"""Main entry point for bmri-monitoring-automation."""
import logging
import queue
import signal
import subprocess
import sys
import threading
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.progress import track

from config.argument_parser import ArgumentParser
from config.contexts import logging_context
from helper import logging as logging_helper
from helper.initializer import create_env, initialize, isallexists
from helper.misc import load_devices_creds
from helper.print_info import info_request
from libs.daemon import DaemonManager, GracefulShutdown, daemonize
from libs.device_comm import connect_ssh
from libs.file_creation import create_ssh_config, update_fw_creds
from libs.persistent_ssh import PersistentSSHService
from models.env import EnvironmentsVariables
from models.main import Devices

env_vars = EnvironmentsVariables()


def daemon_main(interval: int) -> None:
    """
    Main function for daemon mode with persistent SSH connections.

    Args:
        interval (int): Interval in seconds between command executions.
    """
    log = logging.getLogger("mandiri-mona")

    # Load devices from CSV
    devices = load_devices_creds(file_path=env_vars.file_paths.fw_creds)
    log.info(f"Loaded {len(devices)} devices from CSV for daemon mode")

    # Create SSH config
    for tracking in track(
        create_ssh_config(file_path=env_vars.file_paths.sshd_config, devices=devices),
        description="Creating SSH Config...",
    ):
        current, total = tracking
        log.debug(f"Processed {current}/{total} devices for SSH config.")

    # Initialize and run the persistent SSH service
    service = PersistentSSHService(devices, env_vars, interval)

    with GracefulShutdown() as shutdown_handler:
        # Initialize connections
        service.initialize_connections()

        log.info(f"Starting monitoring service with {interval} second interval")

        while shutdown_handler.should_continue():
            # Check for reload signal
            if shutdown_handler.should_reload():
                log.info("Reload signal received, reloading configuration")
                service.reload_config()
                shutdown_handler.reset_reload_flag()

            # Run monitoring cycle
            service.run_monitoring_cycle()

            # Sleep in small intervals to allow for responsive shutdown and reload
            sleep_time = 0
            while sleep_time < interval and shutdown_handler.should_continue():
                time.sleep(1)
                sleep_time += 1

                # Check for reload during sleep
                if shutdown_handler.should_reload():
                    break

        # Cleanup
        service.cleanup_connections()
        log.info("Persistent SSH service stopped")


def main() -> None:
    """Main function and entry point to execute the monitoring automation."""
    log = logging.getLogger("mandiri-mona")

    # Read Firewall Credentials from CSV and Assign to Devices Model
    devices_creds: list[Devices] = load_devices_creds(file_path=env_vars.file_paths.fw_creds)
    if len(devices_creds) == 0:
        log.info("Processing complete: 0/0 devices succeeded")
        return

    log.debug(f"Loaded {len(devices_creds)} firewall credentials from CSV.")

    # Process Devices with ThreadPoolExecutor for Better Concurrency
    all_processed_devices: list[Devices] = []
    failed_devices: list[tuple[str, str]] = []

    for tracking in track(
        create_ssh_config(file_path=env_vars.file_paths.sshd_config, devices=devices_creds),
        description="Creating SSH Config...",
    ):
        current, total = tracking
        log.debug(f"Processed {current}/{total} devices for SSH config.")

    devices_lock = threading.Lock()  # Lock for thread-safe list operations

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
            try:
                dev, res = future.result()
                # Write output with thread-safe file handling
                output_file = env_vars.file_paths.output_dir.joinpath(f"{dev.hostname}.log")
                if args.compatibility_mode:
                    with open(output_file, "a") as f:
                        f.write(res)
                with devices_lock:
                    all_processed_devices.append(dev)
                    completed += 1
                    current = completed  # Capture count inside lock for consistent logging
                log.info(f"Completed processing for device {dev.hostname} ({current}/{total})")
            except Exception as e:
                with devices_lock:
                    failed_devices.append((str(device.hostname or device.ip), str(e)))
                    completed += 1
                    current = completed  # Capture count inside lock for consistent logging
                log.error(
                    f"Failed processing for device {device.hostname or device.ip} ({current}/{total}): {e}",
                    exc_info=True,
                    stack_info=True,
                )

    # Summary report
    with devices_lock:
        success_count = len(all_processed_devices)
        failed_count = len(failed_devices)
        failed_names = [d[0] for d in failed_devices]
        processed_devices_copy = all_processed_devices.copy()

    log.info(f"Processing complete: {success_count}/{total} devices succeeded")
    if failed_count > 0:
        log.warning(f"Failed devices ({failed_count}): {', '.join(failed_names)}")
    update_fw_creds(file_path=env_vars.file_paths.fw_creds, devices=processed_devices_copy)

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

    # Define PID file path
    pid_file = Path("/tmp/mandiri-mona.pid").absolute()
    daemon_manager = DaemonManager(pid_file)

    # Handle daemon control commands (--status, --stop)
    if args.status:
        status = daemon_manager.get_status()
        if status["running"]:
            console.print(f"[green]Daemon is running[/green] (PID: {status['pid']})")
            console.print("[cyan]Streaming logs (press Ctrl+C to stop)...[/cyan]\n")

            log_file = env_vars.logging.log_file_path

            # Check if log file exists
            if not log_file.exists():
                console.print(f"[yellow]Log file not found: {log_file}[/yellow]")
                sys.exit(0)

            try:
                # Use tail -f to follow the log file
                process = subprocess.Popen(
                    ["tail", "-f", str(log_file)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                )

                # Handle Ctrl+C gracefully
                def signal_handler(sig, frame):
                    """Handle Ctrl+C signal to gracefully stop streaming logs.

                    Args:
                        sig: The signal number.
                        frame: The current stack frame.
                    """
                    process.terminate()
                    console.print("\n[yellow]Stopped streaming logs[/yellow]")
                    sys.exit(0)

                signal.signal(signal.SIGINT, signal_handler)

                # Stream the output using console for consistency
                if process.stdout is not None:
                    for line in process.stdout:
                        console.print(line, end="")

            except Exception as e:
                console.print(f"[red]Error streaming logs: {e}[/red]")
                sys.exit(1)
        else:
            console.print("[yellow]Daemon is not running[/yellow]")
        sys.exit(0)

    if args.stop:
        if daemon_manager.stop_daemon():
            console.print("[green]Daemon stopped successfully[/green]")
            sys.exit(0)
        else:
            console.print("[red]Failed to stop daemon or daemon is not running[/red]")
            sys.exit(1)

    if args.reload:
        if daemon_manager.reload_daemon():
            console.print("[green]Reload signal sent to daemon successfully[/green]")
            sys.exit(0)
        else:
            console.print("[red]Failed to send reload signal or daemon is not running[/red]")
            sys.exit(1)

    try:
        env_file = Path(__file__).parent.joinpath(".env").absolute()
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

    # Handle daemon mode
    if args.daemon:
        # Check if daemon is already running
        if daemon_manager.is_running():
            console.print(f"[red]Daemon is already running[/red] (PID: {daemon_manager.get_pid()})")
            sys.exit(1)

        console.print(f"[green]Starting daemon mode with {args.interval} second interval[/green]")

        # Daemonize the process
        daemonize()

        # Write PID file
        daemon_manager.write_pid_file()

        # Set up logging for daemon mode
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
            log.info("Starting Mandiri MONA Application in Daemon Mode")

            try:
                daemon_main(interval=args.interval)
            except Exception as e:
                log.exception(f"An unhandled exception occurred in daemon mode: {e}", exc_info=True)
            finally:
                daemon_manager.remove_pid_file()
                log.info("Mandiri MONA Daemon Finished Execution\n")

        sys.exit(0)

    # Normal (non-daemon) mode
    log_q: queue.Queue = queue.Queue(maxsize=-1)
    with logging_context(
        settings=env_vars.logging,
        console=console,
        log_queue=log_q,
        level=env_vars.log_level,
    ) as log_listener:
        start_time: datetime = datetime.now()
        logging_helper.worker_logger(
            log_queue=log_q,
            log_level=env_vars.log_level,
        )
        log = logging.getLogger("mandiri-mona")
        log.info("Starting Mandiri MONA Application")

        try:
            if len(args.list) > 0:
                # Printing Info if Requested
                info_request(requests=args.list, console=console, env=env_vars)
                log.debug(f"Information for {args.list} displayed as requested.")
            else:
                main()
        except Exception as e:
            log.exception(f"An unhandled exception occurred: {e}", exc_info=True)
        finally:
            log.info(f"Mandiri MONA Finished Execution {datetime.now() - start_time}\n")
