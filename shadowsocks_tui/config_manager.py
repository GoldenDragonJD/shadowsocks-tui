"""Configuration Manager for Shadowsocks TUI Client.
Handles reading and writing config.json, ensuring secure file permissions,
and populating saved settings so the user only enters IP and Port once.
Supports both local directory and XDG standard (~/.config/shadowsocks-tui/config.json).
"""

import json
import os
from pathlib import Path
from typing import Any, Dict


def get_config_file() -> Path:
    """Determine config file path: prefer local config.json if present, else XDG config directory."""
    local_cfg = Path("config.json")
    if local_cfg.exists():
        return local_cfg.resolve()

    xdg_dir = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "shadowsocks-tui"
    try:
        xdg_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return (xdg_dir / "config.json").resolve()


DEFAULT_CONFIG: Dict[str, Any] = {
    "server": "",
    "server_port": 8388,
    "password": "",
    "method": "aes-256-gcm",
    "mode": "system",  # "system" or "tun"
    "local_port": 1080,
    "tun_interface": "sstun0",
    "tun_address": "10.255.0.2/24",
    "ipv6_leak_protection": True,
}


def load_config() -> Dict[str, Any]:
    """Load configuration from config.json if it exists, otherwise return defaults."""
    config = dict(DEFAULT_CONFIG)
    cfg_file = get_config_file()
    if cfg_file.exists():
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    config.update(data)
        except Exception as e:
            print(f"Warning: Failed to load {cfg_file}: {e}")
    return config


def save_config(config_data: Dict[str, Any]) -> bool:
    """Save configuration to config.json with secure 0o600 permissions."""
    try:
        data_to_save = dict(DEFAULT_CONFIG)
        data_to_save.update(config_data)

        # Do not save temporary sudo password into disk for security
        data_to_save.pop("sudo_password", None)

        cfg_file = get_config_file()
        cfg_file.parent.mkdir(parents=True, exist_ok=True)

        with open(cfg_file, "w", encoding="utf-8") as f:
            json.dump(data_to_save, f, indent=4)

        try:
            os.chmod(cfg_file, 0o600)
        except Exception:
            pass

        return True
    except Exception as e:
        print(f"Error saving config: {e}")
        return False


def has_saved_config() -> bool:
    """Check if a valid saved configuration file exists with a non-empty server."""
    cfg_file = get_config_file()
    if not cfg_file.exists():
        return False
    try:
        cfg = load_config()
        return bool(cfg.get("server") and cfg.get("server_port"))
    except Exception:
        return False
