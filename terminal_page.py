"""
PiManager 多标签命令终端 - 多 Agent 独立会话
支持多标签、命令历史、快捷命令、独立输出
"""
import customtkinter as ctk
import threading
import datetime
import os
import tkinter as tk
from collections import deque
from typing import Optional


# ===== 快捷命令预设 =====
QUICK_COMMANDS = [
    ("📊 状态", "top -bn1 | head -8"),
    ("📁 列表", "ls -lah"),
    ("💾 磁盘", "df -h"),
    ("🧠 内存", "free -m"),
    ("🌡️ 温度", "vcgencmd measure_temp"),
    ("⏱ 运行", "uptime"),
    ("🔌 网络", "ip addr show | grep 'inet '"),
    ("📦 进程", "ps aux --sort=-%mem | head -8"),
    ("🐍 Python", "python3 --version 2>&1; pip3 list 2>/dev/null | tail -5"),
    ("🔑 用户", "whoami; id"),
]


# ===== Canvas 终端输出组件（替代 CTkTextbox，真透明看背景） =====

class CanvasTerminalOutput(ctk.CTkFrame):
    """基于 Canvas 的终端输出区 — 文字直接绘制在能显示背景图的画布上。"""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", corner_radius=0, **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # 内部 tk.Canvas — 背景由 _apply_bg_fragment 绘制
        self._canvas = tk.Canvas(
            self, highlightthickness=0, bd=0, bg="#0D1117",
            selectborderwidth=0, insertwidth=0)
        self._canvas.grid(row=0, column=0, sticky="nsew")

        # 文本行缓冲区
        self._lines: list[str] = []
        self._text_ids: list[int] = []
        self._line_height = 18
        self._pad_x = 12
        self._pad_y = 8
        self._visible_start = 0

        # 字体颜色
        self._text_color = "#C9D1D9"
        self._err_color = "#FF6B6B"

        # 滚动
        self._canvas.bind("<MouseWheel>", self._on_mousewheel)
        self._canvas.bind("<Button-4>", self._on_mousewheel)
        self._canvas.bind("<Button-5>", self._on_mousewheel)
        self.bind("<Configure>", self._on_resize)

    def insert(self, position: str, text: str, tag: str = None):
        """追加文本（兼容 CTkTextbox 接口）"""
        color = self._err_color if tag == "stderr" else self._text_color
        for line in text.split("\n"):
            if line:
                self._lines.append((line, color))
            else:
                self._lines.append(("", color))
        self._redraw()

    def delete(self, start: str, end: str):
        """清空"""
        self._lines.clear()
        self._canvas.delete("text")
        self._text_ids.clear()
        self._visible_start = 0

    def see(self, position: str):
        """滚动到底部"""
        self._scroll_to_bottom()

    def get(self, start: str, end: str) -> str:
        """获取全部文本（兼容 CTkTextbox，用于复制全部）"""
        return "\n".join(line for line, _ in self._lines)

    def _redraw(self):
        """重绘可见文本行。"""
        self._canvas.delete("text")
        self._text_ids.clear()

        if not self._lines:
            return

        cw = self._canvas.winfo_width()
        if cw < 20:
            cw = 600

        # 背景片段 — 在第一次绘制时应用
        self._apply_bg_fragment()

        # 计算可见范围
        ch = self._canvas.winfo_height()
        max_visible = max(1, (ch - self._pad_y * 2) // self._line_height)

        total = len(self._lines)
        if self._visible_start > total - max_visible:
            self._visible_start = max(0, total - max_visible)

        end_idx = min(total, self._visible_start + max_visible)
        y = self._pad_y

        max_chars = max(1, (cw - self._pad_x * 2) // 8)  # 等宽估算

        for i in range(self._visible_start, end_idx):
            line_text, color = self._lines[i]
            display = line_text[:max_chars] if len(line_text) > max_chars else line_text
            if display:
                tid = self._canvas.create_text(
                    self._pad_x, y, anchor="nw",
                    text=display, fill=color,
                    font=("Consolas", 11))
                self._text_ids.append(tid)
            y += self._line_height

        # 滚动条指示
        if total > max_visible:
            self._draw_scroll_indicator(total, max_visible)

    def _apply_bg_fragment(self):
        """把背景图片片段绘制到内部 canvas 上。"""
        try:
            from .app import BackgroundManager
            if not BackgroundManager._enabled:
                return
            pil_full = getattr(BackgroundManager, '_bg_pil_blended', None)
            if pil_full is None:
                return
            content = BackgroundManager._content_frame
            if content is None:
                return
            c = self._canvas
            cw = c.winfo_width()
            ch = c.winfo_height()
            if cw < 20 or ch < 20:
                return
            wx = c.winfo_rootx() - content.winfo_rootx()
            wy = c.winfo_rooty() - content.winfo_rooty()
            from PIL import ImageTk
            left = max(0, int(wx))
            top = max(0, int(wy))
            right = min(pil_full.width, int(wx + cw))
            bottom = min(pil_full.height, int(wy + ch))
            if right > left and bottom > top:
                cropped = pil_full.crop((left, top, right, bottom))
                tk_img = ImageTk.PhotoImage(cropped)
                # 保持引用
                if not hasattr(self, '_bg_refs'):
                    self._bg_refs = []
                self._bg_refs.append(tk_img)
                if len(self._bg_refs) > 10:
                    self._bg_refs = self._bg_refs[-5:]
                c.delete("bg_fragment")
                dx = -int(wx) if wx < 0 else 0
                dy = -int(wy) if wy < 0 else 0
                c.create_image(dx, dy, anchor="nw", image=tk_img, tags="bg_fragment")
                c.tag_lower("bg_fragment")
        except Exception:
            pass

    def _scroll_to_bottom(self):
        """滚动到底部。"""
        ch = self._canvas.winfo_height()
        max_visible = max(1, (ch - self._pad_y * 2) // self._line_height)
        total = len(self._lines)
        self._visible_start = max(0, total - max_visible)
        self._redraw()

    def _scroll(self, delta: int):
        """滚动指定行数。"""
        ch = self._canvas.winfo_height()
        max_visible = max(1, (ch - self._pad_y * 2) // self._line_height)
        total = len(self._lines)
        self._visible_start = max(0, min(total - max_visible,
                                         self._visible_start + delta))
        self._redraw()

    def _on_mousewheel(self, event):
        """鼠标滚轮滚动。"""
        if event.num == 4 or event.delta > 0:
            self._scroll(-3)
        elif event.num == 5 or event.delta < 0:
            self._scroll(3)

    def _on_resize(self, event=None):
        """容器大小变化时重绘。"""
        self._redraw()

    def _draw_scroll_indicator(self, total: int, visible: int):
        """绘制滚动条指示器。"""
        cw = self._canvas.winfo_width()
        ch = self._canvas.winfo_height()
        if ch < 20:
            return
        bar_w = 4
        bar_x = cw - bar_w - 4
        bar_h = max(20, int(ch * visible / total))
        bar_y = int((ch - bar_h) * self._visible_start / max(1, total - visible))
        self._canvas.delete("scrollbar")
        self._canvas.create_rectangle(
            bar_x, bar_y, bar_x + bar_w, bar_y + bar_h,
            fill="#555555", outline="", tags="scrollbar")


class TerminalSession:
    """单个终端会话 - 独立的输出缓冲区和命令历史"""

    def __init__(self, name: str, index: int):
        self.name = name
        self.index = index
        self.history: deque = deque(maxlen=200)  # 命令历史
        self.history_index = -1
        self.created_at = datetime.datetime.now()

    def add_history(self, cmd: str):
        if cmd.strip() and (not self.history or self.history[-1] != cmd):
            self.history.append(cmd)

    def history_up(self) -> Optional[str]:
        """上一条历史命令"""
        if not self.history:
            return None
        if self.history_index <= 0:
            self.history_index = 0
            return self.history[0]
        self.history_index -= 1
        return self.history[self.history_index]

    def history_down(self) -> Optional[str]:
        """下一条历史命令"""
        if not self.history:
            return None
        if self.history_index >= len(self.history) - 1:
            self.history_index = len(self.history)
            return ""
        self.history_index += 1
        return self.history[self.history_index]

    def reset_history_index(self):
        self.history_index = len(self.history)


class TerminalTab:
    """终端标签页 UI 组件"""

    def __init__(self, master, session: TerminalSession, ssh_client, app_ref):
        self._ssh = ssh_client
        self._session = session
        self._app = app_ref
        self._running = False

        # 容器
        self.frame = ctk.CTkFrame(master, fg_color="transparent", corner_radius=0)
        self.frame.grid_columnconfigure(0, weight=1)
        self.frame.grid_rowconfigure(0, weight=1)
        self.frame.grid_rowconfigure(1, weight=0)

        # 输出区 — 使用 Canvas 终端输出（真透明，能看到背景图）
        self._output = CanvasTerminalOutput(
            self.frame, border_width=1,
            border_color=("gray55", "gray35"))
        self._output.grid(row=0, column=0, sticky="nsew", padx=5, pady=(2, 2))

        # 命令输入行
        self._build_input_line()

        # 欢迎横幅
        self._print_banner()

    def _build_input_line(self):
        """命令输入行"""
        input_frame = ctk.CTkFrame(self.frame, fg_color="transparent", corner_radius=0)
        input_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=(0, 5))
        input_frame.grid_columnconfigure(1, weight=1)

        # 提示符
        ctk.CTkLabel(
            input_frame,
            text="pi@zero:~$",
            font=ctk.CTkFont(family="Consolas", size=13),
            text_color="#4CAF50",
        ).grid(row=0, column=0, padx=(10, 4), pady=6)

        # 输入框
        self._entry = ctk.CTkEntry(
            input_frame,
            font=ctk.CTkFont(family="Consolas", size=13),
            fg_color="transparent",
            text_color="#C9D1D9",
            border_width=1,
            border_color=("gray55", "gray35"),
            placeholder_text="输入命令...",
        )
        self._entry.grid(row=0, column=1, sticky="ew", padx=(0, 4), pady=6)
        self._entry.bind("<Return>", self._on_send)
        self._entry.bind("<Up>", self._on_history_up)
        self._entry.bind("<Down>", self._on_history_down)

        # 发送按钮
        ctk.CTkButton(
            input_frame,
            text="▶",
            width=36,
            height=28,
            font=ctk.CTkFont(size=14),
            command=self._on_send,
            fg_color="#2B5B2B",
            hover_color="#3A7A3A",
        ).grid(row=0, column=2, padx=(0, 8), pady=6)

    def _print_banner(self):
        """欢迎横幅"""
        banner = f"""╔══════════════════════════════════════════════╗
║  🥧 PiManager Terminal — {self._session.name: <28}║
║  树莓派 Zero W · 轻量远程命令终端           ║
║  ↑↓ 浏览历史 · 多标签并行操作               ║
╚══════════════════════════════════════════════╝
"""
        self._output.insert("end", banner)
        self._output.see("end")

    def _log(self, text: str, tag: str = None):
        """向输出区追加文本"""
        self._output.insert("end", text, tag)
        self._output.see("end")

    def _on_send(self, event=None):
        """发送命令"""
        cmd = self._entry.get().strip()
        self._entry.delete(0, "end")
        self._session.reset_history_index()

        if not cmd:
            return

        self._session.add_history(cmd)

        if cmd.lower() in ("clear", "cls"):
            self._output.delete("1.0", "end")
            return

        if not self._ssh.connected:
            self._log("\n❌ 未连接到树莓派，请先连接\n")
            return

        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self._log(f"\n[{ts}] 💲 {cmd}\n")

        if hasattr(self._app, '_status_label'):
            self._app._status_label.configure(text=f"执行: {cmd[:60]}...")

        self._running = True
        self._entry.configure(state="disabled", placeholder_text="执行中...")

        def _exec():
            try:
                code, out, err = self._ssh.exec_command(cmd, timeout=120)
                self.frame.after(0, lambda: self._on_result(out, err, cmd))
            except Exception as e:
                self.frame.after(0, lambda: self._on_result("", str(e), cmd))

        threading.Thread(target=_exec, daemon=True).start()

    def _on_result(self, stdout: str, stderr: str, cmd: str):
        """命令结果回调"""
        if stdout:
            self._log(stdout.rstrip() + "\n")
        if stderr:
            self._log(stderr.rstrip() + "\n", "stderr")
        self._running = False
        self._entry.configure(state="normal", placeholder_text="输入命令...")
        self._entry.focus_set()

        if hasattr(self._app, '_status_label'):
            self._app._status_label.configure(text="就绪")

    def _on_history_up(self, event=None):
        """上箭头 - 上一条历史"""
        cmd = self._session.history_up()
        if cmd is not None:
            self._entry.delete(0, "end")
            self._entry.insert(0, cmd)
        return "break"

    def _on_history_down(self, event=None):
        """下箭头 - 下一条历史"""
        cmd = self._session.history_down()
        if cmd is not None:
            self._entry.delete(0, "end")
            self._entry.insert(0, cmd)
        return "break"

    def focus_input(self):
        """聚焦输入框"""
        self._entry.focus_set()

    def clear(self):
        """清屏"""
        self._output.delete("1.0", "end")


class TerminalPage(ctk.CTkFrame):
    """多标签命令终端页面"""

    def __init__(self, master, ssh_client, config: dict = None, app_ref=None):
        super().__init__(master, fg_color="transparent", corner_radius=0)
        self._ssh = ssh_client
        self._config = config or {}
        self._app_ref = app_ref
        self._session_counter = 0
        self._tabs: list[TerminalTab] = []
        self._tab_buttons: list[ctk.CTkButton] = []
        self._active_index = 0

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)  # 快捷命令
        self.grid_rowconfigure(1, weight=0)  # 标签栏
        self.grid_rowconfigure(2, weight=1)  # 终端区
        self.grid_rowconfigure(3, weight=0)  # 底部按钮

        self._build_quick_bar()
        self._build_tab_bar()
        self._build_terminal_area()
        self._build_bottom_bar()

        # 创建第一个默认会话
        self._add_session("终端 1")

    # ===== 快捷命令栏 =====

    def _build_quick_bar(self):
        """快捷命令按钮栏"""
        quick_card = self._make_card("⚡ 快捷命令", 0)

        # 前 5 个快捷命令用大按钮
        row_frame = ctk.CTkFrame(quick_card, fg_color="transparent", corner_radius=0)
        row_frame.pack(fill="x", padx=0, pady=2)

        for text, cmd in QUICK_COMMANDS[:5]:
            btn = ctk.CTkButton(
                row_frame,
                text=text,
                width=80,
                height=28,
                font=ctk.CTkFont(size=11),
                fg_color="#1E3A1E",
                hover_color="#2A4A2A",
                command=lambda c=cmd: self._run_quick_cmd(c),
            )
            btn.pack(side="left", padx=3, pady=3)

        # 后 5 个快捷命令
        row_frame2 = ctk.CTkFrame(quick_card, fg_color="transparent", corner_radius=0)
        row_frame2.pack(fill="x", padx=0, pady=2)

        for text, cmd in QUICK_COMMANDS[5:]:
            btn = ctk.CTkButton(
                row_frame2,
                text=text,
                width=80,
                height=28,
                font=ctk.CTkFont(size=11),
                fg_color="#1E3A1E",
                hover_color="#2A4A2A",
                command=lambda c=cmd: self._run_quick_cmd(c),
            )
            btn.pack(side="left", padx=3, pady=3)

    def _run_quick_cmd(self, cmd: str):
        """在当前活跃标签执行快捷命令"""
        if 0 <= self._active_index < len(self._tabs):
            tab = self._tabs[self._active_index]
            tab._entry.delete(0, "end")
            tab._entry.insert(0, cmd)
            tab._on_send()

    # ===== 标签栏 =====

    def _build_tab_bar(self):
        """构建标签栏"""
        self._tab_bar_frame = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        self._tab_bar_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=(2, 0))

        self._tab_buttons_frame = ctk.CTkFrame(
            self._tab_bar_frame, fg_color="transparent", corner_radius=0
        )
        self._tab_buttons_frame.pack(side="left", fill="x", expand=True, padx=0)

        # 添加标签按钮
        self._btn_add_tab = ctk.CTkButton(
            self._tab_bar_frame,
            text="＋",
            width=32,
            height=28,
            font=ctk.CTkFont(size=16),
            fg_color="transparent",
            hover_color="#333",
            command=self._add_session,
        )
        self._btn_add_tab.pack(side="right", padx=(2, 0))

    def _add_session(self, name: str = None):
        """创建新的终端会话"""
        self._session_counter += 1
        if name is None:
            name = f"终端 {self._session_counter}"

        session = TerminalSession(name, self._session_counter)
        tab = TerminalTab(self._terminal_area, session, self._ssh, self._app_ref)
        self._tabs.append(tab)

        # 创建标签按钮
        self._rebuild_tab_buttons()
        self._switch_tab(len(self._tabs) - 1)

    def _remove_session(self, index: int):
        """关闭终端会话"""
        if len(self._tabs) <= 1:
            # 至少保留一个
            return

        tab = self._tabs.pop(index)
        tab.frame.grid_remove()
        tab.frame.destroy()

        self._rebuild_tab_buttons()
        new_idx = min(index, len(self._tabs) - 1)
        self._switch_tab(new_idx)

    def _rebuild_tab_buttons(self):
        """重建标签按钮"""
        for btn in self._tab_buttons:
            btn.destroy()
        self._tab_buttons.clear()

        for i, tab in enumerate(self._tabs):
            is_active = i == self._active_index
            text = tab._session.name
            if len(text) > 10:
                text = text[:9] + "…"

            btn_frame = ctk.CTkFrame(self._tab_buttons_frame, fg_color="transparent")
            btn_frame.pack(side="left", padx=1)

            tab_btn = ctk.CTkButton(
                btn_frame,
                text=f" {text} ",
                height=28,
                font=ctk.CTkFont(size=12),
                fg_color="#2A5A2A" if is_active else "transparent",
                hover_color="#3A4A3A",
                command=lambda idx=i: self._switch_tab(idx),
            )
            tab_btn.pack(side="left")

            # 关闭按钮（仅当多于 1 个标签时）
            if len(self._tabs) > 1:
                close_btn = ctk.CTkButton(
                    btn_frame,
                    text="✕",
                    width=20,
                    height=28,
                    font=ctk.CTkFont(size=10),
                    fg_color="transparent",
                    hover_color="#8B0000",
                    command=lambda idx=i: self._remove_session(idx),
                )
                close_btn.pack(side="left")

            self._tab_buttons.append(btn_frame)

    def _switch_tab(self, index: int):
        """切换到指定标签"""
        if index < 0 or index >= len(self._tabs):
            return

        self._active_index = index

        # 隐藏所有终端
        for i, tab in enumerate(self._tabs):
            if i == index:
                tab.frame.grid(row=0, column=0, sticky="nsew")
                tab.focus_input()
            else:
                tab.frame.grid_remove()

        # 更新标签按钮样式
        self._rebuild_tab_buttons()

    # ===== 终端显示区 =====

    def _build_terminal_area(self):
        """终端显示区域"""
        self._terminal_area = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        self._terminal_area.grid(row=2, column=0, sticky="nsew", padx=5, pady=2)
        self._terminal_area.grid_columnconfigure(0, weight=1)
        self._terminal_area.grid_rowconfigure(0, weight=1)

    # ===== 底部操作栏 =====

    def _build_bottom_bar(self):
        """底部操作栏"""
        bottom = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        bottom.grid(row=3, column=0, sticky="ew", padx=5, pady=(0, 5))

        ctk.CTkButton(
            bottom,
            text="🗑 清屏",
            width=70,
            height=26,
            font=ctk.CTkFont(size=11),
            fg_color="transparent",
            border_width=1,
            border_color=("gray40", "gray30"),
            command=self._clear_active,
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            bottom,
            text="📋 复制全部",
            width=80,
            height=26,
            font=ctk.CTkFont(size=11),
            fg_color="transparent",
            border_width=1,
            border_color=("gray40", "gray30"),
            command=self._copy_all,
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            bottom,
            text="＋ 新建终端",
            width=90,
            height=26,
            font=ctk.CTkFont(size=11),
            fg_color="#2B5B2B",
            hover_color="#3A7A3A",
            command=self._add_session,
        ).pack(side="right", padx=2)

    def _clear_active(self):
        """清空当前终端"""
        if 0 <= self._active_index < len(self._tabs):
            self._tabs[self._active_index].clear()

    def _copy_all(self):
        """复制当前终端全部内容到剪贴板"""
        if 0 <= self._active_index < len(self._tabs):
            text = self._tabs[self._active_index]._output.get("1.0", "end-1c")
            self.clipboard_clear()
            self.clipboard_append(text)

    # ===== 卡片辅助 =====

    def _make_card(self, title: str, row: int) -> ctk.CTkFrame:
        """创建卡片容器 — 透明背景 + 细边框，背景图穿透"""
        frame = ctk.CTkFrame(
            self, fg_color="transparent", border_width=1,
            border_color=("gray55", "gray35"), corner_radius=8)
        frame.grid(row=row, column=0, sticky="ew", padx=5, pady=(5, 2))

        ctk.CTkLabel(
            frame,
            text=title,
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w",
        ).pack(anchor="w", padx=10, pady=(6, 2))

        return frame
