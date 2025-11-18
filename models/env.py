"""Environment variable settings."""

from os import getenv
from pathlib import Path
from typing import Annotated, Literal

from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator

from helper.default_handler import create_filedir


class ConnectionSettings(BaseModel):
    """
    Configuration model for connection settings.

    This class defines connection-related parameters that can be configured
    through environment variables or use default values.

    Attributes:
        max_retry (int): Maximum number of retry attempts for failed connections.
            Defaults to 3. Can be overridden by MAX_RETRY environment variable.
        conn_timeout (int): Connection timeout in seconds.
            Defaults to 30. Can be overridden by CONN_TIMEOUT environment variable.
        read_timeout_override (int): Read timeout override value in seconds.
            Defaults to 60. Can be overridden by READ_TIMEOUT_OVERRIDE environment variable.
        num_of_threads (int): Number of threads to use for concurrent operations.
            Defaults to 10. Can be overridden by NUM_OF_THREADS environment variable.
    """

    max_retry: int = int(getenv("MAX_RETRY", "3"))
    conn_timeout: int = int(getenv("CONN_TIMEOUT", "30"))
    read_timeout_override: int = int(getenv("READ_TIMEOUT_OVERRIDE", "60"))
    num_of_threads: int = int(getenv("NUM_OF_THREADS", "10"))

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

    log_file_path: Path = Path(getenv("LOG_FILE_PATH", "./mandiri-MONA.log"))
    log_rotate_time: str = str(getenv("LOG_ROTATE_TIME", "w0"))
    log_backup_count: int = int(getenv("LOG_BACKUP_COUNT", "9"))
    log_format: str = "%(asctime)s - %(levelname)s - %(message)s"
    log_datetime_format: str = str(getenv("LOG_DATETIME_FORMAT", "%Y-%m-%d %H:%M:%S"))

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
    Configuration model for file paths used in the application.

    This class defines the file path configurations for various components of the
    BMRI monitoring automation system. All paths can be overridden using environment
    variables.

    Attributes:
        fw_creds (Path): Path to the firewall credentials CSV file.
            Defaults to "./configs/fw_creds.csv".
            Override with FW_CREDS_PATH environment variable.
        sshd_config (Path): Path to the SSH daemon configuration file.
            Defaults to "./configs/sshd_config".
            Override with SSHD_CONFIG_PATH environment variable.
        output_dir (Path): Path to the output directory for generated files.
            Defaults to "./outputs/".
            Override with OUTPUT_DIR_PATH environment variable.

    Example:
        >>> config = FilePathConfig()
        >>> print(config.fw_creds)
        configs/fw_creds.csv

        >>> # Using environment variables
        >>> import os
        >>> os.environ['FW_CREDS_PATH'] = '/custom/path/creds.csv'
        >>> config = FilePathConfig()
        >>> print(config.fw_creds)
        /custom/path/creds.csv
    """

    fw_creds: Path = Path(getenv("FW_CREDS_PATH", "./configs/fw_creds.csv"))
    sshd_config: Path = Path(getenv("SSHD_CONFIG_PATH", "./configs/sshd_config"))
    output_dir: Path = Path(getenv("OUTPUT_DIR_PATH", "./outputs/"))

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
    A Pydantic model that encapsulates all environment variables used in the application.

    This class reads configuration from environment variables and provides strongly-typed
    access to application settings including debug mode, logging level, database connection
    settings, and logging configuration.

    Attributes:
        debug_mode (bool): Enables debug mode when set to true. Reads from DEBUG_MODE
            environment variable. Accepts values: "true", "1", "t" (case-insensitive).
            Defaults to False.
        log_level (str): Sets the application logging level. Reads from LOG_LEVEL
            environment variable. Defaults to "INFO". Value is automatically converted
            to uppercase.
        verbose_mode (bool): User verbosity flag. Defaults to False.
        file_paths (FilePathConfig): File path configuration settings encapsulated
            in a FilePathConfig object.
        conn (ConnectionSettings): Database connection configuration settings encapsulated
            in a ConnectionSettings object.
        logging (LoggingSettings): Application logging configuration settings encapsulated
            in a LoggingSettings object.

    Example:
        >>> env = EnvironmentsVariables()
        >>> env.debug_mode
        False
        >>> env.log_level
        'INFO'
    """

    debug_mode: bool = bool(getenv("DEBUG_MODE", "False").lower() in ("true", "1", "t"))
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default=getenv("LOG_LEVEL", "INFO").upper()
    )
    verbose: Annotated[bool, "User verbosity flag"] = False
    file_paths: FilePathConfig = Field(default_factory=FilePathConfig)
    conn: ConnectionSettings = Field(default_factory=ConnectionSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)

    def __init__(self, **data):
        load_dotenv(dotenv_path=Path("./.env").absolute())
        super().__init__(**data)
