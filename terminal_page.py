"""
PiManager 命令终端 v2 — tkinter + Canvas 终端输出（去 CTk）
"""
import tkinter as tk
import threading
from collections import deque

from .theme import ThemeColors


# ============================================================
#  CanvasTerminalOutput — Canvas 终端输出（保留 v1 核心逻辑）
# ============================================================

class CanvasTerminalOutput(tk.Frame):
    """Canvas 渲染的终端输出 — 替代 CTkTextbox。"""

    def __init__(self, master, **kw):
        super().__init__(master, bg=ThemeColors.get("bg"), **kw)
        self._lines = []  # [(text, color)]
        self._auto_scroll = True
        self._scroll_y = 0

        self._canvas = tk.Canvas(self, bg=ThemeColors.get("bg"),
                                 highlightthickness=0, bd=0)
        self._canvas.pack(side="left", fill="both", expand=True)

        # 滚动条
        self._scrollbar = tk.Scrollbar(self, orient="vertical",
                                       command=self._on_scrollbar)
        self._scrollbar.pack(side="right", fill="y")

        self._canvas.bind("<MouseWheel>", self._on_mousewheel)
        self._canvas.bind("<Configure>", lambda e: self._redraw())

    def insert(self, pos, text: str, tag=None):
        """添加一行文字。兼容旧 API。"""
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

        y0 = -self._scroll_y
        font = ("Consolas", 10)

        for i, (text, color) in enumerate(self._lines):
            y = y0 + i * 18
            if y < -18 or y > c.winfo_height() + 18:
                continue
            display = text[:120] if len(text) > 120 else text
            c.create_text(6, y + 2, text=display, anchor="nw",
                          fill=color, font=font)

        # 更新滚动条
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
        return self.history[self.history_index]

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
#  TerminalTab — 单个终端标签页
# ============================================================

class TerminalTab(tk.Frame):
    """单个终端标签 — tk.Entry 输入 + CanvasTerminalOutput 输出。"""

    def __init__(self, master, ssh_client, session: TerminalSession, **kw):
        super().__init__(master, bg=ThemeColors.get("bg"), **kw)
        self._ssh = ssh_client
        self._session = session
        self._streaming = False

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)

        # 终端输出
        self._output = CanvasTerminalOutput(self)
        self._output.grid(row=0, column=0, sticky="nsew")

        # 输入行
        self._build_input()

        # 欢迎信息
        self._output.insert("end", f"=== {session.name} ===\n", "prompt")
        self._output.insert("end", "输入命令后按 Enter 执行\n\n")

    def _build_input(self):
        input_frame = tk.Frame(self, bg=ThemeColors.get("bg_card"), height=32)
        input_frame.grid(row=1, column=0, sticky="ew")
        input_frame.grid_propagate(False)

        # 提示符
        tk.Label(input_frame, text=" $ ", bg=ThemeColors.get("bg_card"),
                fg=ThemeColors.get("accent"), font=("Consolas", 11)).pack(
            side="left", padx=(6, 0))

        # 输入框
        self._entry = tk.Entry(input_frame,
                               bg=ThemeColors.get("bg_card"),
                               fg=ThemeColors.get("text"),
                               insertbackground=ThemeColors.get("text"),
                               relief="flat", bd=0, font=("Consolas", 11))
        self._entry.pack(side="left", fill="x", expand=True, padx=4, pady=4)
        self._entry.bind("<Return>", self._on_enter)
        self._entry.bind("<Up>", self._on_up)
        self._entry.bind("<Down>", self._on_down)

        # 发送按钮
        self._btn_send = tk.Button(input_frame, text="▶ 发送",
                                   command=self._execute,
                                   bg="#2B5B2B", fg="white", relief="flat",
                                   font=("Segoe UI", 10), padx=8)
        self._btn_send.pack(side="right", padx=4, pady=2)

        # 清屏按钮
        tk.Button(input_frame, text="清屏", command=lambda: self._output.delete("1.0", "end"),
                 bg="#333333", fg="white", relief="flat",
                 font=("Segoe UI", 10), padx=8).pack(side="right", padx=2, pady=2)

    def _on_enter(self, event):
        self._execute()

    def _on_up(self, event):
        cmd = self._session.history_up()
        if cmd:
            self._entry.delete(0, "end")
            self._entry.insert(0, cmd)

    def _on_down(self, event):
        cmd = self._session.history_down()
        self._entry.delete(0, "end")
        self._entry.insert(0, cmd)

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

        def _do():
            ec, out, err = self._ssh.exec_command(cmd, timeout=30)
            if out:
                for line in out.rstrip("\n").split("\n"):
                    self.after(0, lambda l=line: self._output.insert("end", l + "\n"))
            if err:
                for line in err.rstrip("\n").split("\n"):
                    self.after(0, lambda l=line: self._output.insert("end", l + "\n", "stderr"))
            if ec != 0:
                self.after(0, lambda: self._output.insert(
                    "end", f"[exit code: {ec}]\n", "stderr"))

        threading.Thread(target=_do, daemon=True).start()

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

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=1)

        self._build_tabbar()
        self._build_quickbar()
        self._add_session("终端 1")

    def _build_tabbar(self):
        """标签栏 — 简单的 tk.Button 标签。"""
        self._tab_frame = tk.Frame(self, bg=ThemeColors.get("bg_card"), height=34)
        self._tab_frame.grid(row=0, column=0, sticky="ew")
        self._tab_frame.grid_propagate(False)

        self._tab_buttons = []
        self._rebuild_tabs()

        # 新建按钮
        tk.Button(self._tab_frame, text="＋ 新建", command=lambda: self._add_session(f"终端 {len(self._sessions)+1}"),
                 bg="#2B5B2B", fg="white", relief="flat",
                 font=("Segoe UI", 9), padx=8).pack(side="right", padx=4, pady=4)

    def _rebuild_tabs(self):
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
        """快速命令栏。"""
        qbar = tk.Frame(self, bg=ThemeColors.get("bg_card"), height=32)
        qbar.grid(row=1, column=0, sticky="ew")
        qbar.grid_propagate(False)

        quick_cmds = [
            ("📊 状态", "top -bn1 | head -5"),
            ("💾 磁盘", "df -h /"),
            ("🧠 内存", "free -h"),
            ("🌡️ 温度", "vcgencmd measure_temp"),
            ("⏱ 时间", "uptime"),
            ("🌐 IP", "hostname -I"),
        ]
        for text, cmd in quick_cmds:
            tk.Button(qbar, text=text, command=lambda c=cmd: self._run_quick(c),
                     bg="#1E3A1E", fg=ThemeColors.get("accent"),
                     relief="flat", font=("Segoe UI", 9), padx=6).pack(
                side="left", padx=2, pady=3)

    def _add_session(self, name: str):
        sess = TerminalSession(name, len(self._sessions))
        self._sessions.append(sess)

        tab = TerminalTab(self, self._ssh, sess)
        tab.grid(row=2, column=0, sticky="nsew")
        self._tabs[sess.index] = tab

        self._switch_tab(sess.index)

    def _switch_tab(self, idx: int):
        self._active_idx = idx
        for i, tab in self._tabs.items():
            if i == idx:
                tab.grid(row=2, column=0, sticky="nsew")
            else:
                tab.grid_remove()
        self._rebuild_tabs()

    def _run_quick(self, cmd: str):
        if self._active_idx in self._tabs:
            tab = self._tabs[self._active_idx]
            tab._entry.delete(0, "end")
            tab._entry.insert(0, cmd)
            tab._execute()

    def refresh_theme(self):
        self.configure(bg=ThemeColors.get("bg"))
        for tab in self._tabs.values():
            tab.refresh_theme()
