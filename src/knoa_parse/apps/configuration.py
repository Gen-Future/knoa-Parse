"""Private project server settings with optional environment overrides."""
import json
import os
from pathlib import Path

from knoa_parse.core.settings import Settings


def server_configuration() -> Settings:
    path = Path(os.getenv("KNOA_PARSE_SERVER_CONFIG", ".local/server.json"))
    try:
        if not path.exists() and "KNOA_PARSE_SERVER_CONFIG" in os.environ:
            raise ValueError("Missing server config")
        config = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        if not isinstance(config, dict) or set(config) - {"api_token", "data_dir"}:
            raise ValueError("Invalid server config")
        # Ignore the old api_token field so existing demos upgrade without a login requirement.
        data_dir = os.getenv("KNOA_PARSE_DATA_DIR", config.get("data_dir", ".local/knoa-parse"))
        if not isinstance(data_dir, str) or not data_dir.strip():
            raise ValueError("Invalid data directory")
        return Settings(Path(data_dir))
    except (OSError, ValueError, TypeError):
        raise RuntimeError("Invalid server configuration; check .local/server.json or KNOA_PARSE_SERVER_CONFIG") from None
