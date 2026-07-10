"""
PiManager — NiceGUI 主页面布局
包含：主布局、侧边栏、连接对话框、导航
"""
import os
import time
from datetime import datetime

from nicegui import ui, app as ng_app

from pimanager.state import AppState, BackgroundManager


# ─── 主页面布局工厂 ──────────────────────────────────
def create_main_page():
    """构建 NiceGUI 主页面（/）。"""
    state = AppState.get()

    # ─── 页面实例（在函数内延迟导入避免循环） ───
    from pimanager.pages.status import StatusPage
    from pimanager.pages.files import FilesPage
    from pimanager.pages.terminal import TerminalPage
    from pimanager.pages.settings import SettingsPage

    pages = {
        'status': StatusPage(),
        'files':  FilesPage(),
        'terminal': TerminalPage(),
        'settings': SettingsPage(),
    }

    # ─── 侧边栏 ──────────────────────────────────
    with ui.left_drawer(value=True, bordered=True).classes('pm-sidebar'):
        _build_sidebar(state)

    # ─── Tab 面板 ────────────────────────────────
    tabs = ui.tabs().classes('w-full').props('dense inline-label')
    with tabs:
        tab_status = ui.tab('状态', icon='dashboard')
        tab_files  = ui.tab('文件', icon='folder')
        tab_term   = ui.tab('终端', icon='terminal')
        tab_sett   = ui.tab('设置', icon='tune')

    tab_panels = ui.tab_panels(tabs, value=tab_status).classes('w-full grow')
    with tab_panels:
        with ui.tab_panel(tab_status):
            pages['status'].build()
        with ui.tab_panel(tab_files):
            pages['files'].build()
        with ui.tab_panel(tab_term):
            pages['terminal'].build()
        with ui.tab_panel(tab_sett):
            pages['settings'].build()

    # ─── 状态栏 ──────────────────────────────────
    with ui.row().classes('w-full items-center q-pa-xs bg-grey-9 text-caption'):
        status_lbl = ui.label('就绪')
        status_lbl.bind_visibility_from(state, 'connected', lambda v: not v)
        conn_lbl = ui.label('已连接')
        conn_lbl.bind_visibility_from(state, 'connected')
        dur_lbl = ui.label()
        ui.space()
        clock_lbl = ui.label()

        def _update_status_bar():
            now = datetime.now()
            clock_lbl.set_text(now.strftime('%Y-%m-%d %H:%M'))
            if state.connected and state.connection_time:
                secs = int(time.time() - state.connection_time)
                h, r = divmod(secs, 3600)
                m, s = divmod(r, 60)
                dur_lbl.set_text(f'已连接 {h}时{m}分' if h else f'已连接 {m}分{s}秒')
            else:
                dur_lbl.set_text('')

        _update_status_bar()
        ui.timer(30, _update_status_bar)

    # ─── 自动连接 ────────────────────────────────
    if state.conn_auto_connect:
        ui.timer(0.5, lambda: state.toggle_connection(), once=True)

    # ─── 侧边栏统计定时刷新 ──────────────────────
    ui.timer(state.refresh_interval, _refresh_sidebar_stats)


def _build_sidebar(state: AppState):
    """构建侧边栏内容。"""
    # ── Logo ──
    with ui.row().classes('items-center q-pa-md'):
        ui.icon('raspberry-pi', size='32px').classes('text-green')
        ui.label('PiManager').classes('text-h6 q-ml-sm')

    # ── 连接状态卡片 ──
    with ui.card().classes('pm-stat-card w-full q-mb-sm').props('flat'):
        conn_text = ui.label('未连接').classes('text-caption')
        conn_sub = ui.label('').classes('text-caption text-grey')

    # ── 连接按钮 ──
    with ui.row().classes('w-full q-px-sm'):
        connect_btn = ui.button('连接', icon='power',
                                on_click=lambda: state.toggle_connection())
        ui.button(icon='settings',
                  on_click=lambda: _show_conn_dialog(state)).props('flat')

    # ── 导航 ──
    ui.separator().classes('q-my-sm')
    nav_items = [
        ('dashboard', '系统状态', 'status'),
        ('folder',     '文件管理', 'files'),
        ('terminal',   '命令终端', 'terminal'),
        ('tune',       '应用设置', 'settings'),
    ]
    for icon, label, key in nav_items:
        ui.button(label, icon=icon,
                  on_click=lambda k=key: _switch_tab(k)
                  ).props('flat').classes('pm-sidebar-btn')

    # ── 实时状态卡片 ──
    ui.separator().classes('q-my-sm')
    with ui.card().classes('pm-stat-card w-full').props('flat') as stats_card:
        ui.label('实时状态').classes('title')
        cpu_row = ui.row().classes('w-full items-center')
        with cpu_row:
            ui.label('CPU:').classes('text-caption')
            cpu_val = ui.label('--').classes('text-caption')
        ram_row = ui.row().classes('w-full items-center')
        with ram_row:
            ui.label('RAM:').classes('text-caption')
            ram_val = ui.label('--').classes('text-caption')
        ip_val = ui.label('IP: --').classes('text-caption')
        temp_val = ui.label('温度: --').classes('text-caption')
    stats_card.set_visibility(False)

    def _update_sidebar_ui():
        if state.connected:
            stats_card.set_visibility(True)
            s = state.sidebar_stats
            cpu_val.set_text(f"{s.get('cpu', 0):.1f}%")
            mem_u = s.get('mem_used', 0)
            mem_t = s.get('mem_total', 0)
            ram_val.set_text(f"{mem_u}/{mem_t} MB")
            ip_val.set_text(f"IP: {s.get('ip', '--')}")
            temp_val.set_text(f"温度: {s.get('temp', 0):.1f}°C")
            conn_text.set_text('已连接')
            conn_text.classes(replace='text-green')
            conn_sub.set_text(state.conn_host)
            connect_btn.set_text('断开')
            connect_btn.enable()
        else:
            stats_card.set_visibility(False)
            conn_text.set_text('未连接')
            conn_text.classes(replace='text-grey')
            conn_sub.set_text('')
            connect_btn.set_text('连接')
            connect_btn.enable()

        if state.connecting:
            connect_btn.set_text('连接中...')
            connect_btn.disable()

    ui.timer(0.3, _update_sidebar_ui, once=True)
    # 持续刷新用独立的 timer（在 create_main_page 末尾添加）

    # ── 电源 ──
    ui.separator().classes('q-my-sm')
    with ui.row().classes('w-full q-px-sm'):
        ui.button('重启', icon='restart_alt', color='warning',
                  on_click=lambda: _confirm_dialog('重启', state.reboot))
        ui.button('关机', icon='power_settings_new', color='negative',
                  on_click=lambda: _confirm_dialog('关机', state.shutdown))

    # ── 版本 ──
    from pimanager import __version__
    ui.label(f'v{__version__}').classes('text-caption text-grey absolute-bottom q-pa-md')


def _refresh_sidebar_stats():
    """后台刷新侧边栏统计（由 timer 驱动）。"""
    import threading
    state = AppState.get()
    if not state.connected:
        return

    def _fetch():
        try:
            data = state.ssh.get_sidebar_stats()
            state.sidebar_stats = data
        except Exception:
            pass

    threading.Thread(target=_fetch, daemon=True).start()


def _switch_tab(name: str):
    """切换到指定标签。"""
    # 通过 ng_app.tabs 访问 tabs 组件
    for tab in reversed(ng_app.tabs):
        if tab.name == name:
            tab.value = True
            break


def _show_conn_dialog(state: AppState):
    """连接设置对话框。"""
    with ui.dialog() as dialog, ui.card().classes('w-96'):
        ui.label('连接设置').classes('text-h6')
        host = ui.input('主机', value=state.conn_host)
        port = ui.number('端口', value=state.conn_port, min=1, max=65535)
        user = ui.input('用户名', value=state.conn_user)
        kp = ui.input('密钥路径', value=state.conn_key_path)
        use_k = ui.switch('使用密钥', value=state.conn_use_key)
        drift = ui.switch('IP漂移检测', value=state.conn_auto_rediscover)

        def _browse_key():
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            path = filedialog.askopenfilename(
                title='选择 SSH 密钥',
                initialdir=os.path.join(os.path.expanduser('~'), '.ssh'),
                filetypes=[('密钥文件', 'id_*'), ('PEM', '*.pem'), ('所有文件', '*.*')])
            root.destroy()
            if path:
                kp.value = path

        ui.button('浏览...', on_click=_browse_key).props('flat')

        def _save():
            state.conn_host = host.value
            state.conn_port = int(port.value)
            state.conn_user = user.value
            state.conn_key_path = kp.value
            state.conn_use_key = use_k.value
            state.conn_auto_rediscover = drift.value
            state._save_conn_params()
            state.save_all_config()
            ui.notify('连接设置已保存', type='positive', position='top')
            dialog.close()

        with ui.row():
            ui.button('保存', on_click=_save, color='primary')
            ui.button('取消', on_click=dialog.close)

    dialog.open()


def _confirm_dialog(action: str, callback):
    """确认对话框。"""
    with ui.dialog() as dialog, ui.card():
        ui.label(f'确认{action}树莓派？')
        with ui.row():
            c = 'warning' if action == '重启' else 'negative'
            ui.button(f'确认{action}', color=c,
                      on_click=lambda: (callback(), dialog.close()))
            ui.button('取消', on_click=dialog.close)
    dialog.open()
