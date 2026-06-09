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
from .theme import ThemeColors


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
    """基于 Canvas 的终端输出区 — 文字直接绘制在能显示背景图的画布上。

    滚动修复：
    - 鼠标滚轮绑定在容器 Frame 上（而非内部 Canvas），解决 Windows 下焦点不在 Canvas 时无法滚动的问题
    - 自动滚动标志：用户手动向上滚动时暂停自动追底，滚到底部时恢复
    - 键盘快捷键：↑↓ PageUp/Down Home/End
    - 滚动条点击跳转
    """

    @property
    def _line_height(self) -> int:
        """行高（跟随字体缩放动态计算）。"""
        return int(self._base_line_height * ThemeColors.get_font_scale())

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", corner_radius=0, **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # 内部 tk.Canvas — 背景由 _apply_bg_fragment 绘制
        self._canvas = tk.Canvas(
            self, highlightthickness=0, bd=0,
            bg=ThemeColors.get("canvas_bg"),
            selectborderwidth=0, insertwidth=0)
        self._canvas.grid(row=0, column=0, sticky="nsew")

        # 文本行缓冲区
        self._lines: list[str] = []
        self._text_ids: list[int] = []
        self._base_line_height = 18
        self._pad_x = 12
        self._pad_y = 8
        self._visible_start = 0

        # ★ 自动滚动标志：True=新输出自动追底，False=用户正在查看历史
        self._auto_scroll = True

        # ★ 防抖：延迟重绘 ID
        self._redraw_after_id = None

        # 字体颜色（跟随主题）
        self._text_color = ThemeColors.get("canvas_text")
        self._err_color = ThemeColors.get("canvas_err")

        # ===== 滚轮事件绑定 =====
        # ★ 关键修复：Windows 下 <MouseWheel> 只发给有焦点的 widget
        # 终端中焦点通常在 CTkEntry（输入框），canvas 永远收不到事件
        # 解决方案：绑定到容器 Frame（self），同时绑定到 canvas 确保覆盖
        self.bind("<MouseWheel>", self._on_mousewheel)
        self._canvas.bind("<MouseWheel>", self._on_mousewheel)
        # Linux 滚轮
        self.bind("<Button-4>", self._on_mousewheel)
        self.bind("<Button-5>", self._on_mousewheel)
        self._canvas.bind("<Button-4>", self._on_mousewheel)
        self._canvas.bind("<Button-5>", self._on_mousewheel)

        # ===== 键盘滚动绑定 =====
        self._canvas.bind("<Up>", lambda e: self._scroll_key(-1))
        self._canvas.bind("<Down>", lambda e: self._scroll_key(1))
        self._canvas.bind("<Prior>", lambda e: self._scroll_page(-1))   # PageUp
        self._canvas.bind("<Next>", lambda e: self._scroll_page(1))     # PageDown
        self._canvas.bind("<Home>", lambda e: self._scroll_home())
        self._canvas.bind("<End>", lambda e: self._scroll_end())
        # 让 canvas 可以接收键盘事件
        self._canvas.bind("<Button-1>", self._on_canvas_click_focus)
        self._canvas.focus_set()

        # ===== 滚动条拖拽 =====
        self._canvas.bind("<B1-Motion>", self._on_scrollbar_drag)
        self._scrollbar_dragging = False

        # 容器大小变化
        self.bind("<Configure>", self._on_resize)

        # ★ 鼠标进入/离开：进入时让 canvas 获取焦点以启用键盘滚动
        self._canvas.bind("<Enter>", lambda e: self._canvas.focus_set())

    def refresh_theme(self):
        """主题切换后刷新 Canvas 背景色和文字颜色。"""
        self._canvas.configure(bg=ThemeColors.get("canvas_bg"))
        self._text_color = ThemeColors.get("canvas_text")
        self._err_color = ThemeColors.get("canvas_err")
        self._do_redraw()

    def insert(self, position: str, text: str, tag: str = None):
        """追加文本（兼容 CTkTextbox 接口）"""
        color = self._err_color if tag == "stderr" else self._text_color
        for line in text.split("\n"):
            if line:
                self._lines.append((line, color))
            else:
                self._lines.append(("", color))
        # ★ 只有自动滚动模式下才追底
        if self._auto_scroll:
            self._scroll_to_bottom()
        self._redraw()

    def delete(self, start: str, end: str):
        """清空"""
        self._lines.clear()
        self._canvas.delete("text")
        self._text_ids.clear()
        self._visible_start = 0
        self._auto_scroll = True

    def see(self, position: str):
        """滚动到底部"""
        self._auto_scroll = True
        self._scroll_to_bottom()

    def get(self, start: str, end: str) -> str:
        """获取全部文本（兼容 CTkTextbox，用于复制全部）"""
        return "\n".join(line for line, _ in self._lines)

    # ===== 核心绘制 =====

    def _redraw(self, delayed: bool = False):
        """重绘可见文本行。

        Args:
            delayed: True 时使用 after_idle 延迟合并多次调用
        """
        if delayed:
            if self._redraw_after_id:
                return
            self._redraw_after_id = self.after_idle(self._do_redraw)
            return
        # 直接重绘前取消待处理的 idle 回调，避免重复绘制
        if self._redraw_after_id:
            self.after_cancel(self._redraw_after_id)
            self._redraw_after_id = None
        self._do_redraw()

    def _do_redraw(self):
        """实际执行重绘。"""
        self._redraw_after_id = None

        if not self._lines:
            self._canvas.delete("text")
            self._canvas.delete("scrollbar")
            return

        # ★ 从容器取尺寸，Canvas sticky=nsew 跟随
        cw = self.winfo_width()
        ch = self.winfo_height()
        if cw < 20:
            cw = self._canvas.winfo_width()
        if ch < 20:
            ch = self._canvas.winfo_height()
        if cw < 20:
            cw = self.winfo_reqwidth()
        if ch < 20:
            ch = max(200, self.winfo_reqheight())
        if cw < 20 or ch < 20:
            if not self._redraw_after_id:
                self._redraw_after_id = self.after(30, self._do_redraw)
            return

        self._canvas.delete("text")
        self._text_ids.clear()

        # 背景片段 — 在第一次绘制时应用
        self._apply_bg_fragment()
        max_visible = max(1, (ch - self._pad_y * 2) // self._line_height)

        total = len(self._lines)
        # ★ 限制 _visible_start 范围
        max_start = max(0, total - max_visible)
        if self._visible_start > max_start:
            self._visible_start = max_start
        if self._visible_start < 0:
            self._visible_start = 0

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
                    font=ThemeColors.scaled_font("Consolas", 11), tags="text")
                self._text_ids.append(tid)
            y += self._line_height

        # ★ 更新自动滚动标志：如果可见区域包含最后一行则恢复自动追底
        if end_idx >= total:
            self._auto_scroll = True

        # 滚动条指示
        if total > max_visible:
            self._draw_scroll_indicator(total, max_visible)
        else:
            self._canvas.delete("scrollbar")

    def _apply_bg_fragment(self):
        """把背景图片片段绘制到内部 canvas 上。"""
        try:
            from .app import BackgroundManager
            BackgroundManager.make_canvas_transparent(self._canvas)
        except Exception:
            pass

    # ===== 滚动控制 =====

    def _scroll_to_bottom(self):
        """滚动到底部。"""
        ch = self._canvas.winfo_height()
        max_visible = max(1, (ch - self._pad_y * 2) // self._line_height)
        total = len(self._lines)
        self._visible_start = max(0, total - max_visible)
        self._auto_scroll = True
        self._do_redraw()

    def _scroll(self, delta: int):
        """滚动指定行数。"""
        ch = self._canvas.winfo_height()
        max_visible = max(1, (ch - self._pad_y * 2) // self._line_height)
        total = len(self._lines)
        max_start = max(0, total - max_visible)
        old_start = self._visible_start
        self._visible_start = max(0, min(max_start, self._visible_start + delta))

        # ★ 如果用户向上滚动（delta < 0），关闭自动追底
        if delta < 0 and self._visible_start < max_start:
            self._auto_scroll = False
        # ★ 如果滚动到底部，恢复自动追底
        if self._visible_start >= max_start:
            self._auto_scroll = True

        if self._visible_start != old_start:
            self._do_redraw()

    def _scroll_key(self, direction: int):
        """键盘 ↑↓ 滚动 1 行"""
        self._scroll(direction)

    def _scroll_page(self, direction: int):
        """键盘 PageUp/PageDown 滚动一页"""
        ch = self._canvas.winfo_height()
        max_visible = max(1, (ch - self._pad_y * 2) // self._line_height)
        self._scroll(direction * max(1, max_visible - 2))

    def _scroll_home(self):
        """键盘 Home 滚动到顶部"""
        self._visible_start = 0
        self._auto_scroll = False
        self._do_redraw()

    def _scroll_end(self):
        """键盘 End 滚动到底部"""
        self._scroll_to_bottom()

    # ===== 事件处理 =====

    def _on_canvas_click_focus(self, event):
        """点击 canvas 时获取焦点（启用键盘滚动）。"""
        self._canvas.focus_set()

        # ★ 检测是否点击了滚动条区域，是则跳转
        cw = self._canvas.winfo_width()
        bar_x = cw - 8  # 滚动条区域
        if event.x >= bar_x:
            self._on_scrollbar_click(event)

    def _on_mousewheel(self, event):
        """鼠标滚轮滚动 — 统一处理 Windows 和 Linux 事件。"""
        # Windows / macOS: event.delta (正=向上, 负=向下)
        # Linux: event.num (4=向上, 5=向下)
        if hasattr(event, 'num') and event.num == 4:
            self._scroll(-3)
        elif hasattr(event, 'num') and event.num == 5:
            self._scroll(3)
        elif hasattr(event, 'delta'):
            # Windows: delta 通常是 ±120 的整数倍
            # macOS: delta 可能是任意值
            lines = int(event.delta / 40)  # ~3 行每格
            self._scroll(-lines if lines != 0 else (-1 if event.delta > 0 else 1))

    def _on_resize(self, event=None):
        """容器大小变化时重绘（防抖80ms，避免瞬间几十次Configure卡死UI）。"""
        if event and event.widget is not self:
            return  # 忽略子 widget 的 Configure 事件
        if hasattr(self, '_resize_after'):
            self.after_cancel(self._resize_after)
        self._resize_after = self.after(80, self._redraw)

    # ===== 滚动条 =====

    def _draw_scroll_indicator(self, total: int, visible: int):
        """绘制滚动条指示器。"""
        cw = self._canvas.winfo_width()
        ch = self._canvas.winfo_height()
        if ch < 20:
            return
        bar_w = 4
        bar_x = cw - bar_w - 4
        bar_h = max(20, int(ch * visible / total))
        max_scroll = max(1, total - visible)
        bar_y = int((ch - bar_h) * self._visible_start / max_scroll)
        self._canvas.delete("scrollbar")
        # 滚动条轨道
        self._canvas.create_rectangle(
            bar_x - 1, 0, bar_x + bar_w + 1, ch,
            fill=ThemeColors.get("scrollbar_track"), outline="",
            tags=("scrollbar", "scrollbar_track"))
        # 滚动条滑块
        self._canvas.create_rectangle(
            bar_x, bar_y, bar_x + bar_w, bar_y + bar_h,
            fill=ThemeColors.get("scrollbar"), outline="",
            tags=("scrollbar", "scrollbar_thumb"))

    def _on_scrollbar_click(self, event):
        """点击滚动条轨道 → 跳转到对应位置。"""
        cw = self._canvas.winfo_width()
        ch = self._canvas.winfo_height()
        if ch < 20:
            return

        total = len(self._lines)
        visible = max(1, (ch - self._pad_y * 2) // self._line_height)
        if total <= visible:
            return

        # 按点击位置比例计算目标行
        ratio = event.y / ch
        max_start = total - visible
        self._visible_start = int(ratio * max_start)
        self._visible_start = max(0, min(max_start, self._visible_start))

        # 点击底部区域恢复自动滚动
        if ratio > 0.85:
            self._auto_scroll = True
            self._visible_start = max_start
        else:
            self._auto_scroll = False

        self._do_redraw()
        self._scrollbar_dragging = True

    def _on_scrollbar_drag(self, event):
        """拖拽滚动条滑块。"""
        if not self._scrollbar_dragging:
            return
        cw = self._canvas.winfo_width()
        ch = self._canvas.winfo_height()
        if ch < 20:
            return

        total = len(self._lines)
        visible = max(1, (ch - self._pad_y * 2) // self._line_height)
        if total <= visible:
            return

        ratio = event.y / ch
        max_start = total - visible
        self._visible_start = int(ratio * max_start)
        self._visible_start = max(0, min(max_start, self._visible_start))

        if self._visible_start >= max_start:
            self._auto_scroll = True
        else:
            self._auto_scroll = False

        self._do_redraw()

        # 释放鼠标时停止拖拽
        def _stop_drag(e):
            self._scrollbar_dragging = False
        self._canvas.bind("<ButtonRelease-1>", _stop_drag, add="+")


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
        self._stream_var = False  # 流式模式开关
        self._stream_handle = None  # 流式命令句柄

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
            text_color=ThemeColors.get("terminal_prompt"),
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
        self._entry.bind("<Control-c>", self._on_ctrl_c)  # ★ Ctrl+C 中止流式命令

        # ★ 输入框滚轮事件转发到输出区
        self._entry.bind("<MouseWheel>", self._forward_wheel)
        self._entry.bind("<Button-4>", self._forward_wheel)
        self._entry.bind("<Button-5>", self._forward_wheel)

        # 流式输出切换开关
        self._stream_toggle_var = ctk.BooleanVar(value=False)
        self._stream_toggle = ctk.CTkSwitch(
            input_frame,
            text="流式",
            variable=self._stream_toggle_var,
            width=50,
            font=ctk.CTkFont(size=11),
            border_width=1,
            switch_width=32,
            switch_height=16,
            fg_color="#555555",
            progress_color="#2B5B2B",
            command=self._on_toggle_stream,
        )
        self._stream_toggle.grid(row=0, column=2, padx=(0, 4), pady=6)

        # 发送/停止按钮
        self._send_btn = ctk.CTkButton(
            input_frame,
            text="▶",
            width=36,
            height=28,
            font=ctk.CTkFont(size=14),
            command=self._on_send,
            fg_color="#2B5B2B",
            hover_color="#3A7A3A",
        )
        self._send_btn.grid(row=0, column=3, padx=(0, 8), pady=6)

    def _forward_wheel(self, event):
        """将输入框上的滚轮事件转发到输出区。"""
        self._output._on_mousewheel(event)

    def _print_banner(self):
        """欢迎横幅"""
        banner = f"""╔══════════════════════════════════════════════╗
║  🥧 PiManager Terminal — {self._session.name: <28}║
║  树莓派 Zero W · 轻量远程命令终端           ║
║  ↑↓ 浏览历史 · 多标签并行操作               ║
║  🖱 滚轮滚动 · 点击滚动条跳转               ║
╚══════════════════════════════════════════════╝
"""
        self._output.insert("end", banner)
        self._output.see("end")

    def _log(self, text: str, tag: str = None):
        """向输出区追加文本"""
        self._output.insert("end", text, tag)
        # ★ 自动追底由 CanvasTerminalOutput 内部的 _auto_scroll 控制

    def _on_send(self, event=None):
        """发送命令（或停止流式命令）"""
        cmd = self._entry.get().strip()

        # ★ 如果流式命令正在运行，先中止它
        if self._running and self._stream_var and self._stream_handle:
            self._stop_streaming()
            if not cmd:  # 空输入 = 仅中止
                return
            # 否则继续执行新命令

        self._entry.delete(0, "end")
        self._session.reset_history_index()

        if not cmd:
            return

        self._session.add_history(cmd)

        if cmd.lower() in ("clear", "cls"):
            self._output.delete("1.0", "end")  # CanvasTerminalOutput ignores args
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

        if self._stream_var:
            self._exec_streaming(cmd)
        else:
            self._exec_blocking(cmd)

    def _exec_blocking(self, cmd):
        """阻塞式命令执行（原有逻辑）"""

        def _exec():
            try:
                code, out, err = self._ssh.exec_command(cmd, timeout=120)
                self.frame.after(0, lambda: self._on_result(out, err, cmd))
            except Exception as e:
                self.frame.after(0, lambda: self._on_result("", str(e), cmd))

        threading.Thread(target=_exec, daemon=True).start()

    def _exec_streaming(self, cmd):
        """流式命令执行 — 输出实时推送到终端"""
        self._stream_handle = None
        self._send_btn.configure(text="⏹", fg_color="#8B0000", hover_color="#A00000")
        self._stream_toggle.configure(state="disabled")

        def on_stdout(line):
            self.frame.after(0, lambda l=line: self._log(l))

        def on_stderr(line):
            self.frame.after(0, lambda l=line: self._log(l, "stderr"))

        def on_done(exit_code, error):
            self.frame.after(0, lambda: self._on_streaming_done(exit_code, error, cmd))

        self._stream_handle = self._ssh.exec_command_streaming(
            cmd, on_stdout=on_stdout, on_stderr=on_stderr, on_done=on_done)

    def _stop_streaming(self):
        """中止正在运行的流式命令 — 先发 Ctrl+C 优雅终止，1.5s 后不响应则强制关闭"""
        if self._stream_handle:
            self._stream_handle.send_ctrl_c()  # 发送 \x03 (SIGINT) 到 PTY
            # 如果进程在 1.5s 内未退出，强制关闭通道
            self.frame.after(1500, self._force_cancel_if_running)
        self._log("\n⏹ Ctrl+C (SIGINT) 已发送...\n", "stderr")

    def _force_cancel_if_running(self):
        """Ctrl+C 宽限期过后，进程仍未退出则强制关闭通道"""
        if self._stream_handle and self._stream_handle.is_running:
            self._stream_handle.cancel()
            self._log("⚠ 进程未响应 SIGINT，已强制关闭通道\n", "stderr")
            self._finish_streaming()

    def _on_ctrl_c(self, event=None):
        """Ctrl+C 键盘快捷键 — 中止流式命令"""
        if self._running and self._stream_handle:
            self._stop_streaming()
            return "break"  # 中止时阻止默认复制行为
        # 没有流式命令在跑时不拦截，保留 tkinter 默认 Ctrl+C 复制功能

    def _on_streaming_done(self, exit_code, error, cmd):
        """流式命令完成回调"""
        if error:
            self._log(f"\n❌ 错误: {error}\n", "stderr")
        elif exit_code != 0:
            self._log(f"\n📋 退出码: {exit_code}\n")
        else:
            self._log(f"\n✅ 完成 (退出码 {exit_code})\n")
        self._finish_streaming()

    def _finish_streaming(self):
        """恢复 UI 状态（流式命令结束后）"""
        self._running = False
        self._stream_handle = None
        self._send_btn.configure(text="▶", fg_color="#2B5B2B", hover_color="#3A7A3A")
        self._stream_toggle.configure(state="normal")
        self._entry.configure(state="normal", placeholder_text="输入命令...")
        self._entry.focus_set()
        if hasattr(self._app, '_status_label'):
            self._app._status_label.configure(text="就绪")

    def _on_toggle_stream(self):
        """流式开关切换"""
        self._stream_var = self._stream_toggle_var.get()

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
        """快捷命令按钮栏（每行最多 5 个，动态分行）"""
        quick_card = self._make_card("⚡ 快捷命令", 0)

        cmds_per_row = 5
        for i in range(0, len(QUICK_COMMANDS), cmds_per_row):
            row_frame = ctk.CTkFrame(quick_card, fg_color="transparent", corner_radius=0)
            row_frame.pack(fill="x", padx=0, pady=2)

            for text, cmd in QUICK_COMMANDS[i:i + cmds_per_row]:
                btn = ctk.CTkButton(
                    row_frame,
                    text=text,
                    width=80,
                    height=28,
                    font=ctk.CTkFont(size=11),
                    fg_color=ThemeColors.get("canvas_quick_btn"),
                    hover_color=ThemeColors.get("canvas_quick_btn_hover"),
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
