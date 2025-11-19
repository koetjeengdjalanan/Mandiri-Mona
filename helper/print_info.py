"""Helper function to print requested information."""

from csv import DictReader

from rich.console import Console
from rich.table import Table

from models.env import EnvironmentsVariables

__all__: list[str] = ["info_request"]


def info_request(requests: list[str], console: Console, env: EnvironmentsVariables) -> None:
    """
    Display requested information about devices and environment variables.

    This function prints formatted information based on the user's request. It can display
    device information from a CSV file and/or environment variables in JSON format.

    Args:
        requests (list[str]): A list of information types to display. Valid options are
            "devices", "env", and "all". If "all" is included, it displays all available
            information types.
        console (Console): A Rich Console instance used for formatted output to the terminal.
        env (EnvironmentsVariables): An object containing environment variables and file paths,
            including the path to the devices CSV file.

    Returns:
        None: This function prints directly to the console and does not return a value.

    Note:
        - The devices CSV file is expected to have a header line followed by rows with
            comma-separated values: hostname, ip_address, model, os_version.
        - Device information is displayed in a formatted table with colored columns.
        - Environment variables are displayed as pretty-printed JSON with 4-space indentation.
    """
    choices = ["devices", "env"] if "all" in requests else requests
    if "devices" in choices:
        table = Table(title="Device Information")
        table.add_column("Hostname", style="cyan", no_wrap=True)
        table.add_column("IP Add", style="magenta")
        table.add_column("Username", style="green")
        table.add_column("Password", style="yellow")

        with open(env.file_paths.fw_creds, "r") as f:
            reader = DictReader(f)
            for row in reader:
                if not all(k in row for k in ["device_type", "host", "username", "password"]):
                    console.print(f"[red]Skipping malformed row:[/red] {row}")
                    continue
                table.add_row(row["device_type"], row["host"], row["username"], row["password"])
        console.print(table)
    if "env" in choices:
        console.rule(title="[bold]Environment Variables:[/bold]", style="blue", characters="=")
        console.print_json(env.model_dump_json(), indent=4)
