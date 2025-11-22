from pathlib import Path
from warnings import warn

from dotenv import load_dotenv

# Load .env file before any models are imported so getenv() can access the values
_env_path = Path(__file__).parent.parent.joinpath(".env").absolute()
if not load_dotenv(dotenv_path=_env_path):
    warn(f"Failed to load .env file or file does not exist: {_env_path}", UserWarning, stacklevel=2)
