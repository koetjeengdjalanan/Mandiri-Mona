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
        # Build a mapping from device IP to device object for quick lookup
        device_map = {str(device.ip): device for device in devices}
        # Iterate over all existing lines (excluding header)
        for line in lines[1:]:
            parts = line.strip().split(",")
            if len(parts) >= 2:
                ip = parts[1]
                if ip in device_map:
                    # Update line for processed device
                    new_lines.append(device_map[ip].as_csv_line)
                else:
                    # Preserve original line for unprocessed device
                    new_lines.append(line)
        # Add any new devices not already in the file
        for ip, device in device_map.items():
            if ip not in existing_devices:
                new_lines.append(device.as_csv_line)

        # Write only if content has changed
        new_content = "".join(new_lines)
        old_content = "".join(lines)

        if new_content != old_content:
            f.seek(0)
            f.write(new_content)
            f.truncate()
