# Mandiri-Mona

**Mandiri MONA** (MONitoring Automation) - A robust network device SSH monitoring automation tool for firewall and network infrastructure management.

## Overview

Mandiri-Mona is a Python-based automation tool designed for efficient monitoring of network devices (primarily Palo Alto firewalls) via SSH. It provides automated collection of system metrics, resource utilization, and high availability states with multi-threaded execution and intelligent retry logic.

## Key Features

### Core Capabilities
- **Multi-threaded SSH Connection Handling** - Concurrent device monitoring with configurable thread pools
- **Network Device Resource Monitoring** - Automated collection of:
  - CPU utilization and system load (1-minute average)
  - Disk space usage
  - Session information (allocated/supported sessions, packet rate, throughput)
  - High availability state monitoring
  - Data Plane resource utilization metrics
- **Intelligent Retry Logic** - Exponential backoff with configurable retry attempts
- **CSV-based Device Management** - Simple credential and device configuration via CSV files
- **Centralized Logging** - Structured logging with rotation and multiple log levels
- **SSH Configuration Management** - Automatic SSH config generation for managed devices
- **Flexible Command-Line Interface** - Multiple operation modes and information display options

### Advanced Features
- Selective resource monitoring per device (configurable via `monitored` flag)
- Thread-safe file operations for concurrent output writing
- Rich console output with progress tracking
- Detailed error handling and reporting
- Pre-commit hooks for code quality
- Comprehensive configuration via environment variables

## Installation

### Prerequisites
- Python 3.12+
- `uv` package manager (recommended) or `pip`

### Setup
```bash
# Install uv package manager
pip install uv
uv sync

# Or using pip
pip install -r requirements.txt
```

## Configuration

### 1. Environment Setup
Copy `.env.example` to `.env` and configure settings:
```bash
cp .env.example .env
```

### 2. Environment Variables
Edit `.env` with your configuration:

```ini
# Debug and Logging Configuration
DEBUG_MODE=False
LOG_LEVEL=INFO

# Connection Settings
MAX_RETRY=3                    # Number of retry attempts for SSH connections
CONN_TIMEOUT=30                # Connection timeout in seconds
READ_TIMEOUT_OVERRIDE=60       # Read timeout override in seconds
NUM_OF_THREADS=10              # Number of concurrent SSH connections

# Logging Settings
LOG_FILE_PATH=./logs/app.log   # Path to application log file
LOG_ROTATE_TIME=w0             # Log rotation time (weekly on Monday)
LOG_BACKUP_COUNT=9             # Number of backup log files to keep
LOG_DATETIME_FORMAT=%Y-%m-%d %H:%M:%S

# File Path Configuration
FW_CREDS_PATH=./configs/fw_creds.csv      # Device credentials CSV
SSHD_CONFIG_PATH=./configs/sshd_config    # SSH configuration file
OUTPUT_DIR_PATH=./outputs/                # Output directory for device logs
```

### 3. Initialize Required Files
```bash
python main.py --init
```

This creates:
- `./configs/fw_creds.csv` - Device credentials file
- `./configs/sshd_config` - SSH configuration
- `./logs/` - Log directory
- `./outputs/` - Output directory for device logs

### 4. Device Configuration
Edit `./configs/fw_creds.csv` with your device information:
```csv
device_type,ip,username,password,hostname,monitored
paloalto_panos,192.168.1.1,admin,password123,some-device-01,True
paloalto_panos,192.168.1.2,admin,password456,some-device-02,False
```

## Usage

### Basic Usage
```bash
python main.py
```

### Command-Line Options

```bash
# Display help
python main.py --help

# Initialize required files and directories
python main.py --init

# Enable verbose output
python main.py --verbose

# Enable debug mode (more detailed logging and error handling)
python main.py --debug

# Set specific log level
python main.py --log-level DEBUG

# List device information
python main.py --list devices

# List environment variables
python main.py --list env

# List all information
python main.py --list all

# Display version
python main.py --version
```

> [!CAUTION]
> Never use `--debug` on production cron job! this will inflate your log file and make your life difficult!

### Monitoring Commands Executed

The tool automatically executes the following commands on each device:

**Standard Commands (all devices):**
- `show system state | match 1minavg` - CPU and load averages
- `show system disk-space` - Disk utilization
- `show session info` - Session statistics (filtered: supported/allocated sessions, packet rate, throughput)
- `show high-availability state | match State:` - HA state

**Additional Commands (for monitored devices):**
- `show running resource-monitor minute last 2` - Detailed resource utilization per Data Plane

## Output

### Log Files
- Application logs: `./logs/app.log` (with automatic rotation)
- Device output: `./outputs/<hostname>.log` (one file per device)

### Device Output Format
Each device log contains timestamped command outputs:
```
========================= show system info | match hostname =========================
firewall-01

========================= show system state | match 1minavg =========================
1minavg: 0.00
...
```

## Development

### Code Quality Tools

The project includes several code quality tools:

```bash
# Format code with black
black .

# Sort imports with isort
isort .

# Lint with ruff
ruff check .

# Run pre-commit hooks
pre-commit run --all-files
```

### Testing
```bash
# Run tests with pytest
pytest

# Run tests with coverage
pytest --cov=.
```

### Project Structure
```
mandiri-mona/
├── config/              # Configuration modules
│   ├── argument_parser.py  # CLI argument parsing
│   └── contexts.py         # Context managers (SSH, logging)
├── helper/              # Helper utilities
│   ├── initializer.py      # File/directory initialization
│   ├── logging.py          # Logging configuration
│   ├── misc.py             # Miscellaneous utilities
│   └── print_info.py       # Information display
├── libs/                # Core libraries
│   ├── device_comm.py      # SSH communication and command processing
│   └── file_creation.py    # SSH config and credential file management
├── models/              # Data models
│   ├── env.py              # Environment variable models
│   └── main.py             # Device models
├── main.py              # Application entry point
├── pyproject.toml       # Project configuration
└── README.md            # This file
```

## Requirements
- Python 3.12+
- Key dependencies:
  - `netmiko` - Network device SSH communication
  - `pydantic` - Data validation
  - `python-dotenv` - Environment variable management
  - `rich` - Terminal formatting
  - `tenacity` - Retry logic

See `pyproject.toml` for complete dependency list and version requirements.

## License

Copyright 2025 Mandiri MONA Contributors

## Contributing

Contributions are welcome! Please ensure code follows the project's style guidelines:
- Use Black for code formatting (line length: 120)
- Follow Google-style docstrings
- Maintain type hints
- Run pre-commit hooks before committing