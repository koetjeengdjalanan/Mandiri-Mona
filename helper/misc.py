"""Miscellaneous helper functions."""

import csv
import logging
from ipaddress import AddressValueError, IPv4Address, NetmaskValueError
from pathlib import Path
from typing import Any

from models.main import Devices

LOGGER = logging.getLogger("mandiri-mona")

__all__: list[str] = ["split_equally", "load_devices_creds"]


def split_equally(item: list[Any], n: int) -> list[list[Any]]:
    """
    Split a list into n approximately equal parts.

    Args:
        item (list[Any]): The list to be split.
        n (int): The number of parts to split the list into.

    Returns:
        item[list[Any]]: A list containing n sublists, each being a part of the original list.
    """
    k, m = divmod(len(item), n)
    return [item[i * k + min(i, m) : (i + 1) * k + min(i + 1, m)] for i in range(n)]


def load_devices_creds(file_path: Path) -> list[Devices]:
    """Load device credentials from a CSV file.

    Reads a CSV file and parses each row into a Devices object with device
    configuration details including device type, IP address, credentials,
    hostname, and monitoring status.

    Args:
        file_path: Path object pointing to the CSV file containing device credentials.

    Returns:
        A list of Devices objects parsed from the CSV file.

    Raises:
        FileNotFoundError: If the specified file does not exist.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    devices_creds: list[Devices] = []
    with open(file=file_path, mode="r") as csvfile:
        reader = csv.DictReader(csvfile)
        for row_num, row in enumerate(reader, start=1):
            try:
                devices_creds.append(
                    Devices(
                        device_type=row.get("device_type", ""),
                        ip=IPv4Address(row.get("ip", "")),
                        username=row.get("username", ""),
                        password=row.get("password", ""),
                        hostname=row.get("hostname", None),
                        monitored=row.get("monitored", "False").lower() == "true",
                    )
                )
            except (AddressValueError, NetmaskValueError) as e:
                message = f"Invalid IP address in row {file_path}:{row_num+1}\n{type(e).__name__}: {e}"
                LOGGER.warning(message)
                continue
    return devices_creds
