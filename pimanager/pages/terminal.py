"""
PiManager 命令终端页面（NiceGUI 版）
- 多标签
- 阻塞/流式执行
- 快速命令
- 历史记录
"""
import threading
from collections import deque

from nicegui import ui

from pimanager.state import AppState


# ─── 快速命令 ──────────────────────────────────────
QUICK_COMMANDS = [
    ('系统状态', 'htop'),
    ('列表', 'ls -la'),
    ('磁盘', 'df -h'),
    ('内存', 'free -h'),
    ('温度', 'vcgencmd measure_temp'),
    ('运行时间', 'uptime'),
    ('网络', 'ip addr'),
    ('进程', 'ps aux --sort=-%mem | head -20'),
    ('Python', 'python3 --version'),
    ('用户', 'who'),
]

# ─── 终端会话 ──────────────────────────────────────
class TerminalSession:
    """单个终端标签状态。"""

    def __init__(self, name: str = '终端'):
        self.name = name
        self.history = deque(maxlen=500)
        self.history_pos = -1
        self._lines = []          # [(text, color_or_None)]
        self._streaming = False

    def add_line(self, text: str, color: str = None):
        self._lines.append((text, color))

    def get_lines(self):
        return self._lines

    def clear(self):
        self._lines.clear()


class TerminalPage:
    """命令终端页面。"""

    def __init__(self):
        self.state = AppState.get()
        self._sessions = [TerminalSession()]
        self._active_idx = 0
        self._stream_mode = False
        self._current_handle = None

        # UI
        self._output_logs = []
        self._cmd_input = None
        self._stream_btn = None

    def build(self):
        with ui.column().classes('w-full q-pa-md'):
            ui.label('命令终端').classes('text-h5')

            # ── 标签栏 ──
            with ui.row().classes('w-full items-center'):
                self._tab_row = ui.row().classes('items-center')
                ui.separator().props('vertical')
                ui.button('+ 新终端', icon='add',
                          on_click=self._add_tab).props('flat')

            # ── 快速命令 ──
            with ui.row().classes('w-full q-mt-xs').props('wrap'):
                for label, cmd in QUICK_COMMANDS:
                    ui.button(label,
                              on_click=lambda c=cmd: self._run_quick(c)).props('size=xs')

            # ── 输出区域 ──
            log = ui.log().classes('w-full pm-terminal').style('height: 400px')
            self._output_logs.append(log)

            # ── 输入栏 ──
            with ui.row().classes('w-full items-center q-mt-xs'):
                ui.label('$').classes('text-caption text-green pm-text-mono')
                self._cmd_input = ui.input(
                    placeholder='输入命令...',
                ).classes('flex-1').on('keydown.enter', self._execute_command)

                self._stream_btn = ui.button(
                    '流式', icon='stream',
                    on_click=self._toggle_stream
                ).props('flat')
                ui.button('清屏', icon='cleaning_services',
                          on_click=self._clear_output).props('flat')

            # ── 连接监听 ──
            ui.timer(1, self._sync_connection)

        self._rebuild_tabs()
        self._sync_connection()

    # ─── 标签管理 ──────────────────────────────────

    def _rebuild_tabs(self):
        self._tab_row.clear()
        for idx, session in enumerate(self._sessions):
            with self._tab_row:
                is_active = idx == self._active_idx
                btn = ui.button(
                    session.name,
                    on_click=lambda i=idx: self._switch_tab(i),
                    color='primary' if is_active else 'grey',
                ).props('flat')
                if len(self._sessions) > 1:
                    ui.button('x', on_click=lambda i=idx: self._close_tab(i)).props('flat size=xs')

    def _add_tab(self):
        n = len(self._sessions)
        self._sessions.append(TerminalSession(f'终端 {n}'))
        log = ui.log().classes('w-full pm-terminal').style('height: 400px')
        log.set_visibility(False)
        self._output_logs.append(log)
        self._active_idx = n
        self._rebuild_tabs()
        self._switch_visible()

    def _close_tab(self, idx: int):
        if len(self._sessions) <= 1:
            return
        del self._sessions[idx]
        self._output_logs[idx].delete()
        del self._output_logs[idx]
        if self._active_idx >= len(self._sessions):
            self._active_idx = len(self._sessions) - 1
        self._rebuild_tabs()
        self._switch_visible()

    def _switch_tab(self, idx: int):
        self._active_idx = idx
        self._rebuild_tabs()
        self._switch_visible()

    def _switch_visible(self):
        for i, log in enumerate(self._output_logs):
            log.set_visibility(i == self._active_idx)

    # ─── 连接状态 ──────────────────────────────────

    def _sync_connection(self):
        if self.state.connected:
            self._cmd_input.enable()
        else:
            self._cmd_input.disable()

    # ─── 命令执行 ──────────────────────────────────

    def _execute_command(self):
        cmd = self._cmd_input.value
        if not cmd:
            return
        self._cmd_input.value = ''

        session = self._sessions[self._active_idx]
        session.history.append(cmd)
        session.history_pos = len(session.history)

        session.add_line(f'$ {cmd}', '#4CAF50')
        self._push_output(f'$ {cmd}')

        if self._stream_mode:
            self._exec_streaming(cmd)
        else:
            self._exec_blocking(cmd)

    def _exec_blocking(self, cmd: str):
        if not self.state.connected:
            self._push_output('未连接')
            return

        def _do():
            try:
                code, out, err = self.state.ssh.exec_command(cmd, timeout=30)
                sess = self._sessions[self._active_idx]
                if out:
                    for line in out.strip().split('\n'):
                        sess.add_line(line)
                if err:
                    for line in err.strip().split('\n'):
                        sess.add_line(line, '#FF6B6B')
                sess.add_line(f'[退出码: {code}]', '#8B949E')
                ui.timer(0, self._refresh_output, once=True)
            except Exception as e:
                ui.timer(0, lambda: self._push_output(f'错误: {e}'), once=True)

        threading.Thread(target=_do, daemon=True).start()

    def _exec_streaming(self, cmd: str):
        if not self.state.connected:
            self._push_output('未连接')
            return

        sess = self._sessions[self._active_idx]

        def on_stdout(line: str):
            sess.add_line(line.rstrip())
            ui.timer(0, self._refresh_output, once=True)

        def on_stderr(line: str):
            sess.add_line(line.rstrip(), '#FF6B6B')
            ui.timer(0, self._refresh_output, once=True)

        def on_done(code: int, err: str):
            sess.add_line(f'[退出码: {code}]', '#8B949E')
            ui.timer(0, self._refresh_output, once=True)

        handle = self.state.ssh.exec_command_streaming(
            cmd, on_stdout, on_stderr, on_done)
        self._current_handle = handle

    def _run_quick(self, cmd: str):
        self._cmd_input.value = cmd
        self._execute_command()

    # ─── 流式 / 阻塞切换 ───────────────────────────

    def _toggle_stream(self):
        self._stream_mode = not self._stream_mode
        self._stream_btn.set_text('流式' if self._stream_mode else '阻塞')

    # ─── 清屏 ──────────────────────────────────────

    def _clear_output(self):
        self._sessions[self._active_idx].clear()
        self._refresh_output()

    # ─── 输出 ──────────────────────────────────────

    def _refresh_output(self):
        if self._active_idx < len(self._output_logs):
            log = self._output_logs[self._active_idx]
            log.clear()
            for text, color in self._sessions[self._active_idx].get_lines():
                log.push(text)

    def _push_output(self, text: str):
        if self._active_idx < len(self._output_logs):
            self._output_logs[self._active_idx].push(text)
