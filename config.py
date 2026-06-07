"""
PiManager 配置管理
"""
import json
import os
from pathlib import Path

CONFIG_DIR = Path(__file__).parent
CONFIG_FILE = CONFIG_DIR / "pimanager.json"

DEFAULT_CONFIG = {
    "connections": [
        {
            "name": "树莓派 Zero W",
            "host": "muchenxi-20081128.local",
            "port": 22,
            "username": "chenxi",
            "key_path": str(Path.home() / ".ssh" / "id_ed25519"),
            "use_key": True,
        }
    ],
    "appearance": {
        "theme": "dark",  # dark / light / system
        "color_theme": "green",  # green / blue / dark-blue
        "background_path": "",
        "background_opacity": 0.15,
        "font_scale": 1.0,
    },
    "behavior": {
        "auto_connect": False,
        "refresh_interval": 3,  # 状态刷新间隔(秒)
        "confirm_before_delete": True,
        "terminal_history_size": 500,
    }
}


def load_config() -> dict:
    """加载配置"""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
            # 合并默认值
            merged = DEFAULT_CONFIG.copy()
            _deep_merge(merged, config)
            return merged
        except (json.JSONDecodeError, IOError):
            return DEFAULT_CONFIG.copy()
    return DEFAULT_CONFIG.copy()


def save_config(config: dict) -> None:
    """保存配置"""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def get_connection(name: str = None) -> dict:
    """获取连接配置"""
    config = load_config()
    connections = config.get("connections", [])
    if name:
        for conn in connections:
            if conn["name"] == name:
                return conn
    return connections[0] if connections else {}


def _deep_merge(base: dict, override: dict) -> None:
    """深度合并字典"""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
