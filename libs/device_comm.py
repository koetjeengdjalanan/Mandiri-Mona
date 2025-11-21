"""Module for SSH communication with network devices and processing command outputs."""

import logging
import re
from typing import Callable, Iterable

from netmiko import NetmikoTimeoutException
from tenacity import before_sleep_log, retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from config.contexts import ssh_connection
from models.env import EnvironmentsVariables
from models.main import Devices

__all__: list[str] = ["iterate_connection", "connect_ssh"]

LOGGER = logging.getLogger("mandiri-mona.device_comm")


def process_high_availability_state(output: str) -> str:
    r"""
    Extract the first line from a multi-line output string.

    This function processes the output of a high availability state command by
    returning only the first line of the output.

    Args:
        output (str): A multi-line string containing the high availability state output.

    Returns:
        str: The first line of the output string.

    Example:
        >>> output = "Active\\nStandby\\nInactive"
        >>> process_high_availability_state(output)
        'Active'
    """
    return output.splitlines()[0]


def process_system_info(output: str) -> str:
    r"""
    Process system information output to filter relevant metrics.

    This function parses system information output and extracts only the lines
    containing specific metrics that are of interest.

    Args:
        output (str): Raw system information output string containing multiple lines
            of key-value pairs separated by ": ".

    Returns:
        str: Filtered output containing only lines with the following metrics:
            - Number of sessions supported
            - Number of allocated sessions
            - Packet rate
            - Throughput
            Each line is separated by newline characters.

    Example:
        >>> raw_output = "Number of sessions supported: 100\\nSome other info: xyz\\nPacket rate: 50"
        >>> process_system_info(raw_output)
        'Number of sessions supported: 100\\nPacket rate: 50'
    """
    included_output_list = ["Number of sessions supported", "Number of allocated sessions", "Packet rate", "Throughput"]
    processed_output = "\n".join([line for line in output.splitlines() if line.split(": ")[0] in included_output_list])
    return processed_output


def process_resource_utilization(output: str) -> str:
    r"""
    Parse and format resource utilization output from network device commands.

    This function processes raw output containing Data Plane (DP) resource utilization
    metrics and reformats it into a more readable, structured format. It extracts
    information about different Data Planes and their associated packet/session metrics.

    Args:
        output (str): Raw output string containing DP resource utilization data.
            Expected format includes DP identifiers followed by metric lines
            with numerical values.

    Returns:
        str: Formatted string where each line contains:
            - DP identifier (e.g., "DP s0p0")
            - Metric labels and their corresponding values, comma-separated

            Example: "DP s0p0 - metric1: 100 200, metric2: 300 400\n"

    The function uses regex patterns to:
        - Split output into chunks per DP
        - Extract DP names (format: "DP <identifier>")
        - Parse metric lines containing labels and numerical values

    If no DP chunks are found, treats the entire output as a single chunk
    with default DP name "DP s0p0".
    """
    expressions: dict[str, str] = {
        "chunk": r"(DP\s+[^:]+:(?:(?!DP\s+)[^\n]*\n)*)",
        "dp_name": r"^(DP\s[\w]+)",
        "packet": r"^(.*\:)\s*\n\s*((?:\d+\s+)+\d+)$",
    }

    res: str = ""
    matches: list[str] = re.findall(expressions["chunk"], output, re.MULTILINE)
    if not matches:
        matches = [output]

    for idx, match in enumerate(matches, 1):
        LOGGER.debug(f"Processing resource utilization chunk {idx}/{len(matches)}")
        match_dp = re.match(expressions["dp_name"], match)
        dp = str(match_dp.group(1)) if match_dp else "DP s0p0"
        sessions_metric: list[tuple[str, str]] = re.findall(expressions["packet"], match, re.MULTILINE)
        tmp = f"{dp} - " + ", ".join(
            [" ".join((re.sub(r"\s+", " ", session) for session in sessions)) for sessions in sessions_metric]
        )
        res += tmp + "\n"
    return res


# TODO: Log for every retry failed attempt with attempt number and exception
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=5),
    retry=retry_if_exception_type((TimeoutError, NetmikoTimeoutException)),
    before_sleep=before_sleep_log(LOGGER, logging.WARNING),
    reraise=True,
)
def connect_ssh(device: Devices, env_vars: EnvironmentsVariables) -> tuple[Devices, str]:
    """
    Establishes an SSH connection to a network device and executes monitoring commands.

    This function connects to a network device via SSH using the provided credentials and
    configuration, retrieves system information, and executes a series of monitoring commands.
    It includes automatic retry logic with exponential backoff for connection reliability.

    Args:
        device (Devices): A Devices object containing device connection information including
            device_type, ip, username, password, and hostname attributes.
        env_vars (EnvironmentsVariables): An EnvironmentsVariables object containing environment
            configuration including SSH config file path and connection timeout settings.

    Returns:
        tuple[Devices, str]: A tuple containing:
            - The updated Devices object with populated hostname
            - A formatted string containing all command outputs separated by dividers

    Raises:
        Exception: Re-raises any exception after 3 retry attempts with exponential backoff
            (2-5 seconds between attempts). Individual command failures are logged but
            don't stop execution of remaining commands.

    Notes:
        - Automatically retrieves and sets the device hostname on first connection
        - Executes standard monitoring commands for all devices
        - Executes additional resource monitoring commands for devices marked as monitored
        - Processes specific command outputs through dedicated processing functions
        - Logs all connection events, command executions, and errors
        - Ensures proper disconnection from the device after command execution
    """
    final_res: str = ""
    divider: str = "=" * 25
    conn_vars: dict[str, str | int] = {
        "device_type": device.device_type,
        "host": str(device.ip),
        "username": device.username,
        "password": device.password,
        "ssh_config_file": str(env_vars.file_paths.sshd_config),
        "conn_timeout": env_vars.conn.conn_timeout,
        "read_timeout_override": env_vars.conn.conn_timeout,
    }
    commands: Iterable[tuple[str, Callable | None]] = [
        ("show system state | match 1minavg", None),
        ("show system disk-space", None),
        ("show session info", process_system_info),
        ("show high-availability state | match State:", process_high_availability_state),
    ]
    if device.monitored:
        commands.append(("show running resource-monitor minute last 2", process_resource_utilization))

    with ssh_connection(conn_vars) as conn_manager:
        LOGGER.info(f"Successfully connected to device {device.hostname or device.ip}")

        hostname = str(
            conn_manager.send_command(command_string="show system info | match hostname", expect_string=r">")
        ).strip("\n")
        device.hostname = hostname.strip().split(" ")[-1]
        final_res += f"{divider} show system info | match hostname {divider}\n{device.hostname}\n\n"

        for command, func in commands:
            LOGGER.debug(f"Executing command on {device.hostname or device.ip}: {command}")
            con_res: str | list | dict = conn_manager.send_command(command)
            if func is not None:
                con_res = func(str(con_res))
            final_res += f"{divider} {command} {divider}\n{con_res}\n\n"
            LOGGER.info(f"Command executed successfully on {device.hostname or device.ip}: {command}")

    LOGGER.debug(f"Disconnected from device {device.hostname or device.ip}")
    return device, final_res


def iterate_connection(devices: list[Devices], env_vars: EnvironmentsVariables) -> list[Devices]:
    """
    Iterate through a list of devices and establish SSH connections to each.

    This function processes a list of devices by attempting to connect to each via SSH,
    logging the output to individual files, and collecting successfully processed devices.

    Args:
        devices (list[Devices]): A list of Device objects to connect to.
        env_vars (EnvironmentsVariables): Environment variables containing configuration
            such as file paths for output logs.

    Returns:
        list[Devices]: A list of successfully processed Device objects.

    Raises:
        No exceptions are raised directly. Errors during individual device processing
        are logged and the iteration continues.

    Notes:
        - Each device's output is written to a separate log file named after the
            device's hostname or IP address.
        - Failed connections are logged but do not stop the iteration.
        - Progress is logged for each device processed.
    """
    processed_devices: list[Devices] = []
    for idx, device in enumerate(devices):
        try:
            dev, res = connect_ssh(device, env_vars)
            with open(env_vars.file_paths.output_dir.joinpath(f"{dev.hostname}.log"), "a") as f:
                f.write(res)
            processed_devices.append(dev)
            LOGGER.info(f"Completed processing for device {dev.hostname} ({idx + 1}/{len(devices)})")
        except Exception as e:
            LOGGER.error(f"Failed processing for device {device.hostname} ({idx + 1}/{len(devices)}): {e}")
            continue
    return processed_devices
