"""Collection of context managers for various application contexts."""

from contextlib import contextmanager
from logging.handlers import QueueListener
from queue import Queue
from typing import Generator, Literal

from influxdb_client.client.influxdb_client import InfluxDBClient
from netmiko import BaseConnection, ConnectHandler
from rich.console import Console

from helper.logging import listener
from models.env import LoggingSettings


@contextmanager
def logging_context(
    settings: LoggingSettings,
    console: Console,
    log_queue: Queue,
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO",
) -> Generator[QueueListener, None, None]:
    """
    Context manager for setting up and managing a logging system with queue-based handling.

    This context manager initializes a QueueListener for handling log records from a queue,
    starts the listener, yields it for use within the context, and ensures proper cleanup
    by stopping the listener when the context exits.

    Args:
        settings (LoggingSettings): Configuration settings for the logging system.
        console (Console): Console object for output handling (likely from rich library).
        log_queue (Queue, optional): Queue for collecting log records. Defaults to an
            unbounded Queue (maxsize=-1).
        level (Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], optional):
            Logging level threshold. Defaults to "INFO".

    Yields:
        QueueListener: The active queue listener instance that processes log records
            from the queue.

    Example:
        >>> with logging_context(settings, console) as listener:
        ...     # Logging operations happen here
        ...     logger.info("Message will be processed by the listener")
    """
    log_listener: QueueListener = listener(
        log_queue=log_queue,
        settings=settings,
        console=console,
        level=level,
    )
    log_listener.start()
    try:
        yield log_listener
    finally:
        log_listener.stop()


@contextmanager
def ssh_connection(conn_vars: dict) -> Generator[BaseConnection, None, None]:
    """
    Context manager for SSH connections using Netmiko's ConnectHandler.

    Args:
        conn_vars (dict): Dictionary containing connection parameters for SSH connection.
            Expected keys may include 'device_type', 'host', 'username', 'password', etc.

    Yields:
        BaseConnection: An active SSH connection object that can be used to execute commands.

    Example:
        >>> conn_params = {
        ...     'device_type': 'cisco_ios',
        ...     'host': '192.168.1.1',
        ...     'username': 'admin',
        ...     'password': 'password'
        ... }
        >>> with ssh_connection(conn_params) as conn:
        ...     output = conn.send_command('show version')

    Note:
        The connection is automatically closed when exiting the context manager,
        even if an exception occurs during the connection lifetime.
    """
    connection = ConnectHandler(**conn_vars)
    try:
        yield connection
    finally:
        connection.disconnect()


@contextmanager
def influx_connection(conn_vars: dict) -> Generator[InfluxDBClient, None, None]:
    """
    Context manager for InfluxDB client connection.

    Creates and manages an InfluxDB client connection with automatic cleanup.
    Ensures the client connection is properly closed after use.

    Args:
        conn_vars: Dictionary containing InfluxDB connection parameters
            (url, token, org, etc.).

    Yields:
        InfluxDBClient: An initialized InfluxDB client instance ready for operations.

    Example:
        >>> conn_params = {
        ...     'url': 'http://localhost:8086',
        ...     'token': 'my-token',
        ...     'org': 'my-org'
        ... }
        >>> with influx_connection(conn_params) as influx_client:
        ...     query_api = influx_client.query_api()
    """
    influx_client = InfluxDBClient(**conn_vars)
    try:
        yield influx_client
    finally:
        influx_client.close()
