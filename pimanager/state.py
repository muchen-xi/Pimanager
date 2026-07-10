"""
PiManager 全局状态 + 背景管理器
独立模块，避免页面与 app.py 之间的循环导入
"""
import os
import time
import threading
import base64
import io
from pathlib import Path

from nicegui import ui
from PIL import Image

from pimanager.config import load_config, save_config
from pimanager.theme import ThemeColors
from pimanager.ssh_client import SSHClient


# ──────────────────────────────────────────────
#  BackgroundManager
# ──────────────────────────────────────────────

class BackgroundManager:
    """全局背景图片管理 — Pillow 处理 + CSS 注入。"""
    _path = ''
    _opacity = 0.15
    _fit_mode = 'cover'
    _blended = None

    @classmethod
    def set_background(cls, path: str, opacity: float):
        cls._path = path
        cls._opacity = float(opacity)
        cls._blended = None
        if path and os.path.exists(path):
            try:
                img = Image.open(path).convert('RGBA')
                bg_hex = ThemeColors.get('bg')
                bg_rgb = tuple(int(bg_hex[i:i+2], 16) for i in (1, 3, 5))
                overlay = Image.new('RGBA', img.size, (*bg_rgb, 255))
                blended = Image.blend(overlay.convert('RGB'), img.convert('RGB'), cls._opacity)
                cls._blended = blended.convert('RGBA')
            except Exception as e:
                print(f'背景加载失败: {e}')
                cls._blended = None
        cls._inject_css()

    @classmethod
    def clear(cls):
        cls._path = ''
        cls._blended = None
        cls._inject_css()

    @classmethod
    def set_fit_mode(cls, mode: str):
        if mode in ('cover', 'contain', 'fill', 'tile'):
            cls._fit_mode = mode
            cls._inject_css()

    @classmethod
    def _inject_css(cls):
        if cls._blended is None:
            bg = ThemeColors.get('bg')
            css = f'body {{ background: {bg} !important; }}'
        else:
            buf = io.BytesIO()
            cls._blended.save(buf, format='PNG')
            b64 = base64.b64encode(buf.getvalue()).decode()
            css = (
                f'body {{'
                f'  background-image: url("data:image/png;base64,{b64}") !important;'
                f'  background-size: {cls._fit_mode} !important;'
                f'  background-position: center !important;'
                f'  background-repeat: no-repeat !important;'
                f'}}'
            )
        ui.add_head_html(f'<style id="pm-background">{css}</style>')


# ──────────────────────────────────────────────
#  AppState（全局单例）
# ──────────────────────────────────────────────

class AppState:
    """全局应用状态 — 所有页面通过 get() 共享。"""
    _instance = None

    def __init__(self):
        self.ssh = SSHClient()
        self.config = load_config()
        self._on_disconnect_cbs = []

        # 主题初始化
        appr = self.config.get('appearance', {})
        ThemeColors.set_mode(appr.get('theme', 'dark'))
        ThemeColors.set_color_theme(appr.get('color_theme', 'green'))
        ThemeColors.set_font_scale(appr.get('font_scale', 1.0))
        ThemeColors.apply()

        # 背景
        bg_path = appr.get('background_path', '')
        bg_op = appr.get('background_opacity', 0.15)
        bg_fm = appr.get('background_fit_mode', 'cover')
        BackgroundManager.set_fit_mode(bg_fm)
        if bg_path:
            BackgroundManager.set_background(bg_path, bg_op)

        # 连接参数
        conn = self._first_conn()
        self.conn_host = conn.get('host', 'raspberrypi.local')
        self.conn_port = conn.get('port', 22)
        self.conn_user = conn.get('username', 'pi')
        self.conn_key_path = conn.get('key_path', str(Path.home() / '.ssh' / 'id_ed25519'))
        self.conn_use_key = conn.get('use_key', True)
        self.conn_auto_rediscover = conn.get('auto_rediscover', False)
        self.conn_auto_connect = self.config.get('behavior', {}).get('auto_connect', False)
        self.refresh_interval = self.config.get('behavior', {}).get('refresh_interval', 3)

        # 响应式 UI 状态
        self.connected = False
        self.connecting = False
        self.status_data = {}
        self.sidebar_stats = {}
        self.current_tab = 'status'
        self.connection_time = None

    @classmethod
    def get(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _first_conn(self):
        conns = self.config.get('connections', [])
        return conns[0] if conns else {}

    # ─── 连接管理 ────────────────────────────────────

    def toggle_connection(self):
        if self.connecting:
            return
        if self.connected:
            self.disconnect()
        else:
            self._do_connect()

    def _do_connect(self):
        self.connecting = True
        threading.Thread(target=self._connect_thread, daemon=True).start()

    def _connect_thread(self):
        try:
            kp = self.conn_key_path if self.conn_use_key else None
            ok, msg = self.ssh.connect(
                self.conn_host, self.conn_port, self.conn_user,
                key_path=kp, timeout=10)
            ui.timer(0.1, lambda: self._on_connect_result(ok, msg), once=True)
        except Exception as e:
            ui.timer(0.1, lambda: self._on_connect_result(False, str(e)), once=True)

    def _on_connect_result(self, ok: bool, msg: str):
        self.connecting = False
        if ok:
            self.connected = True
            self.connection_time = time.time()
            self.ssh.set_auto_rediscover(self.conn_auto_rediscover)
            self.ssh.start_keep_alive(30)
            self._save_conn_params()
            ui.notify(f'已连接到 {self.conn_host}', type='positive', position='top')
        else:
            ui.notify(f'连接失败: {msg}', type='negative', position='top')

    def disconnect(self):
        self.ssh.disconnect()
        self.connected = False
        self.connecting = False
        self.connection_time = None
        self.status_data = {}
        self.sidebar_stats = {}
        for cb in self._on_disconnect_cbs:
            cb()

    def _save_conn_params(self):
        conns = self.config.setdefault('connections', [{}])
        c = conns[0]
        c['host'] = self.conn_host
        c['port'] = self.conn_port
        c['username'] = self.conn_user
        c['key_path'] = self.conn_key_path
        c['use_key'] = self.conn_use_key
        c['auto_rediscover'] = self.conn_auto_rediscover
        save_config(self.config)

    def on_disconnect(self, cb):
        self._on_disconnect_cbs.append(cb)

    def save_all_config(self):
        save_config(self.config)

    def update_config(self, key_path: str, value):
        keys = key_path.split('.')
        target = self.config
        for k in keys[:-1]:
            target = target.setdefault(k, {})
        target[keys[-1]] = value

    def get_behavior(self, key: str, default=None):
        return self.config.get('behavior', {}).get(key, default)

    def reboot(self):
        if not self.connected:
            return
        threading.Thread(
            target=lambda: self.ssh.exec_command('sudo shutdown -r now', timeout=5),
            daemon=True
        ).start()
        ui.notify('已发送重启命令', type='warning', position='top')

    def shutdown(self):
        if not self.connected:
            return
        threading.Thread(
            target=lambda: self.ssh.exec_command('sudo shutdown -h now', timeout=5),
            daemon=True
        ).start()
        ui.notify('已发送关机命令', type='negative', position='top')
