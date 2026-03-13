"""Preferences storage using JSON config file."""

import json
import os
from pathlib import Path

from label_sizes import DEFAULT_SIZE

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "xprinter-label-gui"
CONFIG_FILE = CONFIG_DIR / "settings.json"

DEFAULTS = {
    "label_size": DEFAULT_SIZE,
    "connection_type": "USB",
    "bt_address": "",
    "usb_port": "",
    "wifi_host": "",
    "wifi_port": 9100,
    "density": 8,
    "speed": 3,
    "gap_mm": 2,
    "copies": 1,
}


class Preferences:
    """Simple JSON-backed preferences."""

    def __init__(self):
        self._data = dict(DEFAULTS)
        self._load()

    def _load(self):
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r") as f:
                    saved = json.load(f)
                self._data.update(saved)
            except (json.JSONDecodeError, OSError):
                pass

    def save(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)

    def get(self, key):
        return self._data.get(key, DEFAULTS.get(key))

    def set(self, key, value):
        self._data[key] = value

    def __getitem__(self, key):
        return self.get(key)

    def __setitem__(self, key, value):
        self.set(key, value)
