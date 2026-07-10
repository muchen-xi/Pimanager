"""
PiManager 设置页面（NiceGUI 版）
- 外观：亮暗主题 / 颜色主题 / 字体缩放
- 背景：图片 / 透明度 / 适配模式
- 行为：自动连接 / 刷新间隔 / 确认删除 / IP漂移检测
"""
import os
import threading

from nicegui import ui, app as ng_app

from pimanager.state import AppState, BackgroundManager
from pimanager.theme import ThemeColors


class SettingsPage:
    """设置页面。"""

    def __init__(self):
        self.state = AppState.get()

    def build(self):
        with ui.column().classes('w-full q-pa-md'):
            ui.label('应用设置').classes('text-h5 q-mb-md')
            self._build_appearance_card()
            self._build_background_card()
            self._build_behavior_card()
            self._build_about_card()

    # ─── 外观设置 ──────────────────────────────────

    def _build_appearance_card(self):
        with ui.card().classes('pm-stat-card w-full q-mb-md'):
            ui.label('外观').classes('title')

            with ui.row().classes('items-center q-mt-sm'):
                ui.label('主题模式:').classes('text-caption')
                theme_select = ui.select(
                    ['深色', '浅色'],
                    value='深色' if ThemeColors.get_mode() == 'Dark' else '浅色',
                    on_change=lambda e: self._set_theme(e.value)
                )

            with ui.row().classes('items-center'):
                ui.label('颜色主题:').classes('text-caption')
                color_select = ui.select(
                    ['绿色', '蓝色', '深蓝'],
                    value={'green': '绿色', 'blue': '蓝色', 'dark-blue': '深蓝'}
                          .get(ThemeColors.get_color_theme(), '绿色'),
                    on_change=lambda e: self._set_color(e.value)
                )

            with ui.row().classes('items-center'):
                ui.label('字体缩放:').classes('text-caption')
                scale_slider = ui.slider(
                    min=0.8, max=1.5, step=0.1,
                    value=ThemeColors.get_font_scale()
                ).on('change', lambda e: self._set_scale(e.args))

    def _set_theme(self, label: str):
        mode = 'dark' if label == '深色' else 'light'
        ThemeColors.set_mode(mode)
        ThemeColors.apply()
        self.state.update_config('appearance.theme', mode)
        self.state.save_all_config()
        ui.notify(f'已切换到{mode}模式', type='positive', position='top')

    def _set_color(self, label: str):
        name = {'绿色': 'green', '蓝色': 'blue', '深蓝': 'dark-blue'}.get(label, 'green')
        ThemeColors.set_color_theme(name)
        ThemeColors.apply()
        self.state.update_config('appearance.color_theme', name)
        self.state.save_all_config()

    def _set_scale(self, value: float):
        scale = float(value)
        ThemeColors.set_font_scale(scale)
        ThemeColors.apply()
        self.state.update_config('appearance.font_scale', scale)
        self.state.save_all_config()

    # ─── 背景设置 ──────────────────────────────────

    def _build_background_card(self):
        with ui.card().classes('pm-stat-card w-full q-mb-md'):
            ui.label('背景图片').classes('title')

            bg_path = self.state.config.get('appearance', {}).get('background_path', '')
            path_lbl = ui.label(f'当前: {bg_path or "无"}').classes(
                'text-caption text-grey q-mt-sm')

            with ui.row().classes('items-center q-gutter-sm'):
                def _choose_bg():
                    import tkinter as tk
                    from tkinter import filedialog
                    root = tk.Tk()
                    root.withdraw()
                    path = filedialog.askopenfilename(
                        title='选择背景图片',
                        filetypes=[('图片', '*.jpg *.png *.jpeg'), ('所有文件', '*.*')])
                    root.destroy()
                    if path:
                        self._apply_bg(path, path_lbl)

                ui.button('选择图片', on_click=_choose_bg)

                def _clear_bg():
                    BackgroundManager.clear()
                    self.state.update_config('appearance.background_path', '')
                    self.state.update_config('appearance.background_opacity', 0.15)
                    self.state.save_all_config()
                    path_lbl.set_text('当前: 无')
                    ui.notify('背景已清除', position='top')

                ui.button('清除背景', on_click=_clear_bg).props('flat')

            with ui.row().classes('items-center'):
                ui.label('透明度:').classes('text-caption')
                cur_op = self.state.config.get('appearance', {}).get('background_opacity', 0.15)
                op_slider = ui.slider(
                    min=0.05, max=0.5, step=0.05, value=cur_op
                ).on('change', lambda e: self._set_opacity(e.args, path_lbl))

            with ui.row().classes('items-center'):
                ui.label('适配模式:').classes('text-caption')
                cur_fm = self.state.config.get('appearance', {}).get('background_fit_mode', 'cover')
                fm_labels = {'cover': '裁剪', 'contain': '包含', 'fill': '拉伸', 'tile': '平铺'}
                fm_select = ui.select(
                    list(fm_labels.values()),
                    value=fm_labels.get(cur_fm, '裁剪'),
                    on_change=lambda e: self._set_fit_mode(e.value)
                )

    def _apply_bg(self, path: str, path_lbl):
        opacity = self.state.config.get('appearance', {}).get('background_opacity', 0.15)
        BackgroundManager.set_background(path, opacity)
        self.state.update_config('appearance.background_path', path)
        self.state.save_all_config()
        path_lbl.set_text(f'当前: {os.path.basename(path)}')
        ui.notify('背景已更新', type='positive', position='top')

    def _set_opacity(self, value: float, path_lbl):
        opacity = float(value)
        self.state.update_config('appearance.background_opacity', opacity)
        self.state.save_all_config()
        bg_path = self.state.config.get('appearance', {}).get('background_path', '')
        if bg_path:
            BackgroundManager.set_background(bg_path, opacity)

    def _set_fit_mode(self, label: str):
        mode = {'裁剪': 'cover', '包含': 'contain', '拉伸': 'fill', '平铺': 'tile'}.get(label, 'cover')
        BackgroundManager.set_fit_mode(mode)
        self.state.update_config('appearance.background_fit_mode', mode)
        self.state.save_all_config()

    # ─── 行为设置 ──────────────────────────────────

    def _build_behavior_card(self):
        behavior = self.state.config.get('behavior', {})

        with ui.card().classes('pm-stat-card w-full q-mb-md'):
            ui.label('行为').classes('title')

            auto_conn = ui.switch(
                '启动时自动连接',
                value=behavior.get('auto_connect', False),
                on_change=lambda e: self._set_behavior('auto_connect', e.value)
            ).classes('q-mt-sm')

            with ui.row().classes('items-center'):
                ui.label('刷新间隔 (秒):').classes('text-caption')
                cur_interval = behavior.get('refresh_interval', 3)
                ui.slider(
                    min=1, max=30, step=1, value=cur_interval
                ).on('change', lambda e: self._set_refresh_interval(e.args)).classes('w-40')

            confirm_del = ui.switch(
                '删除前确认',
                value=behavior.get('confirm_before_delete', True),
                on_change=lambda e: self._set_behavior('confirm_before_delete', e.value)
            )

            ip_drift = ui.switch(
                'IP漂移检测',
                value=behavior.get('ip_drift_detection', True),
                on_change=lambda e: self._set_behavior('ip_drift_detection', e.value)
            )

    def _set_behavior(self, key: str, value):
        self.state.update_config(f'behavior.{key}', value)
        self.state.save_all_config()

    def _set_refresh_interval(self, value):
        self.state.refresh_interval = int(value)
        self._set_behavior('refresh_interval', int(value))

    # ─── 关于 ──────────────────────────────────────

    def _build_about_card(self):
        from pimanager import __version__

        with ui.card().classes('pm-stat-card w-full q-mb-md'):
            ui.label('关于').classes('title')
            ui.label(f'PiManager v{__version__}').classes('text-caption q-mt-sm')
            ui.label('轻量级树莓派 Zero W 桌面管理器').classes('text-caption')
            ui.label('技术栈: NiceGUI + tkinter + Pillow + Paramiko').classes('text-caption')

            def _save_all():
                self.state.save_all_config()
                ui.notify('所有设置已保存', type='positive', position='top')

            ui.button('保存所有设置', icon='save', on_click=_save_all).classes('q-mt-sm')
