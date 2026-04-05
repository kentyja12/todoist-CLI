from __future__ import annotations

import os
from pathlib import Path


def config_dir() -> Path:
    """Return the platform-appropriate config directory for Todash."""
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home()))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "todash"


def config_file() -> Path:
    return config_dir() / ".env"


def is_configured() -> bool:
    """Return True if a valid API token is saved in the config file."""
    cf = config_file()
    if not cf.exists():
        return False
    for line in cf.read_text().splitlines():
        if line.startswith("TODOIST_TOKEN="):
            token = line.split("=", 1)[1].strip()
            return bool(token)
    return False
