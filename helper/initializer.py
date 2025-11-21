"""Project Initializer Module."""

from os import getenv
from pathlib import Path
from typing import Generator

__all__: list[str] = ["create_env", "initialize", "isallexists"]


def isallexists(paths: list[tuple[Path, str]]) -> list[list[bool | str | None]]:
    """
    Check if all specified paths exist and match their expected types.

    Args:
        paths (list[Path, str]): A list of tuples where each tuple contains:
            - path (Path): A Path object to check
            - type (str): Expected type of the path, either "file" or "dir"

    Returns:
        list[list[bool, str | None]]: A list of results for each path, where each result is a list containing:
            - [0] (bool): True if the path exists, False otherwise
            - [1] (bool): True if the path matches the expected type (file or directory), False otherwise
            - [2] (str | None): None if no error occurred, or an error message string if an OSError was raised

    Example:
        >>> from pathlib import Path
        >>> paths = [(Path("/tmp/test.txt"), "file"), (Path("/tmp/testdir"), "dir")]
        >>> results = isallexists(paths)
        >>> # Returns [[True, True, None], [True, False, None]] if test.txt exists and testdir doesn't
    """
    res = []
    for path, type in paths:
        temp = []
        try:
            temp.append(path.exists())
            temp.append(path.is_file() if type == "file" else path.is_dir())
            temp.append(None)
        except OSError as err:
            print(err)
            for idx in range(2):
                try:
                    temp[idx] = temp[idx]
                except IndexError:
                    temp.append(False)
            temp.append(f"Error accessing path: {path}, {err}")
        finally:
            res.append(temp)
            continue
    return res


def initialize(missing: list[str]) -> Generator[Path, None, list[Path]]:
    """
    Initialize missing files and directories required by the application.

    This generator function creates necessary files and directories based on the
    provided list of missing items. It yields each created Path object as it's
    created and returns a list of all created paths at the end.

    Args:
        missing (list[str]): A list of strings indicating which files/directories
            are missing and need to be created. Valid values include:
            - "logs": Creates log file and directory
            - "fw_creds.csv": Creates firewall credentials CSV file with header
            - "sshd_config": Creates SSH daemon configuration file
            - "outputs": Creates output directory

    Yields:
        Path: Each created file or directory path as it's initialized.

    Returns:
        list[Path]: A list of all Path objects that were created during initialization.

    Environment Variables:
        LOG_FILE_PATH (str): Path for log file. Defaults to "./mandiri-MONA.log"
        FW_CREDS_PATH (str): Path for firewall credentials CSV. Defaults to "./configs/fw_creds.csv"
        SSHD_CONFIG_PATH (str): Path for SSH config. Defaults to "./configs/sshd_config"
        OUTPUT_DIR_PATH (str): Path for output directory. Defaults to "./outputs/"

    Note:
        - Directories are created with mode 0o755 (rwxr-xr-x)
        - Files are created with mode 0o644 (rw-r--r--)
        - The fw_creds.csv file is initialized with a header row
    """
    created_paths: list[Path] = []
    if "logs" in missing:
        log_path = Path(getenv("LOG_FILE_PATH", "./mandiri-MONA.log"))
        log_path.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
        log_path.touch(exist_ok=True, mode=0o644)
        yield log_path
        created_paths.append(log_path)
    if "fw_creds.csv" in missing:
        fw_creds_path = Path(getenv("FW_CREDS_PATH", "./configs/fw_creds.csv"))
        fw_creds_path.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
        fw_creds_path.touch(exist_ok=True, mode=0o644)
        yield fw_creds_path
        created_paths.append(fw_creds_path)
        with open(fw_creds_path, "w") as f:
            f.write("device_type,ip,username,password,hostname,monitored\n")
    if "sshd_config" in missing:
        sshd_config_path = Path(getenv("SSHD_CONFIG_PATH", "./configs/sshd_config"))
        sshd_config_path.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
        sshd_config_path.touch(exist_ok=True, mode=0o644)
        yield sshd_config_path
        created_paths.append(sshd_config_path)
    if "outputs" in missing:
        output_dir_path = Path(getenv("OUTPUT_DIR_PATH", "./outputs/"))
        output_dir_path.mkdir(parents=True, exist_ok=True, mode=0o755)
        yield output_dir_path
        created_paths.append(output_dir_path)
    return created_paths


def create_env() -> bool:
    """
    Create a default environment configuration file (.env) with predefined settings.

    This function generates a .env file containing default configuration values for
    debugging, logging, connection settings, and file paths. The file is created at
    the location specified by the MANDIRI_MONA_ENV environment variable, or defaults
    to the parent directory of the current file if the variable is not set.

    Returns:
        bool: True if the .env file was successfully created.

    Environment Variables:
        MANDIRI_MONA_ENV (str, optional): Custom path for the .env file location.
            If not set, defaults to the parent directory of the current script.

    Generated Configuration Sections:
        - Debug and Logging Configuration: DEBUG_MODE, LOG_LEVEL
        - Connection Settings: MAX_RETRY, CONN_TIMEOUT, READ_TIMEOUT_OVERRIDE, NUM_OF_THREADS
        - Logging Settings: LOG_FILE_PATH, LOG_ROTATE_TIME, LOG_BACKUP_COUNT, LOG_DATETIME_FORMAT
        - File Path Configuration: FW_CREDS_PATH, SSHD_CONFIG_PATH, OUTPUT_DIR_PATH

    Note:
        This function will overwrite any existing .env file at the target location.
    """
    example_env = """# Debug and Logging Configuration
DEBUG_MODE=False
LOG_LEVEL=INFO

# Connection Settings
MAX_RETRY=3
CONN_TIMEOUT=30
READ_TIMEOUT_OVERRIDE=60
NUM_OF_THREADS=10

# Logging Settings
LOG_FILE_PATH=./mandiri-MONA.log
LOG_ROTATE_TIME=w0
LOG_BACKUP_COUNT=9
LOG_DATETIME_FORMAT=%Y-%m-%d %H:%M:%S

# File Path Configuration
FW_CREDS_PATH=./configs/fw_creds.csv
SSHD_CONFIG_PATH=./configs/sshd_config
OUTPUT_DIR_PATH=./outputs/
"""
    env_path = Path(getenv("MANDIRI_MONA_ENV") or Path(__file__).resolve().parents[1] / ".env")
    with open(env_path, "w") as f:
        f.write(example_env)
    return True
