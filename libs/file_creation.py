"""File creation utilities."""

from pathlib import Path
from typing import Iterable

from models.main import Devices

__all___: list[str] = ["create_ssh_config", "update_fw_creds"]


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


def update_fw_creds(file_path: Path, devices: list[Devices]) -> None:
    """
    Update firewall credentials file, only modifying lines that have changed.

    Args:
        file_path (Path): Path to the credentials CSV file.
        devices (list[Devices]): List of device configurations to update.
    """
    with file_path.open(mode="r+") as f:
        lines = f.readlines()
        header = lines[0] if lines else ""

        # Create mapping of existing lines by IP for quick lookup
        existing_devices = {}
        for line in lines[1:]:
            parts = line.strip().split(",")
            if len(parts) >= 2:
                existing_devices[parts[1]] = line

        # Build new content with only changed lines
        new_lines = [header]
        for device in devices:
            new_line = device.as_csv_line
            device_ip = str(device.ip)

            # Only add to write list if line is new or changed
            if device_ip not in existing_devices or existing_devices[device_ip] != new_line:
                new_lines.append(new_line)
            else:
                new_lines.append(existing_devices[device_ip])

        # Write only if content has changed
        new_content = "".join(new_lines)
        old_content = "".join(lines)

        if new_content != old_content:
            f.seek(0)
            f.write(new_content)
            f.truncate()
