"""Environment variable settings."""

from os import getenv
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, DirectoryPath, Field, FilePath, PositiveInt, StrictBool, field_validator

from helper.default_handler import create_filedir


class ConnectionSettings(BaseModel):
    """
    Configuration model for connection and concurrency settings.

    This class defines the connection parameters and threading configuration used
    throughout the application. All values can be overridden via environment variables.

    Attributes:
        max_retry (PositiveInt): Maximum number of retry attempts for failed connections.
            Default: 3 (from MAX_RETRY env var)
        conn_timeout (PositiveInt): Connection timeout in seconds.
            Default: 30 (from CONN_TIMEOUT env var)
        read_timeout_override (PositiveInt): Read timeout override value in seconds.
            Default: 60 (from READ_TIMEOUT_OVERRIDE env var)
        num_of_threads (PositiveInt): Number of threads to use for concurrent operations.
            Default: 8 (from NUM_OF_THREADS env var)

    Validation Rules:
        - max_retry: Must be at least 1
        - conn_timeout: Must be positive (> 0)
        - read_timeout_override: Must be positive (> 0)
        - num_of_threads: Must be between 1 and 100 (inclusive)

    Raises:
        ValueError: If any field fails its validation constraints

    Example:
        >>> settings = ConnectionSettings()
        >>> settings.max_retry
        3
        >>> settings = ConnectionSettings(max_retry=5, num_of_threads=16)
        >>> settings.num_of_threads
        16
    """

    max_retry: PositiveInt = Field(
        int(getenv("MAX_RETRY", "3")), description="Maximum number of retry attempts for failed connections"
    )
    conn_timeout: PositiveInt = Field(int(getenv("CONN_TIMEOUT", "30")), description="Connection timeout in seconds")
    read_timeout_override: PositiveInt = Field(
        int(getenv("READ_TIMEOUT_OVERRIDE", "60")), description="Read timeout override value in seconds"
    )
    num_of_threads: PositiveInt = Field(
        int(getenv("NUM_OF_THREADS", "8")), description="Number of threads to use for concurrent operations"
    )

    @field_validator("conn_timeout", "read_timeout_override")
    @classmethod
    def validate_positive_timeout(cls, v: int) -> int:
        """Validation classmethod."""
        if v <= 0:
            raise ValueError("Timeout values must be positive")
        return v

    @field_validator("max_retry")
    @classmethod
    def validate_retry_count(cls, v: int) -> int:
        """Validation classmethod."""
        if v < 1:
            raise ValueError("max_retry must be at least 1")
        return v

    @field_validator("num_of_threads")
    @classmethod
    def validate_thread_count(cls, v: int) -> int:
        """Validation classmethod."""
        if not 1 <= v <= 100:
            raise ValueError("num_of_threads must be between 1 and 100")
        return v


class LoggingSettings(BaseModel):
    """
    Configuration model for application logging settings.

    This class defines the logging configuration parameters used throughout the application,
    with values loaded from environment variables or sensible defaults.

    Attributes:
        log_file_path (Path): The file path where log files will be stored.
            Defaults to "./mandiri-MONA.log" if LOG_FILE_PATH environment variable is not set.
        log_rotate_time (str): The time interval for log rotation.
            Defaults to "w0" (weekly rotation on Monday) if LOG_ROTATE_TIME environment variable is not set.
            Common values: 'D' (daily), 'W0-W6' (weekly on specific day), 'midnight' (daily at midnight).
        log_backup_count (int): The number of backup log files to retain.
            Defaults to 9 if LOG_BACKUP_COUNT environment variable is not set.
        log_format (str): The format string for log messages.
            Defaults to "%(asctime)s - %(levelname)s - %(message)s".
        log_datetime_format (str): The datetime format string for log messages.
            Defaults to "%Y-%m-%d %H:%M:%S" if LOG_DATETIME_FORMAT environment variable is not set.

    Environment Variables:
        LOG_FILE_PATH: Path to the log file (optional)
        LOG_ROTATE_TIME: Log rotation interval (optional)
        LOG_BACKUP_COUNT: Number of backup logs to keep (optional)
        LOG_FORMAT: Log message format (optional)
        LOG_DATETIME_FORMAT: Log datetime format (optional)

    Example:
        >>> settings = LoggingSettings()
        >>> print(settings.log_file_path)
        mandiri-MONA.log
    """

    log_file_path: FilePath = Field(
        Path(getenv("LOG_FILE_PATH", "./mandiri-MONA.log")).absolute(), description="Path to the log file"
    )
    log_rotate_time: str = Field(str(getenv("LOG_ROTATE_TIME", "w0")), description="Log rotation interval")
    log_backup_count: int = Field(
        int(getenv("LOG_BACKUP_COUNT", "9")), description="Number of backup log files to retain"
    )
    log_format: str = Field("%(asctime)s - %(levelname)s - %(message)s", description="Log message format")
    log_datetime_format: str = Field(
        str(getenv("LOG_DATETIME_FORMAT", "%Y-%m-%d %H:%M:%S")), description="Log datetime format"
    )

    @field_validator("log_file_path", mode="before")
    @classmethod
    def validate_log_file_path(cls, v: Path) -> Path:
        """Validate that the log file path points to a valid `.log` file and create the file if it does not exist."""
        path = Path(v) if isinstance(v, str) else v
        if path.suffix != ".log":
            raise ValueError("Log file path must point to a valid `.log` file.")
        if not path.exists():
            path = create_filedir(path, "file")
        return path


class FilePathConfig(BaseModel):
    """
    Configuration model for managing file and directory paths in the application.

    This class validates and manages paths for firewall credentials, SSH daemon configuration,
    and output directory. It automatically creates missing files and directories during validation.

    Attributes:
        fw_creds (FilePath): Path to the firewall credentials CSV file.
            Defaults to './configs/fw_creds.csv' or the value of FW_CREDS_PATH environment variable.
        sshd_config (FilePath): Path to the SSH daemon configuration file.
            Defaults to './configs/sshd_config' or the value of SSHD_CONFIG_PATH environment variable.
        output_dir (DirectoryPath): Path to the output directory.
            Defaults to './outputs/' or the value of OUTPUT_DIR_PATH environment variable.

    Notes:
        - All paths are validated before assignment
        - Missing files and directories are automatically created during validation
        - Environment variables take precedence over default values
    """

    fw_creds: FilePath = Field(
        Path(getenv("FW_CREDS_PATH", "./configs/fw_creds.csv")).absolute(),
        description="Path to firewall credentials CSV file.",
    )
    sshd_config: FilePath = Field(
        Path(getenv("SSHD_CONFIG_PATH", "./configs/sshd_config")).absolute(),
        description="Path to SSH daemon configuration file.",
    )
    output_dir: DirectoryPath = Field(
        Path(getenv("OUTPUT_DIR_PATH", "./outputs/")).absolute(), description="Path to output directory."
    )

    @field_validator("fw_creds", "sshd_config", mode="before")
    @classmethod
    def validate_file_paths(cls, v: Path) -> Path:
        """Validate that the file paths point to valid files and create the files if they do not exist."""
        path = Path(v) if isinstance(v, str) else v
        if not path.exists():
            path = create_filedir(path, "file")
        return path

    @field_validator("output_dir", mode="before")
    @classmethod
    def validate_output_dir(cls, v: Path) -> Path:
        """Validate that the output directory path points to a valid directory and create it if it does not exist."""
        path = Path(v) if isinstance(v, str) else v
        if not path.exists():
            path = create_filedir(path, "dir")
        return path


class EnvironmentsVariables(BaseModel):
    """
    Pydantic model for managing application environment variables and configuration settings.

    This class handles the loading and validation of environment variables from a .env file,
    providing structured access to various configuration settings including debug mode,
    logging configuration, file paths, and connection settings.

    Attributes:
        debug_mode (StrictBool): Flag to enable debug mode. Reads from DEBUG_MODE environment
            variable. Accepts "true", "1", or "t" (case-insensitive) as True values.
        log_level (Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]): The logging
            level for the application. Defaults to "INFO" if not specified.
        verbose (StrictBool): User verbosity flag. When set to True, changes the debug
            level to DEBUG. Defaults to False.
        file_paths (FilePathConfig): Configuration object for file paths used by the
            application. Created using default factory.
        conn (ConnectionSettings): Configuration object for connection settings.
            Created using default factory.
        logging (LoggingSettings): Configuration object for logging settings.
            Created using default factory.

    Example:
        >>> env = EnvironmentsVariables()
        >>> print(env.debug_mode)
        False
        >>> print(env.log_level)
        'INFO'

    Note:
        The .env file is expected to be located at the root of the project directory.
        Environment variables are automatically loaded during initialization.
    """

    debug_mode: StrictBool = Field(
        bool(getenv("DEBUG_MODE", "False").lower() in ("true", "1", "t")), description="Enables debug mode"
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", description="Logging level for the application"
    )
    verbose: StrictBool = Field(False, description="User verbosity flag, will change debug level to DEBUG if set")
    file_paths: FilePathConfig = Field(default_factory=FilePathConfig)
    conn: ConnectionSettings = Field(default_factory=ConnectionSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)

    @field_validator("log_level", mode="before")
    @classmethod
    def validate_log_level(cls, v: str | None) -> str:
        """Validate and convert log level from environment variable."""
        if v is None:
            v = getenv("LOG_LEVEL", "INFO")
        level = str(v).upper()
        valid_levels: set[str] = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if level not in valid_levels:
            raise ValueError(f"log_level must be one of {valid_levels}")
        return level
