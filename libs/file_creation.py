"""File creation utilities."""

from pathlib import Path
from typing import Iterable

from models.main import Devices

__all___: list[str] = ["create_ssh_config"]


def create_ssh_config(file_path: Path, devices: list[Devices]) -> Iterable[tuple[int, int]]:
    """
    Create an SSH configuration file with specified devices.

    This function generates an SSH config file by writing host configurations for each device
    in the provided list. Each host entry includes the hostname and SSH RSA key algorithm settings.

    Args:
        file_path (Path): The path where the SSH config file will be created/written.
        devices (list[Devices]): A list of Devices objects representing the devices to include in the SSH config.

    Yields:
        tuple[int, int]: A tuple containing:
            - counter (int): The current number of devices processed.
            - dev_len (int): The total number of devices to process.

    Returns:
        Iterable[tuple[int, int]]: An iterable of tuples tracking progress through the device list.

    Example:
        >>> devices = [{'host': 'server1'}, {'host': 'server2'}]
        >>> for current, total in create_ssh_config(Path('/path/to/config'), devices):
        ...     print(f"Processing {current}/{total}")
    """
    dev_len: int = len(devices)
    counter: int = 0
    with file_path.open(mode="w") as f:
        for device in devices:
            counter += 1
            f.writelines(f"Host {device.ip}\n")
            f.writelines("    HostKeyAlgorithms +ssh-rsa\n")
            yield counter, dev_len
