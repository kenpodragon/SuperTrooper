"""
Shared database configuration for SuperTroopers utilities.

Reads connection parameters from environment variables first,
then falls back to backend/.env file. Never hardcodes credentials.
"""

import os
from pathlib import Path


def get_db_config() -> dict:
    """Get database connection parameters.

    Priority:
    1. Environment variables (DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD)
    2. backend/.env file (relative to code/ directory)
    3. Defaults for host/port/name/user only (password MUST come from env or .env)
    """
    config = {
        "host": os.environ.get("DB_HOST", ""),
        "port": os.environ.get("DB_PORT", ""),
        "dbname": os.environ.get("DB_NAME", ""),
        "user": os.environ.get("DB_USER", ""),
        "password": os.environ.get("DB_PASSWORD", ""),
    }

    # If any value is missing, try reading from backend/.env
    if not all(config.values()):
        env_file = _find_env_file()
        if env_file:
            env_vars = _parse_env_file(env_file)
            if not config["host"]:
                config["host"] = env_vars.get("DB_HOST", "localhost")
            if not config["port"]:
                config["port"] = env_vars.get("DB_PORT", "5555")
            if not config["dbname"]:
                config["dbname"] = env_vars.get("DB_NAME", "supertroopers")
            if not config["user"]:
                config["user"] = env_vars.get("DB_USER", "supertroopers")
            if not config["password"]:
                config["password"] = env_vars.get("DB_PASSWORD", "")

    # Apply non-sensitive defaults for anything still missing
    if not config["host"]:
        config["host"] = "localhost"
    if not config["port"]:
        config["port"] = "5555"
    if not config["dbname"]:
        config["dbname"] = "supertroopers"
    if not config["user"]:
        config["user"] = "supertroopers"

    if not config["password"]:
        raise ValueError(
            "DB_PASSWORD not found. Set it as an environment variable "
            "or in backend/.env"
        )

    return config


def _find_env_file() -> Path | None:
    """Search for backend/.env relative to this file's location."""
    # code/utils/db_config.py -> code/backend/.env
    here = Path(__file__).resolve().parent
    candidates = [
        here.parent / "backend" / ".env",       # code/utils/ -> code/backend/.env
        here / ".." / "backend" / ".env",
        here / ".." / ".." / "code" / "backend" / ".env",
    ]
    for c in candidates:
        if c.resolve().exists():
            return c.resolve()
    return None


def _parse_env_file(path: Path) -> dict:
    """Parse a .env file into a dict."""
    result = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        result[key.strip()] = val.strip()
    return result
