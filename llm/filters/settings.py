"""Read a setting from api/config.py, with a fallback if there is no config."""

import sys
from pathlib import Path

API = Path(__file__).resolve().parents[2] / 'api'


def config_value(name, fallback):
    try:
        if str(API) not in sys.path:
            sys.path.insert(0, str(API))
        import config
        return getattr(config, name, fallback)
    except Exception:
        return fallback
