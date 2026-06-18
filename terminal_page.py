"""
PiManager 命令终端 v3 — tkinter + Canvas 终端输出 + 流式执行
"""
import tkinter as tk
import threading
import shlex
from collections import deque

from .theme import ThemeColors
from .app import BackgroundManager

# 全量快捷命令 (10个)
QUICK_COMMANDS = [
    ("状态", "top -bn1 | head -8"),
    ("列表", "ls -lah"),
    ("磁盘", "df -h"),
    ("内存", "free -m"),
    ("温度", "vcgencmd measure_temp"),
    ("运行", "uptime"),
    ("网络", "ip addr show | grep 'inet '"),
    ("进程", "ps aux --sort=-%mem | head -8"),
    ("Python", "python3 --version 2>&1; pip3 list 2>/dev/null | tail -5"),
    ("用户", "whoami; id"),
]


# ============================================================
#  CanvasTerminalOutput — Canvas 终端输出
# ============================================================

class CanvasTerminalOutput(tk.Frame):
    """Canvas 渲染的终端输出。"""

    def __init__(self, master, **kw):
        super().__init__(master, bg=ThemeColors.get("bg"), **kw)
        self._lines = []  # [(text, color)]
        self._auto_scroll = True
        self._scroll_y = 0

        self._canvas = tk.Canvas(self, bg=ThemeColors.get("bg"),
                                 highlightthickness=0, bd=0)
        self._canvas.pack(side="left", fill="both", expand=True)

        self._scrollbar = tk.Scrollbar(self, orient="vertical",
                                       command=self._on_scrollbar)
        self._scrollbar.pack(side="right", fill="y")

        self._canvas.bind("<MouseWheel>", self._on_mousewheel)
        self._canvas.bind("<Configure>", lambda e: self._redraw())
        BackgroundManager.register(self._canvas)

    def insert(self, pos, text: str, tag=None):
        color = ThemeColors.get("text")
        if tag == "stderr":
            color = "#FF6B6B"
        elif tag == "prompt":
            color = ThemeColors.get("accent")
        self._lines.append((text, color))
        if self._auto_scroll:
            self._scroll_to_bottom()
        self._redraw()

    def delete(self, start, end=None):
        self._lines.clear()
        self._scroll_y = 0
        self._redraw()

    def see(self, pos):
        self._scroll_to_bottom()

    def get(self, start, end=None):
        return "\n".join(line for line, _ in self._lines)

    def _on_mousewheel(self, event):
        self._scroll_y = max(0, self._scroll_y -
                            (1 if event.delta > 0 else -1) * 30)
        self._auto_scroll = False
        self._redraw()

    def _on_scrollbar(self, *args):
        if args[0] == "moveto":
            self._scroll_y = int(float(args[1]) * len(self._lines) * 18)
            self._auto_scroll = False
            self._redraw()

    def _scroll_to_bottom(self):
        total_h = len(self._lines) * 18
        visible_h = self._canvas.winfo_height()
        self._scroll_y = max(0, total_h - visible_h + 20)

    def _redraw(self):
        c = self._canvas
        c.delete("all")
        cw = c.winfo_width() or 400
        BackgroundManager.apply_to_canvas(c)

        y0 = -self._scroll_y
        font = ("Microsoft YaHei", 10)
        for i, (text, color) in enumerate(self._lines):
            y = y0 + i * 18
            if y < -18 or y > c.winfo_height() + 18:
                continue
            display = text[:120] if len(text) > 120 else text
            c.create_text(6, y + 2, text=display, anchor="nw",
                          fill=color, font=font)

        total_h = len(self._lines) * 18
        vis_h = c.winfo_height()
        if total_h > vis_h:
            self._scrollbar.set(
                self._scroll_y / (total_h - vis_h),
                (self._scroll_y + vis_h) / total_h
            )

    def refresh_theme(self):
        self._canvas.configure(bg=ThemeColors.get("bg"))
        self._redraw()


# ============================================================
#  TerminalSession — 会话数据模型
# ============================================================

class TerminalSession:
    def __init__(self, name: str, index: int):
        self.name = name
        self.index = index
        self.history = deque(maxlen=500)
        self.history_index = -1

    def add_history(self, cmd: str):
        if cmd.strip():
            self.history.append(cmd)

    def history_up(self) -> str:
        if not self.history:
            return ""
        if self.history_index == -1:
            self.history_index = len(self.history) - 1
        elif self.history_index > 0:
            self.history_index -= 1
        return self.history[self.history_index] if self.history_index < len(self.history) else ""

    def history_down(self) -> str:
        if self.history_index == -1:
            return ""
        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            return self.history[self.history_index]
        self.history_index = -1
        return ""

    def reset_history(self):
        self.history_index = -1


# ============================================================
#  TerminalTab — 单个终端标签页（支持流式执行）
# ============================================================

class TerminalTab(tk.Frame):
    """单个终端标签 — 流式 + 阻塞双模式。"""

    def __init__(self, master, ssh_client, session: TerminalSession, **kw):
        super().__init__(master, bg=ThemeColors.get("bg"), **kw)
        self._ssh = ssh_client
        self._session = session
        self._running = False
        self._stream_handle = None
        self._stream_var = tk.BooleanVar(value=False)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)

        self._output = CanvasTerminalOutput(self)
        self._output.grid(row=0, column=0, sticky="nsew")

        self._build_input()
        self._output.insert("end", f"=== {session.name} ===\n", "prompt")
        self._output.insert("end", "输入命令后按 Enter 执行\n\n")

    def _build_input(self):
        input_frame = tk.Frame(self, bg=ThemeColors.get("bg_card"), height=34)
        input_frame.grid(row=1, column=0, sticky="ew")
        input_frame.grid_propagate(False)

        tk.Label(input_frame, text=" $ ", bg=ThemeColors.get("bg_card"),
                fg=ThemeColors.get("accent"), font=("Microsoft YaHei", 11)).pack(
            side="left", padx=(6, 0))

        self._entry = tk.Entry(input_frame, bg=ThemeColors.get("bg_card"),
                               fg=ThemeColors.get("text"),
                               insertbackground=ThemeColors.get("text"),
                               relief="flat", bd=0, font=("Consolas", 11))
        self._entry.pack(side="left", fill="x", expand=True, padx=4, pady=4)
        self._entry.bind("<Return>", self._on_enter)
        self._entry.bind("<Up>", self._on_up)
        self._entry.bind("<Down>", self._on_down)
        self._entry.bind("<Control-c>", self._on_ctrl_c)

        self._btn_send = tk.Button(input_frame, text="发送",
                                   command=self._on_send,
                                   bg="#2B5B2B", fg="white", relief="flat",
                                   font=("Segoe UI", 10), padx=8)
        self._btn_send.pack(side="right", padx=4, pady=2)

        tk.Button(input_frame, text="清屏",
                 command=lambda: self._output.delete("1.0", "end"),
                 bg="#333333", fg="white", relief="flat",
                 font=("Segoe UI", 10), padx=8).pack(side="right", padx=2, pady=2)

    def _on_enter(self, event):
        self._on_send()

    def _on_up(self, event):
        cmd = self._session.history_up()
        if cmd:
            self._entry.delete(0, "end")
            self._entry.insert(0, cmd)

    def _on_down(self, event):
        cmd = self._session.history_down()
        self._entry.delete(0, "end")
        self._entry.insert(0, cmd)

    def _on_ctrl_c(self, event):
        if self._running and self._stream_handle:
            self._stop_streaming()
            return "break"

    def _on_send(self):
        if self._running and self._stream_handle and self._stream_var.get():
            self._stop_streaming()
            if not self._entry.get().strip():
                return
        self._execute()

    def _execute(self):
        cmd = self._entry.get().strip()
        if not cmd:
            return
        self._entry.delete(0, "end")
        self._session.add_history(cmd)
        self._output.insert("end", f"$ {cmd}\n", "prompt")

        if not self._ssh.connected:
            self._output.insert("end", "未连接到树莓派\n", "stderr")
            return

        if self._stream_var.get():
            self._exec_streaming(cmd)
        else:
            self._exec_blocking(cmd)

    def _exec_blocking(self, cmd: str):
        self._running = True
        self._btn_send.configure(text="...", state="disabled")

        def _do():
            ec, out, err = self._ssh.exec_command(cmd, timeout=30)
            if out:
                for line in out.rstrip("\n").split("\n"):
                    self.after(0, lambda l=line: self._output.insert("end", l + "\n"))
            if err:
                for line in err.rstrip("\n").split("\n"):
                    self.after(0, lambda l=line: self._output.insert("end", l + "\n", "stderr"))
            if ec != 0:
                self.after(0, lambda: self._output.insert("end", f"[exit: {ec}]\n", "stderr"))
            self.after(0, self._finish_streaming)

        threading.Thread(target=_do, daemon=True).start()

    def _exec_streaming(self, cmd: str):
        self._running = True
        self._stream_handle = None
        self._btn_send.configure(text="停止", bg="#8B0000")

        def on_stdout(line):
            self.after(0, lambda l=line: self._output.insert("end", l, ""))

        def on_stderr(line):
            self.after(0, lambda l=line: self._output.insert("end", l, "stderr"))

        def on_done(exit_code, error):
            if error:
                self.after(0, lambda: self._output.insert("end", f"错误: {error}\n", "stderr"))
            if exit_code != 0:
                self.after(0, lambda: self._output.insert("end", f"[exit: {exit_code}]\n", "stderr"))
            self.after(0, self._finish_streaming)

        def _stream():
            handle = self._ssh.exec_command_streaming(
                cmd, on_stdout, on_stderr, on_done, timeout=120)
            self.after(0, lambda h=handle: setattr(self, '_stream_handle', h))

        threading.Thread(target=_stream, daemon=True).start()

    def _stop_streaming(self):
        if self._stream_handle:
            self._stream_handle.send_ctrl_c()
            self._output.insert("end", "Ctrl+C (SIGINT) 已发送...\n", "stderr")
            self.after(1500, self._force_cancel_if_running)

    def _force_cancel_if_running(self):
        if self._stream_handle and self._stream_handle.is_running:
            self._stream_handle.cancel()
            self._output.insert("end", "进程未响应，已强制关闭\n", "stderr")
        self._finish_streaming()

    def _finish_streaming(self):
        self._running = False
        self._stream_handle = None
        self._btn_send.configure(text="发送", bg="#2B5B2B", state="normal")
        self._entry.configure(state="normal")

    def focus_input(self):
        self._entry.focus_set()

    def refresh_theme(self):
        self.configure(bg=ThemeColors.get("bg"))
        self._output.refresh_theme()


# ============================================================
#  TerminalPage — 多标签控制器
# ============================================================

class TerminalPage(tk.Frame):
    """多标签终端页。"""

    def __init__(self, master, ssh_client, config: dict = None, app_ref=None):
        super().__init__(master, bg=ThemeColors.get("bg"))
        self._ssh = ssh_client
        self._config = config or {}
        self._app = app_ref
        self._sessions = []
        self._tabs = {}
        self._active_idx = 0
        self._session_counter = 0

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=1)

        self._build_tabbar()
        self._build_quickbar()
        self._build_bottombar()
        self._add_session("终端 1")

    def _build_tabbar(self):
        self._tab_frame = tk.Frame(self, bg=ThemeColors.get("bg_card"), height=34)
        self._tab_frame.grid(row=0, column=0, sticky="ew")
        self._tab_frame.grid_propagate(False)
        self._tab_buttons = []
        tk.Button(self._tab_frame, text="＋ 新建",
                 command=lambda: self._add_session(f"终端 {self._session_counter + 1}"),
                 bg="#2B5B2B", fg="white", relief="flat",
                 font=("Segoe UI", 9), padx=8).pack(side="right", padx=4, pady=4)

    def _rebuild_tab_buttons(self):
        for b in self._tab_buttons:
            b.destroy()
        self._tab_buttons.clear()
        for i, sess in enumerate(self._sessions):
            btn = tk.Button(self._tab_frame, text=sess.name,
                           command=lambda idx=i: self._switch_tab(idx),
                           bg="#2B5B2B" if i == self._active_idx else ThemeColors.get("bg_card"),
                           fg="white" if i == self._active_idx else ThemeColors.get("text_secondary"),
                           relief="flat", font=("Segoe UI", 9), padx=10)
            btn.pack(side="left", padx=1, pady=2)
            self._tab_buttons.append(btn)

    def _build_quickbar(self):
        qbar = tk.Frame(self, bg=ThemeColors.get("bg_card"), height=60)
        qbar.grid(row=1, column=0, sticky="ew")
        qbar.grid_propagate(False)

        for row_idx in range(0, len(QUICK_COMMANDS), 5):
            row_frame = tk.Frame(qbar, bg=ThemeColors.get("bg_card"))
            row_frame.pack(fill="x", padx=2, pady=1)
            for text, cmd in QUICK_COMMANDS[row_idx:row_idx + 5]:
                tk.Button(row_frame, text=text, command=lambda c=cmd: self._run_quick(c),
                         bg="#1E3A1E", fg="#4CAF50", relief="flat",
                         font=("Segoe UI", 9), padx=8).pack(side="left", padx=2, pady=2)

    def _build_bottombar(self):
        bar = tk.Frame(self, bg=ThemeColors.get("bg_card"), height=30)
        bar.grid(row=3, column=0, sticky="ew")
        bar.grid_propagate(False)
        tk.Button(bar, text="清屏", command=lambda: self._clear_active(),
                 bg="#333333", fg="white", relief="flat",
                 font=("Segoe UI", 9), padx=8).pack(side="left", padx=4, pady=3)
        tk.Button(bar, text="复制全部", command=lambda: self._copy_all(),
                 bg="#333333", fg="white", relief="flat",
                 font=("Segoe UI", 9), padx=8).pack(side="left", padx=2, pady=3)
        tk.Button(bar, text="＋ 新终端",
                 command=lambda: self._add_session(f"终端 {self._session_counter + 1}"),
                 bg="#2B5B2B", fg="white", relief="flat",
                 font=("Segoe UI", 9), padx=8).pack(side="right", padx=4, pady=3)

    def _add_session(self, name: str):
        self._session_counter += 1
        sess = TerminalSession(name, self._session_counter)
        self._sessions.append(sess)
        tab = TerminalTab(self, self._ssh, sess)
        tab.grid(row=2, column=0, sticky="nsew")
        self._tabs[sess.index] = tab
        self._switch_tab(len(self._sessions) - 1)

    def _switch_tab(self, idx: int):
        self._active_idx = idx
        target_key = self._sessions[idx].index if idx < len(self._sessions) else idx
        for key, tab in self._tabs.items():
            if key == target_key:
                tab.grid(row=2, column=0, sticky="nsew")
            else:
                tab.grid_remove()
        self._rebuild_tab_buttons()

    def _active_tab(self):
        """获取当前激活的 TerminalTab。"""
        if 0 <= self._active_idx < len(self._sessions):
            return self._tabs.get(self._sessions[self._active_idx].index)
        return None

    def _run_quick(self, cmd: str):
        tab = self._active_tab()
        if tab:
            tab._entry.delete(0, "end")
            tab._entry.insert(0, cmd)
            tab._on_send()

    def _clear_active(self):
        tab = self._active_tab()
        if tab:
            tab._output.delete("1.0", "end")

    def _copy_all(self):
        tab = self._active_tab()
        if tab:
            text = tab._output.get("1.0", "end")
            self.clipboard_clear()
            self.clipboard_append(text)

    def refresh_theme(self):
        self.configure(bg=ThemeColors.get("bg"))
        for tab in self._tabs.values():
            tab.refresh_theme()
