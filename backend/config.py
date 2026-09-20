"""Backend configuration. Reads `.env` from the repo root without a library.

The only secret is TYPESAFE_API_KEY. It is read here, handed to the Jev
client, and never logged or returned by any endpoint (CLAUDE.md rule 2).
"""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = REPO_ROOT / ".env"

# JEV_URL is overridable only so tools/fake_jev.py can stand in for the API
# during UI development. Leave it unset for real runs.
JEV_URL = os.environ.get("JEV_URL", "https://api.typesafe.ai/v1/systemone")
JEV_MODEL = "jev-latest"
COST_PER_INPUT_TOKEN = 0.042 / 1_000_000


def load_dotenv(path: Path = ENV_PATH) -> None:
    """Populate os.environ from KEY=VALUE lines.

    A non-empty existing env var wins. An empty one does not: the file is
    re-read on every call so a key added to .env after boot is picked up
    without restarting the backend.
    """
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and value and not os.environ.get(key):
            os.environ[key] = value


def api_key() -> str | None:
    load_dotenv()
    key = os.environ.get("TYPESAFE_API_KEY", "").strip()
    return key or None
