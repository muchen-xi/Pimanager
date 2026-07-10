"""
PiManager - 轻量级树莓派管理工具 (v3: NiceGUI)
"""
# Copyright (c) 2026 晨曦 (Chenxi)
__version__ = '3.0.0'

from .state import AppState, BackgroundManager
from .app import create_main_page
from .theme import ThemeColors
from .ssh_client import SSHClient
