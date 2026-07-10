"""
PiManager 系统状态监控页面（NiceGUI 版）
显示 CPU/RAM/Disk/温度/运行时间等信息，自动刷新
"""
import threading
from datetime import datetime

from nicegui import ui

from pimanager.state import AppState


class StatusPage:
    """系统状态页面。"""

    def __init__(self):
        self.state = AppState.get()
        self._data = {}
        self._last_refresh = None

        # UI 元素引用（build 时填充）
        self._hostname_lbl = None
        self._os_lbl = None
        self._kernel_lbl = None
        self._cpu_bar = None
        self._cpu_pct = None
        self._temp_val = None
        self._mem_bar = None
        self._mem_text = None
        self._disk_bar = None
        self._disk_text = None
        self._uptime_lbl = None
        self._load_lbl = None
        self._refresh_btn = None
        self._last_time_lbl = None

    def build(self):
        """构建页面 UI（由 tab_panel 调用）。"""
        with ui.column().classes('w-full q-pa-md'):
            ui.label('系统状态').classes('text-h5 q-mb-md')

            # ── 信息卡片网格 ──
            with ui.row().classes('w-full'):
                self._build_info_card()
                self._build_cpu_card()

            with ui.row().classes('w-full'):
                self._build_mem_card()
                self._build_disk_card()

            with ui.row().classes('w-full'):
                self._build_temp_card()
                self._build_uptime_card()

            # ── 刷新控制 ──
            with ui.row().classes('items-center q-mt-sm'):
                self._refresh_btn = ui.button('刷新', icon='refresh',
                                              on_click=self.refresh)
                self._last_time_lbl = ui.label('').classes('text-caption text-grey')

            # ── 自动刷新 ──
            ui.timer(self.state.refresh_interval, self._auto_refresh)

            # 如果已连接，立即加载
            if self.state.connected:
                self.refresh()

    def _build_info_card(self):
        """系统信息卡片。"""
        with ui.card().classes('pm-stat-card col-6'):
            ui.label('系统信息').classes('title')
            self._hostname_lbl = ui.label('主机名: --').classes('text-caption')
            self._os_lbl      = ui.label('系统: --').classes('text-caption')
            self._kernel_lbl  = ui.label('内核: --').classes('text-caption')

    def _build_cpu_card(self):
        """CPU 信息卡片。"""
        with ui.card().classes('pm-stat-card col-6'):
            ui.label('CPU 使用率').classes('title')
            self._cpu_bar = ui.linear_progress(value=0).classes('w-full q-mt-sm')
            self._cpu_pct = ui.label('0%').classes('text-caption')

    def _build_mem_card(self):
        """内存信息卡片。"""
        with ui.card().classes('pm-stat-card col-6'):
            ui.label('内存使用').classes('title')
            self._mem_bar  = ui.linear_progress(value=0).classes('w-full q-mt-sm')
            self._mem_text = ui.label('0 / 0 MB').classes('text-caption')

    def _build_disk_card(self):
        """磁盘信息卡片。"""
        with ui.card().classes('pm-stat-card col-6'):
            ui.label('磁盘使用').classes('title')
            self._disk_bar  = ui.linear_progress(value=0).classes('w-full q-mt-sm')
            self._disk_text = ui.label('0 / 0 MB').classes('text-caption')

    def _build_temp_card(self):
        """温度卡片。"""
        with ui.card().classes('pm-stat-card col-4'):
            ui.label('CPU 温度').classes('title')
            self._temp_val = ui.label('--°C').classes('value')

    def _build_uptime_card(self):
        """运行时间卡片。"""
        with ui.card().classes('pm-stat-card col-8'):
            ui.label('运行时间 / 负载').classes('title')
            self._uptime_lbl = ui.label('--').classes('text-caption')
            self._load_lbl   = ui.label('负载: --').classes('text-caption')

    # ─── 数据加载 ──────────────────────────────────

    def refresh(self):
        """手动刷新状态。"""
        if not self.state.connected:
            ui.notify('未连接', type='warning', position='top')
            return
        self._refresh_btn.disable()
        self._refresh_btn.set_text('刷新中...')

        def _fetch():
            try:
                data = self.state.ssh.get_system_status()
                ui.timer(0, lambda: self._update_ui(data), once=True)
            except Exception as e:
                ui.timer(0, lambda: ui.notify(f'获取状态失败: {e}', type='negative'), once=True)
            finally:
                ui.timer(0, lambda: self._refresh_btn.enable(), once=True)
                ui.timer(0, lambda: self._refresh_btn.set_text('刷新'), once=True)

        threading.Thread(target=_fetch, daemon=True).start()

    def _auto_refresh(self):
        """自动刷新（由 timer 调用）。"""
        if self.state.connected:
            self._auto_fetch()

    def _auto_fetch(self):
        """后台异步获取状态。"""
        def _fetch():
            try:
                data = self.state.ssh.get_system_status()
                ui.timer(0, lambda: self._update_ui(data), once=True)
            except Exception:
                pass

        threading.Thread(target=_fetch, daemon=True).start()

    def _update_ui(self, data: dict):
        """更新 UI 显示。"""
        self._data = data
        self._last_refresh = datetime.now()

        # 系统信息
        self._hostname_lbl.set_text(f"主机名: {data.get('hostname', '--')}")
        self._os_lbl.set_text(f"系统: {data.get('os_version', '--')}")
        self._kernel_lbl.set_text(f"内核: {data.get('kernel', '--')}")

        # CPU
        cpu = data.get('cpu_percent', 0)
        self._cpu_bar.set_value(cpu / 100)
        self._cpu_pct.set_text(f'{cpu:.1f}%')
        self._cpu_bar._props['color'] = self._cpu_color(cpu)
        self._cpu_bar.update()

        # 温度
        temp = data.get('cpu_temp', 0)
        self._temp_val.set_text(f'{temp:.1f}°C')
        t_color = self._temp_color(temp)
        self._temp_val.classes(f'text-{t_color}')

        # 内存
        mem_pct = data.get('memory_percent', 0)
        self._mem_bar.set_value(mem_pct / 100)
        mem_u = data.get('memory_used', 0)
        mem_t = data.get('memory_total', 0)
        self._mem_text.set_text(f'{mem_u} / {mem_t} MB')
        self._mem_bar._props['color'] = self._cpu_color(mem_pct)
        self._mem_bar.update()

        # 磁盘
        disk_pct = data.get('disk_percent', 0)
        self._disk_bar.set_value(disk_pct / 100)
        disk_u = data.get('disk_used', 0)
        disk_t = data.get('disk_total', 0)
        if disk_t >= 1024:
            self._disk_text.set_text(f'{disk_u/1024:.1f} / {disk_t/1024:.1f} GB')
        else:
            self._disk_text.set_text(f'{disk_u} / {disk_t} MB')
        self._disk_bar._props['color'] = self._cpu_color(disk_pct)
        self._disk_bar.update()

        # 运行时间
        self._uptime_lbl.set_text(f"运行: {data.get('uptime', '--')}")
        self._load_lbl.set_text(f"负载: {data.get('load_avg', '--')}")

        # 计时
        self._last_time_lbl.set_text(
            f"最后更新: {self._last_refresh.strftime('%H:%M:%S')}")

    # ─── 颜色辅助 ──────────────────────────────────

    @staticmethod
    def _cpu_color(pct: float) -> str:
        if pct < 50:
            return 'green'
        elif pct < 80:
            return 'orange'
        return 'red'

    @staticmethod
    def _temp_color(temp: float) -> str:
        if temp < 50:
            return 'green-8'
        elif temp < 70:
            return 'orange-8'
        return 'red-8'
