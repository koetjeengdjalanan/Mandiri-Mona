# Mandiri-Mona

An automation tool for BMRI monitoring and log management.

## Features
- Automated firewall monitoring
- SSH configuration management
- Centralized logging with rotation
- Multi-threaded connection handling
- **Background daemon mode with persistent SSH connections**
- **Interval-based monitoring**
- **Status monitoring and daemon control**

## Installation
\`\`\`bash
pip install uv
uv sync
\`\`\`

## Configuration
Copy `.env.example` to `.env` and configure:
\`\`\`bash
cp .env.example .env
\`\`\`

## Usage

### Normal Mode (One-time execution)
\`\`\`bash
python main.py
\`\`\`

### Daemon Mode (Background service with persistent connections)

Start the daemon with default interval (300 seconds):
\`\`\`bash
python main.py --daemon
\`\`\`

Start the daemon with custom interval (e.g., 60 seconds):
\`\`\`bash
python main.py --daemon --interval 60
\`\`\`

Check daemon status:
\`\`\`bash
python main.py --status
\`\`\`

Stop the daemon:
\`\`\`bash
python main.py --stop
\`\`\`

### Other Options

Initialize required files and directories:
\`\`\`bash
python main.py --init
\`\`\`

List devices or environment information:
\`\`\`bash
python main.py --list devices
python main.py --list env
python main.py --list all
\`\`\`

Enable debug mode:
\`\`\`bash
python main.py --debug
\`\`\`

## Daemon Mode Details

When running in daemon mode:
- The application maintains persistent SSH connections to all configured devices
- Commands are executed at the specified interval (default: 300 seconds)
- Connection health is monitored and automatic reconnection is performed if needed
- Output is appended to device-specific log files with timestamps
- The daemon runs in the background and can be controlled via \`--status\` and \`--stop\` commands
- PID file is stored at \`/tmp/mandiri-mona.pid\`

## Requirements
- Python 3.12+
- See pyproject.toml for dependencies