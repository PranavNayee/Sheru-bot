"""Loads settings from the .env file next to this script (no extra packages needed)."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env_file(ROOT / ".env")


def get(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def get_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def get_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


# Folders
OUTPUT_DIR = ROOT / "output"
PROFILE_DIR = ROOT / "browser_profile"
STATE_FILE = ROOT / "state.json"
EPISODES_FILE = ROOT / "episodes.json"
SELECTORS_FILE = ROOT / "selectors.json"

# Flow
FLOW_URL = get("FLOW_URL", "https://flow.google.com/")
FLOW_TIMEOUT_SECONDS = get_int("FLOW_TIMEOUT_SECONDS", 600)

# Instagram
IG_USER_ID = get("IG_USER_ID")
IG_ACCESS_TOKEN = get("IG_ACCESS_TOKEN")
IG_GRAPH_HOST = get("IG_GRAPH_HOST", "https://graph.facebook.com")
IG_API_VERSION = get("IG_API_VERSION", "v21.0")

# Behaviour
DRY_RUN = get_bool("DRY_RUN", True)
