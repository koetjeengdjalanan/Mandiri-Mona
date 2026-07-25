# Mandiri-Mona

**Mandiri MONA** (MONitoring Automation) - A robust network device SSH monitoring automation tool for firewall and network infrastructure management.

## Overview

Mandiri-Mona is a Python-based automation tool designed for efficient monitoring of network devices (primarily Palo Alto firewalls) via SSH. It collects system metrics, resource utilization, and high availability states with multi-threaded execution and intelligent retry logic.

It runs in two ways:

- **One-time (normal) mode** – processes every device once, then exits. Useful for cron.
- **Daemon mode** – runs as a background service with **persistent SSH connections**, executing commands on a fixed interval and pushing parsed metrics to **InfluxDB** (a time-series database).

Collected metrics can be delivered through one of two output formats:

- **InfluxDB output (default)** – command output is parsed into structured metrics and written to InfluxDB for dashboards/alerting.
- **Compatibility output** (`--compatibility-mode`) – raw, human-readable command output is appended to per-device `.log` files.

## Key Features

### Core Capabilities
- **Persistent & Multi-threaded SSH** - Long-lived connections in daemon mode plus a configurable thread pool for concurrent device processing
- **Network Device Resource Monitoring** - Automated collection of:
  - CPU utilization (hardware and per-dataplane), memory usage, and system load (1-minute average)
  - Disk space usage (parsed to structured JSON)
  - Session information (allocated/supported sessions, packet rate, throughput)
  - High availability state, synchronization state, and running-config sync
  - Data Plane packet buffer / packet descriptor utilization
  - Operational mode
- **InfluxDB Integration** - Parsed metrics written to InfluxDB with a persistent, pooled, batched client (guards against file-descriptor exhaustion)
- **Intelligent Retry Logic** - Exponential backoff with configurable retry attempts
- **CSV-based Device Management** - Simple credential and device configuration via CSV files
- **Centralized Logging** - Structured logging with rotation and multiple log levels
- **SSH Configuration Management** - Automatic SSH config generation for managed devices
- **Flexible Command-Line Interface** - Multiple operation modes and information display options

### Advanced Features
- Selective deep monitoring per device (configurable via the `monitored` flag)
- Live daemon control: `--status` (with log streaming), `--stop`, and `--reload` (hot config reload)
- Graceful shutdown and automatic reconnection on connection loss
- Thread-safe file and InfluxDB writes for concurrent execution
- Rich console output with progress tracking
- Pre-commit hooks for code quality
- Comprehensive configuration via environment variables

## Installation

### Prerequisites
- Python 3.12+
- `uv` package manager (recommended) or `pip`
- An InfluxDB instance (v2.x, token-based auth) if using the default InfluxDB output

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
NUM_OF_THREADS=10              # Number of concurrent SSH connections (1-100)

# Logging Settings
LOG_FILE_PATH=/var/log/mandiri-mona.log   # Path to application log file
LOG_ROTATE_TIME=w0             # Log rotation time (weekly on Monday)
LOG_BACKUP_COUNT=9             # Number of backup log files to keep
LOG_DATETIME_FORMAT=%Y-%m-%d %H:%M:%S

# File Path Configuration
FW_CREDS_PATH=./configs/fw_creds.csv      # Device credentials CSV
SSHD_CONFIG_PATH=./configs/sshd_config    # SSH configuration file
OUTPUT_DIR_PATH=./outputs/                # Output directory for device logs

# InfluxDB Credentials
INFLUXDB_URL=http://localhost:8086
INFLUXDB_TOKEN=your-influxdb-token
INFLUXDB_ORG=your-org
INFLUXDB_BUCKET=mandiri-mona

# InfluxDB Connection Pool Settings (to prevent file descriptor exhaustion)
INFLUXDB_CONNECTION_POOL_MAXSIZE=10       # Max concurrent HTTP connections to InfluxDB
INFLUXDB_MAX_RETRIES=2                    # Max retry attempts for failed writes
INFLUXDB_TIMEOUT_MS=30000                 # Request timeout (ms)
INFLUXDB_BATCH_SIZE=500                   # Points batched before writing
INFLUXDB_FLUSH_INTERVAL_MS=10000          # Flush interval (ms)
```

### 3. Initialize Required Files
```bash
python main.py --init
```

This creates:
- `./configs/fw_creds.csv` - Device credentials file
- `./configs/sshd_config` - SSH configuration
- The log directory (parent of `LOG_FILE_PATH`)
- `./outputs/` - Output directory for device logs

> [!NOTE]
> On startup the application also checks for a `.env` file. If it is missing or empty, a template is generated and the app exits so you can populate it before restarting.

### 4. Device Configuration
Edit `./configs/fw_creds.csv` with your device information:
```csv
device_type,ip,username,password,hostname,monitored
paloalto_panos,192.168.1.1,admin,password123,some-device-01,True
paloalto_panos,192.168.1.2,admin,password456,some-device-02,False
```

The `monitored` flag enables the additional data-plane resource-monitor command for that device.

## Usage

### Normal Mode (One-time execution)
```bash
python main.py
```

> [!NOTE]
> In normal mode, per-device `.log` files are only written when `--compatibility-mode` is set. InfluxDB writes happen in **daemon mode**.

### Daemon Mode (Background service with persistent connections)

Start the daemon with the default interval (300 seconds):
```bash
python main.py --daemon
```

Start the daemon with a custom interval (e.g., 60 seconds):
```bash
python main.py --daemon --interval 60
```

Check daemon status (and stream its logs):
```bash
python main.py --status
```

Reload configuration (re-read `fw_creds.csv` and `.env`) without restarting:
```bash
python main.py --reload
```

Stop the daemon:
```bash
python main.py --stop
```

### Command-Line Options

```bash
python main.py --help                 # Display help
python main.py --version              # Display version (mandiri-mona 0.2.0)
python main.py --init                 # Initialize required files and directories
python main.py --verbose              # Enable verbose output (raises level to DEBUG)
python main.py --debug                # Enable debug mode (broadens retries and error detail)
python main.py --log-level DEBUG      # Set specific log level
python main.py --compatibility-mode   # Write raw text output to files instead of InfluxDB
python main.py --list devices         # List device information
python main.py --list env             # List environment variables
python main.py --list all             # List all information
python main.py --daemon               # Run as a background service
python main.py --interval 60          # Interval in seconds (daemon mode only, default: 300)
python main.py --status               # Check/stream a running daemon
python main.py --reload               # Hot-reload daemon configuration
python main.py --stop                 # Stop a running daemon
```

> [!CAUTION]
> Never use `--debug` on a production cron job! This will inflate your log file and make your life difficult.

> [!NOTE]
> `--status`, `--stop`, and `--reload` cannot be combined with `--daemon`.

### Monitoring Commands Executed

The exact commands depend on the output format.

**InfluxDB format (default)** — each command's output is parsed into structured metrics:

| Command | Metrics extracted |
|---------|-------------------|
| `show system resources` | Hardware CPU usage (`cpu.hw`), memory usage (`mem.hw`) |
| `show system state \| match 1minavg` | Per-plane CPU load (`cpu.*`) |
| `show session info` | Sessions supported/allocated, packet rate, throughput |
| `show high-availability state \| match "State\|Enabled\|Running Configuration"` | `ha.state`, `sync.state`, `conf.sync` |
| `show running resource-monitor minute last 2` | Per-DP packet buffer / descriptor stats *(monitored devices)* |
| `show system disk-space` | Disk usage as JSON (`disk.usage`) |
| `show system info \| match operational-mode` | Operational mode (`ops.mode`) |

**Compatibility format (`--compatibility-mode`)** — raw output is captured as text:

- `show system state | match 1minavg` - CPU and load averages
- `show system disk-space` - Disk utilization
- `show session info` - Session statistics (filtered: supported/allocated sessions, packet rate, throughput)
- `show high-availability state | match State:` - HA state
- `show running resource-monitor minute last 2` - Data Plane resource utilization *(monitored devices)*

## Output

### Application Logs
- Application logs: `LOG_FILE_PATH` (default `/var/log/mandiri-mona.log`, with automatic rotation)

### InfluxDB (default)
Parsed metrics are written to the configured bucket under measurement **`pa_devices_hw_metrics`**, tagged with:
- `device_ip` - device IP address
- `device_name` - device hostname

Timestamps are recorded in second precision (Asia/Jakarta timezone).

### Compatibility Files (`--compatibility-mode`)
Raw command output is appended per device to `./outputs/<hostname>.log`:
```
========================= show system info | match hostname =========================
hostname: firewall-01

========================= show system state | match 1minavg =========================
1minavg: 0.00
...
```

## Daemon Mode Details

When running in daemon mode:
- The application maintains persistent SSH connections to all configured devices
- Commands are executed at the specified interval (default: 300 seconds)
- Connection health is monitored and automatic reconnection is performed if needed
- Metrics are written to InfluxDB (or to per-device files under `--compatibility-mode`)
- A persistent, pooled, batched InfluxDB client is reused across cycles to avoid file-descriptor leaks
- The daemon can be controlled via `--status`, `--reload`, and `--stop`
- Configuration can be hot-reloaded (`--reload`) without dropping the service
- The PID file is stored at `/tmp/mandiri-mona.pid`

## Development

### Code Quality Tools

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
├── config/                 # Configuration modules
│   ├── argument_parser.py     # CLI argument parsing
│   └── contexts.py            # Context managers (SSH, logging)
├── helper/                 # Helper utilities
│   ├── default_handler.py     # File/directory creation helpers
│   ├── initializer.py         # File/directory initialization
│   ├── logging.py             # Logging configuration
│   ├── misc.py                # Miscellaneous utilities (device loading, etc.)
│   └── print_info.py          # Information display
├── libs/                   # Core libraries
│   ├── __init__.py            # Command sets (COMMANDS_LIST)
│   ├── daemon.py              # Daemonization & PID/lifecycle management
│   ├── data_extractor.py      # Parsers turning raw output into InfluxDB metrics
│   ├── device_comm.py         # SSH communication and command processing
│   ├── file_creation.py       # SSH config and credential file management
│   └── persistent_ssh.py      # Persistent-connection service + InfluxDB writer
├── models/                 # Data models
│   ├── env.py                 # Environment variable models
│   └── main.py                # Device models
├── main.py                 # Application entry point
├── pyproject.toml          # Project configuration
└── README.md               # This file
```

## Requirements
- Python 3.12+
- Key dependencies:
  - `netmiko` - Network device SSH communication
  - `influxdb-client` - Writing metrics to InfluxDB
  - `pydantic` - Data validation
  - `python-dotenv` - Environment variable management
  - `rich` - Terminal formatting
  - `tenacity` - Retry logic

See `pyproject.toml` for the complete dependency list and version requirements.

## License

Copyright 2025 Mandiri MONA Contributors

## Contributing

Contributions are welcome! Please ensure code follows the project's style guidelines:
- Use Black for code formatting (line length: 120)
- Follow Google-style docstrings
- Maintain type hints
- Run pre-commit hooks before committing
