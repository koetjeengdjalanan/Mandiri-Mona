# Mandiri-Mona

An automation tool for BMRI monitoring and log management.

## Features
- Automated firewall monitoring
- SSH configuration management
- Centralized logging with rotation
- Multi-threaded connection handling

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
\`\`\`bash
python main.py
\`\`\`

## Requirements
- Python 3.12+
- See pyproject.toml for dependencies