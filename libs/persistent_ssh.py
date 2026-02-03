"""Module for managing persistent SSH connections as a background service."""

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Iterable

from netmiko import ConnectHandler

from models.env import EnvironmentsVariables
from models.main import Devices

LOGGER = logging.getLogger("mandiri-mona.persistent_ssh")

# Configuration constants
RECONNECT_DELAY_SECONDS = 2  # Delay before attempting to reconnect after connection loss


class PersistentSSHConnection:
    """
    Manages a persistent SSH connection to a network device.

    This class maintains a long-lived SSH connection to a device and periodically
    executes commands on it.

    Attributes:
        device (Devices): The device to connect to.
        env_vars (EnvironmentsVariables): Environment configuration.
        connection: The active SSH connection object.
        lock (threading.Lock): Thread lock for connection safety.
    """

    def __init__(self, device: Devices, env_vars: EnvironmentsVariables) -> None:
        """
        Initialize a persistent SSH connection manager.

        Args:
            device (Devices): Device information and credentials.
            env_vars (EnvironmentsVariables): Environment configuration.
        """
        self.device = device
        self.env_vars = env_vars
        self.connection = None
        self.lock = threading.Lock()
        self._connected = False

    def connect(self) -> None:
        """
        Establish SSH connection to the device.

        Raises:
            Exception: If connection fails after retries.
        """
        with self.lock:
            if self._connected and self.connection:
                return

            conn_vars: dict[str, str | int] = {
                "device_type": self.device.device_type,
                "host": str(self.device.ip),
                "username": self.device.username,
                "password": self.device.password,
                "ssh_config_file": str(self.env_vars.file_paths.sshd_config),
                "conn_timeout": self.env_vars.conn.conn_timeout,
                "read_timeout_override": self.env_vars.conn.read_timeout_override,
            }

            try:
                LOGGER.info(f"Establishing connection to {self.device.hostname or self.device.ip}")
                self.connection = ConnectHandler(**conn_vars)
                self._connected = True

                # Get hostname if not already set
                if not self.device.hostname:
                    hostname = str(
                        self.connection.send_command(
                            command_string="show system info | match hostname", expect_string=r">"
                        )
                    ).strip("\n")
                    self.device.hostname = hostname.strip().split(" ")[-1]

                LOGGER.info(f"Successfully connected to {self.device.hostname}")
            except Exception as e:
                LOGGER.error(f"Failed to connect to {self.device.hostname or self.device.ip}: {e}")
                self._connected = False
                raise

    def disconnect(self) -> None:
        """Disconnect from the device."""
        with self.lock:
            if self.connection and self._connected:
                try:
                    self.connection.disconnect()
                    LOGGER.info(f"Disconnected from {self.device.hostname or self.device.ip}")
                except Exception as e:
                    LOGGER.error(f"Error during disconnect from {self.device.hostname or self.device.ip}: {e}")
                finally:
                    self._connected = False
                    self.connection = None

    def is_alive(self) -> bool:
        """
        Check if the connection is still alive.

        Returns:
            bool: True if connection is alive, False otherwise.
        """
        with self.lock:
            if not self._connected or not self.connection:
                return False

            try:
                # Use Netmiko's built-in is_alive method if available
                if hasattr(self.connection, "is_alive") and callable(self.connection.is_alive):
                    return self.connection.is_alive()
                # Fallback: send empty command as keepalive test
                self.connection.send_command("", expect_string=r">", read_timeout=5)
                return True
            except Exception as e:
                LOGGER.warning(f"Connection check failed for {self.device.hostname or self.device.ip}: {e}")
                self._connected = False
                return False

    def reconnect(self) -> None:
        """Reconnect to the device if connection is lost."""
        LOGGER.info(f"Attempting to reconnect to {self.device.hostname or self.device.ip}")
        self.disconnect()
        time.sleep(RECONNECT_DELAY_SECONDS)
        self.connect()

    def execute_commands(self, commands: Iterable[tuple[str, Callable | None]]) -> str:
        """
        Execute a series of commands on the connected device.

        Args:
            commands (Iterable[tuple[str, Callable | None]]): List of (command, processor) tuples.

        Returns:
            str: Formatted output from all commands.

        Raises:
            Exception: If connection is not established or commands fail.
        """
        with self.lock:
            if not self._connected or not self.connection:
                raise ConnectionError(f"Not connected to {self.device.hostname or self.device.ip}")

            final_res: str = ""
            divider: str = "=" * 25

            for command, func in commands:
                try:
                    LOGGER.debug(f"Executing command on {self.device.hostname}: {command}")
                    con_res: str | list | dict = self.connection.send_command(command)
                    if func is not None:
                        con_res = func(str(con_res))
                    final_res += f"{divider} {command} {divider}\n{con_res}\n\n"
                    LOGGER.info(f"Command executed successfully on {self.device.hostname}: {command}")
                except Exception as e:
                    LOGGER.error(f"Failed to execute command '{command}' on {self.device.hostname}: {e}")
                    final_res += f"{divider} {command} {divider}\nERROR: {e}\n\n"

            return final_res


class PersistentSSHService:
    """
    Background service managing persistent SSH connections to multiple devices.

    This class orchestrates persistent connections to multiple devices and periodically
    executes monitoring commands on them.

    Attributes:
        devices (list[Devices]): List of devices to monitor.
        env_vars (EnvironmentsVariables): Environment configuration.
        interval (int): Interval in seconds between command executions.
        connections (dict): Dictionary mapping device IPs to PersistentSSHConnection instances.
    """

    def __init__(self, devices: list[Devices], env_vars: EnvironmentsVariables, interval: int) -> None:
        """
        Initialize the persistent SSH service.

        Args:
            devices (list[Devices]): List of devices to monitor.
            env_vars (EnvironmentsVariables): Environment configuration.
            interval (int): Interval in seconds between command executions.
        """
        self.devices = devices
        self.env_vars = env_vars
        self.interval = interval
        self.connections: dict[str, PersistentSSHConnection] = {}
        self._reload_lock = threading.Lock()  # Lock for thread-safe reload operations

    def initialize_connections(self) -> None:
        """Establish initial connections to all devices."""
        LOGGER.info(f"Initializing connections to {len(self.devices)} devices")

        for device in self.devices:
            try:
                conn = PersistentSSHConnection(device, self.env_vars)
                conn.connect()
                self.connections[str(device.ip)] = conn
            except Exception as e:
                LOGGER.error(f"Failed to initialize connection to {device.hostname or device.ip}: {e}")

        LOGGER.info(f"Successfully connected to {len(self.connections)}/{len(self.devices)} devices")

    def cleanup_connections(self) -> None:
        """Disconnect from all devices."""
        LOGGER.info("Cleaning up all connections")
        for ip, conn in self.connections.items():
            try:
                conn.disconnect()
            except Exception as e:
                LOGGER.error(f"Error disconnecting from {ip}: {e}")
        self.connections.clear()

    def reload_config(self) -> None:
        """
        Reload configuration from fw_creds.csv and .env file.

        This method re-reads the credentials file and environment variables,
        then updates connections accordingly. Existing connections to devices
        that are still present are kept, new devices are connected, and removed
        devices are disconnected.
        """
        with self._reload_lock:
            LOGGER.info("Reloading configuration from fw_creds.csv and .env file")

            try:
                # Re-read environment variables
                from pathlib import Path

                from dotenv import load_dotenv

                # Reload .env file
                env_file = Path(".env").absolute()
                if env_file.exists():
                    load_dotenv(env_file, override=True)
                    LOGGER.info("Reloaded .env file")

                # Re-create environment variables object
                from models.env import EnvironmentsVariables

                new_env_vars = EnvironmentsVariables()
                self.env_vars = new_env_vars

                # Re-read devices from CSV
                from helper.misc import load_devices_creds

                new_devices = load_devices_creds(file_path=self.env_vars.file_paths.fw_creds)
                LOGGER.info(f"Loaded {len(new_devices)} devices from CSV")

                # Track devices by IP for easy comparison
                new_device_ips = {str(device.ip): device for device in new_devices}
                current_device_ips = {str(device.ip): device for device in self.devices}

                # Disconnect from devices that are no longer in the list
                devices_to_remove = set(current_device_ips.keys()) - set(new_device_ips.keys())
                for ip in devices_to_remove:
                    if ip in self.connections:
                        LOGGER.info(f"Disconnecting from removed device: {ip}")
                        try:
                            self.connections[ip].disconnect()
                            del self.connections[ip]
                        except Exception as e:
                            LOGGER.error(f"Error disconnecting from {ip}: {e}")

                # Connect to new devices
                devices_to_add = set(new_device_ips.keys()) - set(current_device_ips.keys())
                for ip in devices_to_add:
                    device = new_device_ips[ip]
                    LOGGER.info(f"Connecting to new device: {ip}")
                    try:
                        conn = PersistentSSHConnection(device, self.env_vars)
                        conn.connect()
                        self.connections[ip] = conn
                    except Exception as e:
                        LOGGER.error(f"Failed to connect to new device {ip}: {e}")

                # Update the devices list
                self.devices = new_devices

                LOGGER.info(f"Configuration reloaded successfully. Active connections: {len(self.connections)}")

            except Exception as e:
                LOGGER.error(f"Failed to reload configuration: {e}")

    def get_commands_for_device(self, device: Devices) -> Iterable[tuple[str, Callable | None]]:
        """
        Get the list of commands to execute for a device.

        Args:
            device (Devices): The device to get commands for.

        Returns:
            Iterable[tuple[str, Callable | None]]: List of (command, processor) tuples.
        """
        from libs.device_comm import process_high_availability_state, process_resource_utilization, process_system_info

        commands: list[tuple[str, Callable | None]] = [
            ("show system state | match 1minavg", None),
            ("show system disk-space", None),
            ("show session info", process_system_info),
            ("show high-availability state | match State:", process_high_availability_state),
        ]

        if device.monitored:
            commands.append(("show running resource-monitor minute last 2", process_resource_utilization))

        return commands

    def run_monitoring_cycle(self) -> None:
        """Execute one monitoring cycle on all connected devices in parallel."""
        LOGGER.info("Starting monitoring cycle")

        # Get the number of threads to use from environment variables
        max_workers = self.env_vars.conn.num_of_threads

        def monitor_device(ip: str, conn: PersistentSSHConnection) -> tuple[str, str | None]:
            """
            Monitor a single device.

            Args:
                ip (str): Device IP address.
                conn (PersistentSSHConnection): Connection object for the device.

            Returns:
                tuple[str, str | None]: (device_ip, error_message or None)
            """
            try:
                # Check connection health
                if not conn.is_alive():
                    LOGGER.warning(f"Connection to {conn.device.hostname or ip} is not alive, reconnecting")
                    conn.reconnect()

                # Execute commands
                commands = self.get_commands_for_device(conn.device)
                result = conn.execute_commands(commands)

                # Write output to file
                output_file = self.env_vars.file_paths.output_dir.joinpath(f"{conn.device.hostname}.log")
                with open(output_file, "a") as f:
                    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                    f.write(f"\n{'=' * 50}\n")
                    f.write(f"Timestamp: {timestamp}\n")
                    f.write(f"{'=' * 50}\n")
                    f.write(result)

                LOGGER.info(f"Monitoring cycle completed for {conn.device.hostname}")
                return (ip, None)

            except Exception as e:
                LOGGER.error(f"Error during monitoring cycle for {ip}: {e}")
                return (ip, str(e))

        # Use ThreadPoolExecutor to process devices in parallel
        with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="MandiriMona_Monitor") as executor:
            # Submit all device monitoring tasks
            futures = {executor.submit(monitor_device, ip, conn): ip for ip, conn in list(self.connections.items())}

            # Wait for all tasks to complete
            for future in as_completed(futures):
                ip = futures[future]
                try:
                    device_ip, error = future.result()
                    if error:
                        LOGGER.warning(f"Device {device_ip} monitoring failed: {error}")
                except Exception as e:
                    LOGGER.error(f"Unexpected error processing device {ip}: {e}")

        LOGGER.info("Monitoring cycle completed")

    def run(self, shutdown_handler) -> None:
        """
        Run the persistent SSH service.

        Args:
            shutdown_handler: Handler object with should_continue() method to check for shutdown.
        """
        try:
            self.initialize_connections()

            LOGGER.info(f"Starting monitoring service with {self.interval} second interval")

            while shutdown_handler.should_continue():
                self.run_monitoring_cycle()

                # Sleep in small intervals to allow for responsive shutdown
                sleep_time = 0
                while sleep_time < self.interval and shutdown_handler.should_continue():
                    time.sleep(1)
                    sleep_time += 1

        except Exception as e:
            LOGGER.exception(f"Critical error in persistent SSH service: {e}")
        finally:
            self.cleanup_connections()
            LOGGER.info("Persistent SSH service stopped")
