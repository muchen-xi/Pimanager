"""
PiManager 主应用窗口 (v2: tkinter + Pillow)
"""
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
import threading
import os
import logging
import datetime
from pathlib import Path

from .config import load_config, save_config
from .ssh_client import SSHClient
from .theme import ThemeColors
from .pillui import PageCanvas, PillowButton, PillowLabel, PillowProgressBar, PillowCard

# 延迟导入页面（避免循环依赖）
# StatusPanel, FileBrowser, TerminalPage, SettingsPage 在 _build_pages 中导入


# ============================================================
#  BackgroundManager (v2: 极简版)
# ============================================================

class BackgroundManager:
    """全局背景管理 — 加载图片 + 与暗色混合 → Canvas 背景。"""

    _blended: Image.Image = None
    _opacity: float = 0.15
    _path: str = ""
    _canvases: list = []  # PageCanvas 或 tk.Canvas
    _tk_images: dict = {}  # id → PhotoImage (防回收)

    @classmethod
    def register(cls, canvas):
        """注册一个 canvas（PageCanvas 或 tk.Canvas）。"""
        if canvas not in cls._canvases:
            cls._canvases.append(canvas)

    @classmethod
    def unregister(cls, canvas):
        if canvas in cls._canvases:
            cls._canvases.remove(canvas)
            cls._tk_images.pop(id(canvas), None)

    @classmethod
    def set_background(cls, path: str, opacity: float):
        """设置背景图片。"""
        cls._path = path
        cls._opacity = float(opacity)
        if path and os.path.exists(path):
            try:
                bg = Image.open(path)
                bg.verify()
                bg = Image.open(path).convert("RGBA")
                dark = Image.new("RGBA", bg.size, (13, 17, 23, 255))
                cls._blended = Image.blend(
                    dark.convert("RGB"), bg.convert("RGB"), cls._opacity
                )
            except Exception as e:
                logging.warning(f"背景加载失败: {e}")
                cls._blended = None
        else:
            cls._blended = None
        cls._tk_images.clear()
        cls._refresh()

    @classmethod
    def clear(cls):
        cls._path = ""
        cls._blended = None
        cls._tk_images.clear()
        cls._refresh()

    @classmethod
    def get_blended(cls, size: tuple = None) -> Image.Image:
        """返回混合后的背景图。"""
        if cls._blended is None:
            return None
        if size:
            return cls._blended.resize(size, Image.LANCZOS)
        return cls._blended

    @classmethod
    def apply_to_canvas(cls, canvas):
        """将混合背景绘制到原始 tk.Canvas（供文件列表/终端调用）。"""
        if cls._blended is None:
            return
        try:
            cw = canvas.winfo_width()
            ch = canvas.winfo_height()
            if cw < 20 or ch < 20:
                return
            img = cls._blended.resize((cw, ch), Image.LANCZOS)
            tk_img = ImageTk.PhotoImage(img)
            cls._tk_images[id(canvas)] = tk_img
            canvas.delete("bg_image")
            canvas.create_image(0, 0, anchor="nw", image=tk_img, tags="bg_image")
            canvas.tag_lower("bg_image")
        except Exception:
            pass

    @classmethod
    def _refresh(cls):
        for c in cls._canvases:
            try:
                if hasattr(c, 'set_bg_image') and hasattr(c, 'render'):
                    # PageCanvas
                    if cls._blended:
                        c.set_bg_image(cls._blended)
                    else:
                        c.set_bg_color(ThemeColors.get("bg"))
                    c.render()
                else:
                    # 原始 tk.Canvas
                    c.delete("bg_image")
                    if cls._blended:
                        cls.apply_to_canvas(c)
            except Exception:
                pass


# ============================================================
#  PiManagerApp
# ============================================================

class PiManagerApp(tk.Tk):
    """PiManager 主应用 (v2: tkinter + Pillow 渲染)"""

    SIDEBAR_W = 240

    def __init__(self):
        super().__init__()

        self._setup_logging()

        self._config = load_config()
        self._ssh = SSHClient()
        self._connect_time = None

        # 窗口设置
        self.title("PiManager - 树莓派管理器")
        self.geometry("1100x700")
        self.minsize(900, 600)
        self.configure(bg=ThemeColors.get("bg"))
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # 图标
        icon_path = Path(__file__).parent / "assets" / "icon.ico"
        if icon_path.exists():
            try:
                self.iconbitmap(str(icon_path))
            except Exception:
                pass

        # 网格布局
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ===== 侧边栏 =====
        self._sidebar_frame = tk.Frame(self, width=self.SIDEBAR_W,
                                        bg=ThemeColors.get("bg"))
        self._sidebar_frame.grid(row=0, column=0, sticky="ns", rowspan=2)
        self._sidebar_frame.grid_propagate(False)

        self._sidebar = PageCanvas(
            self._sidebar_frame,
            width=self.SIDEBAR_W, height=700,
            bg=ThemeColors.get("bg")
        )
        self._sidebar.pack(fill="both", expand=True)
        # 侧边栏不用背景图，保持纯色
        self._build_sidebar()

        # ===== 主内容区 =====
        self._content = tk.Frame(self, bg=ThemeColors.get("bg"))
        self._content.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self._content.grid_columnconfigure(0, weight=1)
        self._content.grid_rowconfigure(0, weight=1)

        # ===== 页面容器 =====
        self._pages = {}
        self._current_page = None
        self._build_pages()

        # ===== 状态栏 =====
        self._build_status_bar()

        # 显示首页
        self._show_page("status")

        # 应用背景
        self.after(500, self._apply_background)
        self.bind("<Configure>", self._on_window_resize)

        # 自动连接
        if self._config.get("behavior", {}).get("auto_connect", False):
            self.after(500, self._auto_connect)

        # 状态栏时钟
        self._update_status_clock()

    # ============================================================
    #  日志
    # ============================================================

    def _setup_logging(self):
        log_path = Path(__file__).parent / "pimanager.log"
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            handlers=[
                logging.FileHandler(str(log_path), encoding='utf-8'),
                logging.StreamHandler()
            ]
        )

    # ============================================================
    #  侧边栏构建
    # ============================================================

    def _build_sidebar(self):
        """构建侧边栏 — 全部 Pillow 组件。"""
        W = self.SIDEBAR_W

        # ---- Logo / 标题 ----
        self._sidebar.add("logo",
            PillowLabel("🥧", 0, 18, W, 36,
                        font_size=32, align="center"))
        self._sidebar.add("logo_text",
            PillowLabel("PiManager", 0, 52, W, 24,
                        font_size=16, color="#4CAF50",
                        weight="bold", align="center"))

        # ---- 连接状态 ----
        self._sidebar.add("status_card",
            PillowCard(15, 85, W - 30, 52,
                       fill="#161B22", border="gray30", radius=8))
        self._conn_label = PillowLabel("🔴 未连接", 25, 95, W - 50, 22,
                                       font_size=12)
        self._sidebar.add("conn_status", self._conn_label)
        self._conn_host_label = PillowLabel("", 25, 116, W - 50, 18,
                                            font_size=10, color="#8B949E")
        self._sidebar.add("conn_host", self._conn_host_label)

        # ---- 连接按钮 ----
        self._connect_btn = PillowButton("🔌 连接", 15, 150, W - 30, 34,
                                        command=self._toggle_connection,
                                        font_size=12)
        self._sidebar.add("btn_connect", self._connect_btn)
        self._sidebar.add("btn_settings_conn",
            PillowButton("⚙️ 连接设置", 15, 190, W - 30, 30,
                         command=self._show_conn_settings,
                         style="transparent", font_size=11))

        # ---- 分隔线（用透明组件标记位置，实际在渲染中只是一行文字分隔）----
        # ---- 我们不画分隔线卡片，在重绘时由背景自然分隔 ----

        # ---- 系统状态卡片（初始隐藏）----
        self._sys_card = PillowCard(15, 232, W - 30, 160,
                                     title="📡 实时状态",
                                     fill="#161B22", border="gray30", radius=8)
        self._sys_card.visible = False
        self._sidebar.add("sys_card", self._sys_card)

        # CPU
        self._sidebar_cpu_bar = PillowProgressBar(70, 260, 90, 8)
        self._sidebar.add("sidebar_cpu_bar", self._sidebar_cpu_bar)
        self._sidebar_cpu_bar.visible = False
        self._sidebar.add("sidebar_cpu_label",
            PillowLabel("🔥 CPU", 20, 256, 48, 16, font_size=10, color="#8B949E"))
        self._sidebar_cpu_pct = PillowLabel("--", 165, 256, 48, 16,
                                            font_size=10, color="#C9D1D9", align="right")
        self._sidebar.add("sidebar_cpu_pct", self._sidebar_cpu_pct)
        self._sidebar_cpu_pct.visible = False

        # RAM
        self._sidebar_ram_bar = PillowProgressBar(70, 286, 90, 8)
        self._sidebar.add("sidebar_ram_bar", self._sidebar_ram_bar)
        self._sidebar_ram_bar.visible = False
        self._sidebar.add("sidebar_ram_label",
            PillowLabel("🧠 RAM", 20, 282, 48, 16, font_size=10, color="#8B949E"))
        self._sidebar_ram_pct = PillowLabel("--", 165, 282, 48, 16,
                                            font_size=10, color="#C9D1D9", align="right")
        self._sidebar.add("sidebar_ram_pct", self._sidebar_ram_pct)
        self._sidebar_ram_pct.visible = False

        # IP
        self._sidebar_ip = PillowLabel("🌐 --", 20, 310, W - 40, 16,
                                       font_size=10, color="#8B949E")
        self._sidebar.add("sidebar_ip", self._sidebar_ip)
        self._sidebar_ip.visible = False

        # Temp
        self._sidebar_temp = PillowLabel("🌡️ --°C", 20, 334, W - 40, 18,
                                         font_size=13, weight="bold", color="#4CAF50")
        self._sidebar.add("sidebar_temp", self._sidebar_temp)
        self._sidebar_temp.visible = False

        # ---- 导航按钮 ----
        self._nav_buttons = {}
        nav_items = [
            ("📊  系统状态", "status"),
            ("📁  文件管理", "files"),
            ("💻  命令终端", "terminal"),
            ("⚙️  应用设置", "settings"),
        ]
        for i, (text, page_id) in enumerate(nav_items):
            btn = PillowButton(text, 15, 400 + i * 44, W - 30, 36,
                              command=lambda p=page_id: self._show_page(p),
                              style="transparent", font_size=12)
            self._sidebar.add(f"nav_{page_id}", btn)
            self._nav_buttons[page_id] = btn

        # ---- 电源按钮 ----
        self._reboot_btn = PillowButton("🔄 重启", 15, 580, (W - 36) // 2, 30,
                                        command=self._reboot_pi,
                                        style="transparent", font_size=11,
                                        disabled=True)
        self._sidebar.add("btn_reboot", self._reboot_btn)
        self._shutdown_btn = PillowButton("⏻ 关机", 15 + (W - 36) // 2 + 6, 580,
                                          (W - 36) // 2, 30,
                                          command=self._shutdown_pi,
                                          style="danger", font_size=11,
                                          disabled=True)
        self._sidebar.add("btn_shutdown", self._shutdown_btn)

        # ---- 版本 ----
        self._sidebar.add("version",
            PillowLabel("v2.0.0", 0, 640, W, 20,
                        font_size=10, color="gray", align="center"))

        self._sidebar.render()

    def _highlight_nav(self, page_id: str):
        """高亮当前导航按钮。"""
        for pid, btn in self._nav_buttons.items():
            if pid == page_id:
                btn.set_style("primary")
            else:
                btn.set_style("transparent")

    # ============================================================
    #  状态栏
    # ============================================================

    def _build_status_bar(self):
        """底部状态栏 — 用 tk.Frame + Label（简单，不需要 Pillow 渲染）。"""
        self._status_bar = tk.Frame(self, height=28, bg=ThemeColors.get("bg_card"))
        self._status_bar.grid(row=1, column=1, sticky="ew")
        self._status_bar.grid_propagate(False)
        self._status_bar.grid_columnconfigure(1, weight=1)

        self._status_label = tk.Label(
            self._status_bar, text="就绪", anchor="w",
            bg=ThemeColors.get("bg_card"), fg=ThemeColors.get("text"),
            font=("Segoe UI", 10))
        self._status_label.grid(row=0, column=0, padx=(10, 5), sticky="w")

        self._status_duration = tk.Label(
            self._status_bar, text="", anchor="w",
            bg=ThemeColors.get("bg_card"), fg=ThemeColors.get("text_secondary"),
            font=("Segoe UI", 9))
        self._status_duration.grid(row=0, column=1, padx=5, sticky="w")

        self._status_clock = tk.Label(
            self._status_bar, text="", anchor="e",
            bg=ThemeColors.get("bg_card"), fg=ThemeColors.get("text_secondary"),
            font=("Segoe UI", 10))
        self._status_clock.grid(row=0, column=2, padx=10, sticky="e")

    def _update_status_clock(self):
        """更新状态栏时钟。"""
        now = datetime.datetime.now()
        self._status_clock.configure(text=now.strftime("%Y-%m-%d %H:%M"))

        if self._ssh.connected and self._connect_time:
            delta = now - self._connect_time
            hours, rem = divmod(int(delta.total_seconds()), 3600)
            mins, secs = divmod(rem, 60)
            if hours > 0:
                dur_text = f"已连接 {hours}时{mins}分"
            else:
                dur_text = f"已连接 {mins}分{secs}秒"
            self._status_duration.configure(text=dur_text)

        self._status_clock_job = self.after(30000, self._update_status_clock)

    def _update_status_bar_theme(self):
        """主题切换时更新状态栏颜色。"""
        bg = ThemeColors.get("bg_card")
        fg = ThemeColors.get("text")
        fg2 = ThemeColors.get("text_secondary")
        self._status_bar.configure(bg=bg)
        self._status_label.configure(bg=bg, fg=fg)
        self._status_duration.configure(bg=bg, fg=fg2)
        self._status_clock.configure(bg=bg, fg=fg2)

    # ============================================================
    #  页面管理
    # ============================================================

    def _build_pages(self):
        """构建所有页面 — 延迟导入避免循环依赖。"""
        from .status_panel import StatusPanel
        from .file_browser import FileBrowser
        from .terminal_page import TerminalPage
        from .settings_page import SettingsPage

        self._status_panel = StatusPanel(self._content, self._ssh, self._config)
        self._pages["status"] = self._status_panel

        self._file_browser = FileBrowser(self._content, self._ssh, self._config,
                                         app_ref=self)
        self._pages["files"] = self._file_browser

        self._terminal_page = TerminalPage(self._content, self._ssh, self._config,
                                           app_ref=self)
        self._pages["terminal"] = self._terminal_page

        self._settings_page = SettingsPage(self._content, self._config,
                                           self._ssh, app_ref=self)
        self._pages["settings"] = self._settings_page

    def _show_page(self, page_id: str):
        """切换页面。"""
        if self._current_page == page_id:
            return
        self._current_page = page_id
        self._highlight_nav(page_id)

        for page in self._pages.values():
            page.grid_remove()

        page = self._pages[page_id]
        page.grid(row=0, column=0, sticky="nsew")

        if page_id == "status" and self._ssh.connected:
            self._status_panel.refresh()
        elif page_id == "files" and self._ssh.connected:
            self._file_browser.refresh()

    # ============================================================
    #  背景管理
    # ============================================================

    def _on_window_resize(self, event=None):
        """窗口 resize 防抖。"""
        # 由各 PageCanvas 自行处理 resize
        pass

    def _apply_background(self, force=False):
        """应用背景图片。"""
        bg_path = self._config["appearance"].get("background_path", "")
        opacity = self._config["appearance"].get("background_opacity", 0.15)
        BackgroundManager.set_background(bg_path, float(opacity))

    def refresh_all_canvases(self):
        """主题/字体变更后刷新所有页面。"""
        # 更新侧边栏颜色
        self._sidebar.set_bg_color(ThemeColors.get("bg"))
        self._sidebar.render()
        # 更新状态栏
        self._update_status_bar_theme()
        # 更新内容区背景
        self._content.configure(bg=ThemeColors.get("bg"))
        # 触发各页面刷新（子类覆盖 refresh_theme）
        for page in self._pages.values():
            if hasattr(page, 'refresh_theme'):
                page.refresh_theme()

    # ============================================================
    #  连接管理（逻辑不变，只改 UI 更新方式）
    # ============================================================

    def _auto_connect(self):
        conn = self._config.get("connections", [{}])[0]
        if not conn or not conn.get("host"):
            return
        self._do_connect(
            conn.get("host", ""), conn.get("port", 22),
            conn.get("username", "pi"),
            conn.get("key_path", ""),
            conn.get("password", ""),
            conn.get("use_key", True),
        )

    def _toggle_connection(self):
        if self._ssh.connected:
            self._ssh.disconnect()
            self._on_disconnected()
        else:
            conn = self._config.get("connections", [{}])[0]
            if not conn or not conn.get("host"):
                self._show_conn_settings()
                return
            self._do_connect(
                conn.get("host", ""), conn.get("port", 22),
                conn.get("username", "pi"),
                conn.get("key_path", ""),
                conn.get("password", ""),
                conn.get("use_key", True),
            )

    def _do_connect(self, host, port, username, key_path, password, use_key):
        self._status_label.configure(text=f"正在连接 {host}...")
        self._connect_btn.set_text("⏳ 连接中...")
        self._connect_btn.set_disabled(True)

        def _connect():
            kp = key_path if use_key and key_path else None
            pw = password if not use_key else None
            ok, msg = self._ssh.connect(host, port, username, kp, pw)
            self.after(0, lambda: self._on_connect_result(ok, msg))

        threading.Thread(target=_connect, daemon=True).start()

    def _on_connect_result(self, ok: bool, msg: str):
        if ok:
            self._connect_time = datetime.datetime.now()
            self._conn_label.set_text("🟢 已连接")
            self._conn_label.set_color("#4CAF50")
            self._conn_host_label.set_text(f"{self._ssh.host}")
            self._connect_btn.set_text("🔌 断开")
            self._connect_btn.set_style("danger")
            self._connect_btn.set_disabled(False)
            self._status_label.configure(text="已连接")

            # 显示系统状态卡片
            self._sys_card.visible = True
            self._sidebar_cpu_bar.visible = True
            self._sidebar_cpu_pct.visible = True
            self._sidebar_ram_bar.visible = True
            self._sidebar_ram_pct.visible = True
            self._sidebar_ip.visible = True
            self._sidebar_temp.visible = True
            self._sidebar.render()

            self._reboot_btn.set_disabled(False)
            self._shutdown_btn.set_disabled(False)
            self._refresh_sidebar_stats()
            self._start_sidebar_refresh()

            if self._current_page == "status":
                self._status_panel.refresh()
                self._status_panel.start_auto_refresh()
            elif self._current_page == "files":
                self._file_browser.refresh()
            logging.info(f"已连接到 {self._ssh.host}")
        else:
            self._connect_time = None
            self._conn_label.set_text("🔴 连接失败")
            self._conn_label.set_color("#FF6B6B")
            self._conn_host_label.set_text(msg)
            self._connect_btn.set_text("🔌 连接")
            self._connect_btn.set_style("primary")
            self._connect_btn.set_disabled(False)
            self._status_label.configure(text="连接失败")
            logging.warning(f"连接失败: {msg}")
            messagebox.showerror("连接失败", msg)

    def _on_disconnected(self):
        self._connect_time = None
        self._status_duration.configure(text="")
        self._conn_label.set_text("🔴 未连接")
        self._conn_label.set_color("#8B949E")
        self._conn_host_label.set_text("")
        self._connect_btn.set_text("🔌 连接")
        self._connect_btn.set_style("primary")
        self._status_label.configure(text="已断开")

        self._sys_card.visible = False
        self._sidebar_cpu_bar.visible = False
        self._sidebar_cpu_pct.visible = False
        self._sidebar_ram_bar.visible = False
        self._sidebar_ram_pct.visible = False
        self._sidebar_ip.visible = False
        self._sidebar_temp.visible = False
        self._sidebar.render()

        self._reboot_btn.set_disabled(True)
        self._shutdown_btn.set_disabled(True)
        self._stop_sidebar_refresh()

        if self._current_page == "status":
            self._status_panel.stop_auto_refresh()
        logging.info("已断开连接")

    # ============================================================
    #  侧边栏系统状态刷新
    # ============================================================

    def _refresh_sidebar_stats(self):
        """刷新侧边栏 CPU/RAM/IP/温度。"""
        if not self._ssh.connected:
            return

        def _fetch():
            try:
                s = self._ssh.get_sidebar_stats()
                self.after(0, lambda: self._update_sidebar_ui(
                    s["cpu"], s["mem_pct"], s["mem_used"],
                    s["mem_total"], s["ip"], s["temp"]))
            except Exception:
                pass

        threading.Thread(target=_fetch, daemon=True).start()

    def _update_sidebar_ui(self, cpu, mem_pct, mem_used, mem_total, ip_addr, temp):
        """更新侧边栏 UI — Pillow 组件。"""
        ok, warn, danger = (ThemeColors.get(k) for k in
                            ("status_ok", "warning", "warning_strong"))

        self._sidebar_cpu_bar.set(cpu / 100)
        self._sidebar_cpu_pct.set_text(f"{cpu:.0f}%")
        cpu_c = ok if cpu < 50 else (warn if cpu < 80 else danger)
        self._sidebar_cpu_bar.set_color(cpu_c)

        self._sidebar_ram_bar.set(mem_pct / 100)
        self._sidebar_ram_pct.set_text(f"{mem_pct:.0f}%")
        ram_c = ok if mem_pct < 50 else (warn if mem_pct < 80 else danger)
        self._sidebar_ram_bar.set_color(ram_c)

        self._sidebar_ip.set_text(f"🌐 {ip_addr}")

        t_color = ok if temp < 50 else (warn if temp < 70 else danger)
        self._sidebar_temp.set_text(f"🌡️ {temp:.1f}°C")
        self._sidebar_temp.set_color(t_color)

    def _start_sidebar_refresh(self):
        self._stop_sidebar_refresh()
        self._do_sidebar_refresh()

    def _do_sidebar_refresh(self):
        if self._ssh.connected:
            self._refresh_sidebar_stats()
        self._sidebar_refresh_job = self.after(3000, self._do_sidebar_refresh)

    def _stop_sidebar_refresh(self):
        if hasattr(self, '_sidebar_refresh_job') and self._sidebar_refresh_job:
            self.after_cancel(self._sidebar_refresh_job)
            self._sidebar_refresh_job = None

    # ============================================================
    #  电源控制（逻辑不变）
    # ============================================================

    def _shutdown_pi(self):
        if not self._ssh.connected:
            return
        if not messagebox.askyesno("⚠️ 确认关机",
            "确定要关闭树莓派吗？\n\n关机后需手动重新上电才能启动。", icon="warning"):
            return
        def _do():
            self._ssh.exec_command("sudo shutdown -h now", timeout=5)
        threading.Thread(target=_do, daemon=True).start()
        self._status_label.configure(text="已发送关机命令")
        logging.info("发送关机命令")
        messagebox.showinfo("已发送", "关机命令已发送，树莓派即将关闭")

    def _reboot_pi(self):
        if not self._ssh.connected:
            return
        if not messagebox.askyesno("⚠️ 确认重启",
            "确定要重启树莓派吗？\n\n重启期间连接将断开，约 30 秒后可重新连接。", icon="warning"):
            return
        def _do():
            self._ssh.exec_command("sudo shutdown -r now", timeout=5)
        threading.Thread(target=_do, daemon=True).start()
        self._status_label.configure(text="已发送重启命令")
        logging.info("发送重启命令")
        messagebox.showinfo("已发送", "重启命令已发送，树莓派即将重启")

    # ============================================================
    #  连接设置对话框
    # ============================================================

    def _show_conn_settings(self):
        """连接设置对话框 — 使用 tk.Toplevel。"""
        dialog = tk.Toplevel(self)
        dialog.title("连接设置")
        dialog.geometry("450x380")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()
        dialog.configure(bg=ThemeColors.get("bg"))

        conn = self._config.get("connections", [{}])[0] if self._config.get("connections") else {}

        content = tk.Frame(dialog, bg=ThemeColors.get("bg"))
        content.pack(fill="both", expand=True, padx=20, pady=20)

        fields = [
            ("连接名称:", "name", conn.get("name", "树莓派")),
            ("主机地址:", "host", conn.get("host", "muchenxi-20081128.local")),
            ("端口:", "port", str(conn.get("port", 22))),
            ("用户名:", "username", conn.get("username", "chenxi")),
        ]

        entries = {}
        for i, (label, key, default) in enumerate(fields):
            tk.Label(content, text=label, anchor="w",
                    bg=ThemeColors.get("bg"), fg=ThemeColors.get("text")).grid(
                row=i, column=0, sticky="w", pady=6, padx=(0, 10))
            entry = tk.Entry(content, width=30,
                            bg=ThemeColors.get("bg_card"),
                            fg=ThemeColors.get("text"),
                            insertbackground=ThemeColors.get("text"),
                            relief="flat", bd=1)
            entry.grid(row=i, column=1, sticky="ew", pady=6)
            entry.insert(0, default)
            entries[key] = entry
            content.grid_columnconfigure(1, weight=1)

        # 密钥路径
        tk.Label(content, text="密钥路径:", anchor="w",
                bg=ThemeColors.get("bg"), fg=ThemeColors.get("text")).grid(
            row=4, column=0, sticky="w", pady=6, padx=(0, 10))
        key_frame = tk.Frame(content, bg=ThemeColors.get("bg"))
        key_frame.grid(row=4, column=1, sticky="ew", pady=6)
        key_frame.grid_columnconfigure(0, weight=1)
        key_entry = tk.Entry(key_frame,
                            bg=ThemeColors.get("bg_card"),
                            fg=ThemeColors.get("text"),
                            insertbackground=ThemeColors.get("text"),
                            relief="flat", bd=1)
        key_entry.grid(row=0, column=0, sticky="ew")
        key_entry.insert(0, conn.get("key_path", ""))
        entries["key_path"] = key_entry
        tk.Button(key_frame, text="📂", width=4, height=1,
                 command=lambda: self._browse_key(key_entry)).grid(
            row=0, column=1, padx=(4, 0))

        btn_frame = tk.Frame(content, bg=ThemeColors.get("bg"))
        btn_frame.grid(row=6, column=0, columnspan=2, pady=10)

        def _save():
            self._config["connections"] = [{
                "name": entries["name"].get(),
                "host": entries["host"].get(),
                "port": int(entries["port"].get() or 22),
                "username": entries["username"].get(),
                "key_path": entries["key_path"].get(),
                "use_key": bool(entries["key_path"].get()),
            }]
            save_config(self._config)
            dialog.destroy()
            messagebox.showinfo("保存成功", "连接设置已保存")

        tk.Button(btn_frame, text="💾 保存并连接",
                 command=lambda: (_save(), self._auto_connect()),
                 bg="#2B5B2B", fg="white", relief="flat", padx=12, pady=4).pack(
            side="left", padx=5)
        tk.Button(btn_frame, text="保存", command=_save,
                 relief="flat", padx=12, pady=4).pack(side="left", padx=5)

    def _browse_key(self, entry):
        path = filedialog.askopenfilename(
            title="选择SSH密钥",
            initialdir=os.path.join(os.path.expanduser("~"), ".ssh"),
            filetypes=[("密钥文件", "id_*"), ("PEM文件", "*.pem"), ("所有文件", "*.*")])
        if path:
            entry.delete(0, "end")
            entry.insert(0, path)

    # ============================================================
    #  关闭
    # ============================================================

    def _on_close(self):
        self._stop_sidebar_refresh()
        if hasattr(self, '_status_clock_job'):
            self.after_cancel(self._status_clock_job)
        if self._current_page == "status":
            self._status_panel.stop_auto_refresh()
        self._ssh.disconnect()
        logging.info("应用关闭")
        self.destroy()
