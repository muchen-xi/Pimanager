"""
PiManager 主应用窗口
"""
import customtkinter as ctk
import threading
import datetime
import os
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk

from .config import load_config, save_config
from .ssh_client import SSHClient
from .status_panel import StatusPanel
from .file_browser import FileBrowser


class PiManagerApp(ctk.CTk):
    """PiManager 主应用"""

    def __init__(self):
        super().__init__()

        # 初始化
        self._config = load_config()
        self._ssh = SSHClient()
        self._resize_after_id = None

        # 窗口设置
        self.title("PiManager - 树莓派管理器")
        self.geometry("1100x700")
        self.minsize(900, 600)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # 图标（如果有）
        icon_path = Path(__file__).parent / "assets" / "icon.ico"
        if icon_path.exists():
            try:
                self.iconbitmap(str(icon_path))
            except Exception:
                pass

        # 布局
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)  # 状态栏

        # ===== 左侧边栏 =====
        self._sidebar = ctk.CTkFrame(self, width=240)
        self._sidebar.grid(row=0, column=0, sticky="ns", rowspan=2)
        self._sidebar.grid_columnconfigure(0, weight=1)
        self._build_sidebar()

        # ===== 主内容区 =====
        self._content = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        self._content.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self._content.grid_columnconfigure(0, weight=1)
        self._content.grid_rowconfigure(0, weight=1)

        # ===== 背景层 =====
        self._bg_image = None
        self._bg_refs = []  # 防 GC，存所有裁剪后的 PhotoImage

        # 等窗口完全就绪后加载背景（足够时间让所有 widget 渲染）
        self.after(1000, self._apply_background)
        self.bind("<Configure>", self._on_window_resize)

        # ===== 页面容器 =====
        self._pages = {}
        self._current_page = None
        self._build_pages()

        # ===== 状态栏 =====
        self._status_bar = ctk.CTkFrame(self, height=28, corner_radius=0)
        self._status_bar.grid(row=1, column=1, sticky="ew", padx=(0, 0))
        self._status_bar.grid(row=1, column=1, sticky="ew", padx=(0, 0))
        self._status_bar.grid_columnconfigure(1, weight=1)
        self._status_label = ctk.CTkLabel(
            self._status_bar, text="就绪", anchor="w", font=ctk.CTkFont(size=11))
        self._status_label.grid(row=0, column=0, padx=10, sticky="w")
        self._status_right = ctk.CTkLabel(
            self._status_bar, text="", anchor="e", font=ctk.CTkFont(size=11), text_color="gray")
        self._status_right.grid(row=0, column=1, padx=10, sticky="e")

        # 显示首页
        self._show_page("status")

        # 自动连接
        if self._config.get("behavior", {}).get("auto_connect", False):
            self.after(500, self._auto_connect)

    # ===== 侧边栏 =====

    def _build_sidebar(self):
        """构建侧边栏"""
        # Logo / 标题
        title_frame = ctk.CTkFrame(self._sidebar)
        title_frame.grid(row=0, column=0, sticky="ew", padx=15, pady=(20, 10))

        ctk.CTkLabel(title_frame, text="🥧", font=ctk.CTkFont(size=36)).pack(pady=(0, 5))
        ctk.CTkLabel(title_frame, text="PiManager",
                     font=ctk.CTkFont(size=18, weight="bold")).pack()

        # 连接状态
        status_frame = ctk.CTkFrame(
            self._sidebar, fg_color=("gray85", "gray17"), corner_radius=8)
        status_frame.grid(row=1, column=0, sticky="ew", padx=15, pady=(5, 10))

        self._conn_indicator = ctk.CTkLabel(
            status_frame, text="🔴 未连接", font=ctk.CTkFont(size=12))
        self._conn_indicator.pack(pady=(8, 2))

        self._conn_host = ctk.CTkLabel(
            status_frame, text="", font=ctk.CTkFont(size=11), text_color="gray")
        self._conn_host.pack(pady=(0, 8))

        # 连接按钮
        btn_frame = ctk.CTkFrame(self._sidebar)
        btn_frame.grid(row=2, column=0, sticky="ew", padx=15, pady=(0, 10))

        self._btn_connect = ctk.CTkButton(
            btn_frame, text="🔌 连接", command=self._toggle_connection,
            height=32, fg_color="#2B5B2B", hover_color="#3A7A3A")
        self._btn_connect.pack(fill="x", pady=2)

        self._btn_settings_conn = ctk.CTkButton(
            btn_frame, text="⚙️ 连接设置", command=self._show_conn_settings,
            height=28, fg_color="transparent", border_width=1,
            border_color=("gray40", "gray30"),
            font=ctk.CTkFont(size=12))
        self._btn_settings_conn.pack(fill="x", pady=2)

        # 分隔线
        ctk.CTkFrame(self._sidebar, height=1, fg_color=("gray70", "gray30")).grid(
            row=3, column=0, sticky="ew", padx=20, pady=5)

        # 导航按钮
        nav_items = [
            ("📊  系统状态", "status"),
            ("📁  文件管理", "files"),
            ("💻  命令终端", "terminal"),
            ("⚙️  应用设置", "settings"),
        ]
        self._nav_buttons = {}
        for i, (text, page_id) in enumerate(nav_items):
            btn = ctk.CTkButton(
                self._sidebar, text=text, anchor="w", height=36,
                fg_color="transparent", hover_color=("gray75", "gray25"),
                font=ctk.CTkFont(size=13),
                command=lambda p=page_id: self._show_page(p))
            btn.grid(row=4 + i, column=0, sticky="ew", padx=15, pady=2)
            self._nav_buttons[page_id] = btn

        # 底部信息
        bottom_frame = ctk.CTkFrame(self._sidebar)
        bottom_frame.grid(row=10, column=0, sticky="ew", padx=15, pady=10)
        bottom_frame.grid_rowconfigure(10, weight=1)

        ctk.CTkLabel(bottom_frame, text="v1.0.0", text_color="gray",
                     font=ctk.CTkFont(size=10)).pack(side="bottom")

    def _highlight_nav(self, page_id: str):
        """高亮当前导航按钮"""
        for pid, btn in self._nav_buttons.items():
            if pid == page_id:
                btn.configure(fg_color=("gray80", "gray28"))
            else:
                btn.configure(fg_color="transparent")

    # ===== 页面管理 =====

    def _build_pages(self):
        """构建所有页面"""
        # 状态页
        self._status_panel = StatusPanel(self._content, self._ssh, self._config)
        self._pages["status"] = self._status_panel

        # 文件管理页
        self._file_browser = FileBrowser(self._content, self._ssh, self._config)
        self._pages["files"] = self._file_browser

        # 终端页
        self._terminal_page = self._build_terminal_page()
        self._pages["terminal"] = self._terminal_page

        # 设置页
        self._settings_page = self._build_settings_page()
        self._pages["settings"] = self._settings_page

    def _show_page(self, page_id: str):
        """切换页面"""
        if self._current_page == page_id:
            return
        self._current_page = page_id
        self._highlight_nav(page_id)

        # 隐藏所有页面
        for page in self._pages.values():
            page.grid_remove()

        # 显示目标页面
        page = self._pages[page_id]
        page.grid(row=0, column=0, sticky="nsew")
        # 新页面需要重新绘制背景
        if self._config["appearance"].get("background_path"):
            self.after(100, self._apply_background)

        # 页面切换时的额外操作
        if page_id == "status":
            if self._ssh.connected:
                self._status_panel.refresh()
        elif page_id == "files":
            if self._ssh.connected:
                self._file_browser.refresh()

    # ===== 终端页面 =====

    def _build_terminal_page(self) -> ctk.CTkFrame:
        """构建命令终端页面"""
        frame = ctk.CTkFrame(self._content, fg_color="transparent", corner_radius=0)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(0, weight=0)
        frame.grid_rowconfigure(1, weight=1)
        frame.grid_rowconfigure(2, weight=0)

        # 快捷命令
        quick_frame = ctk.CTkFrame(frame)
        quick_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=(5, 2))

        quick_cmds = [
            ("📊 状态", "top -bn1 | head -5"),
            ("📁 文件", "ls -lah"),
            ("💾 磁盘", "df -h"),
            ("🧠 内存", "free -m"),
            ("🌡️ 温度", "vcgencmd measure_temp"),
            ("⏱ 运行", "uptime"),
        ]
        for text, cmd in quick_cmds:
            btn = ctk.CTkButton(
                quick_frame, text=text, width=70, height=26,
                font=ctk.CTkFont(size=11), fg_color="#2B3B2B",
                hover_color="#3A4A3A",
                command=lambda c=cmd: self._run_terminal_cmd(c))
            btn.pack(side="left", padx=2)

        ctk.CTkButton(
            quick_frame, text="🗑 清屏", width=60, height=26,
            font=ctk.CTkFont(size=11), fg_color="transparent",
            border_width=1, border_color=("gray40", "gray30"),
            command=self._clear_terminal).pack(side="right", padx=2)

        # 输出区
        self._terminal_output = ctk.CTkTextbox(
            frame, font=ctk.CTkFont(family="Consolas", size=12),
            fg_color="#0D1117", text_color="#C9D1D9")
        self._terminal_output.grid(row=1, column=0, sticky="nsew", padx=5, pady=2)

        # 命令输入行
        input_frame = ctk.CTkFrame(frame, fg_color="transparent", corner_radius=0)
        input_frame.grid(row=2, column=0, sticky="ew", padx=5, pady=(2, 5))
        input_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(input_frame, text="pi@zero:~$",
                     font=ctk.CTkFont(family="Consolas", size=13),
                     text_color="#4CAF50").grid(row=0, column=0, padx=(8, 4), pady=5)

        self._terminal_input = ctk.CTkEntry(
            input_frame, font=ctk.CTkFont(family="Consolas", size=13),
            fg_color="#0D1117", text_color="#C9D1D9",
            border_width=0, placeholder_text="输入命令...")
        self._terminal_input.grid(row=0, column=1, sticky="ew", padx=(0, 4), pady=5)
        self._terminal_input.bind("<Return>", lambda e: self._run_terminal_cmd())

        send_btn = ctk.CTkButton(
            input_frame, text="发送", width=60, height=28,
            command=lambda: self._run_terminal_cmd())
        send_btn.grid(row=0, column=2, padx=(0, 8), pady=5)

        return frame

    def _terminal_log(self, text: str, color: str = None):
        """终端输出"""
        self._terminal_output.insert("end", text)
        self._terminal_output.see("end")

    def _run_terminal_cmd(self, cmd: str = None):
        """执行终端命令"""
        if cmd is None:
            cmd = self._terminal_input.get().strip()
            self._terminal_input.delete(0, "end")

        if not cmd:
            return

        if not self._ssh.connected:
            self._terminal_log("\n❌ 未连接到树莓派\n")
            return

        self._terminal_log(f"\n💲 {cmd}\n")
        self._status_label.configure(text=f"执行: {cmd[:50]}...")

        def _exec():
            code, out, err = self._ssh.exec_command(cmd, timeout=60)
            self.after(0, lambda: self._on_terminal_result(out, err, cmd))

        threading.Thread(target=_exec, daemon=True).start()

    def _on_terminal_result(self, stdout: str, stderr: str, cmd: str):
        """终端结果回调"""
        if stdout:
            self._terminal_log(stdout.rstrip() + "\n")
        if stderr:
            self._terminal_log(stderr.rstrip() + "\n", "#FF6B6B")
        self._status_label.configure(text="就绪")

    def _clear_terminal(self):
        """清屏"""
        self._terminal_output.delete("1.0", "end")

    # ===== 设置页面 =====

    def _build_settings_page(self) -> ctk.CTkFrame:
        """构建设置页面"""
        frame = ctk.CTkFrame(self._content, fg_color="transparent", corner_radius=0)

        # 使用scrollable
        scroll = ctk.CTkScrollableFrame(frame, fg_color="transparent", corner_radius=0)
        scroll.pack(fill="both", expand=True, padx=5, pady=5)

        # ===== 外观设置 =====
        self._section_label(scroll, "🎨 外观设置", 0)

        theme_frame = ctk.CTkFrame(scroll)
        theme_frame.pack(fill="x", pady=5)
        theme_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(theme_frame, text="主题模式:").grid(row=0, column=0, sticky="w", padx=10, pady=8)
        theme_var = ctk.StringVar(value=self._config["appearance"]["theme"])
        theme_menu = ctk.CTkOptionMenu(
            theme_frame, values=["dark", "light"], variable=theme_var,
            command=lambda v: self._on_theme_change(v))
        theme_menu.grid(row=0, column=1, sticky="e", padx=10, pady=8)

        ctk.CTkLabel(theme_frame, text="颜色主题:").grid(row=1, column=0, sticky="w", padx=10, pady=8)
        color_var = ctk.StringVar(value=self._config["appearance"]["color_theme"])
        color_menu = ctk.CTkOptionMenu(
            theme_frame, values=["green", "blue", "dark-blue"], variable=color_var,
            command=lambda v: ctk.set_default_color_theme(v))
        color_menu.grid(row=1, column=1, sticky="e", padx=10, pady=8)

        ctk.CTkLabel(theme_frame, text="字体缩放:").grid(row=2, column=0, sticky="w", padx=10, pady=8)
        scale_var = ctk.DoubleVar(value=self._config["appearance"]["font_scale"])
        scale_slider = ctk.CTkSlider(
            theme_frame, from_=0.8, to=1.5, number_of_steps=7, variable=scale_var,
            command=lambda v: ctk.set_widget_scaling(float(v)))
        scale_slider.grid(row=2, column=1, sticky="ew", padx=10, pady=8)

        # ===== 背景设置 =====
        self._section_label(scroll, "🖼️ 背景设置", 0)

        bg_frame = ctk.CTkFrame(scroll)
        bg_frame.pack(fill="x", pady=5)

        ctk.CTkLabel(bg_frame, text="背景图片:").grid(row=0, column=0, sticky="w", padx=10, pady=8)
        bg_path = self._config["appearance"].get("background_path", "")
        bg_display = os.path.basename(bg_path) if bg_path else "未设置"
        self._bg_path_label = ctk.CTkLabel(bg_frame, text=bg_display, text_color="gray")
        self._bg_path_label.grid(row=0, column=1, sticky="e", padx=10, pady=8)

        bg_btn_frame = ctk.CTkFrame(bg_frame, fg_color="transparent", corner_radius=0)
        bg_btn_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 8))
        ctk.CTkButton(
            bg_btn_frame, text="选择图片", width=90, height=28,
            command=self._choose_background).pack(side="left", padx=2)
        ctk.CTkButton(
            bg_btn_frame, text="清除背景", width=90, height=28,
            fg_color="transparent", border_width=1, border_color=("gray40", "gray30"),
            command=self._clear_background).pack(side="left", padx=2)

        ctk.CTkLabel(bg_frame, text="背景透明度:").grid(row=2, column=0, sticky="w", padx=10, pady=8)
        opacity_var = ctk.DoubleVar(value=self._config["appearance"]["background_opacity"])
        opacity_slider = ctk.CTkSlider(
            bg_frame, from_=0.05, to=0.5, number_of_steps=9, variable=opacity_var,
            command=lambda v: self._on_opacity_change(float(v)))
        opacity_slider.grid(row=2, column=1, sticky="ew", padx=10, pady=8)

        # ===== 行为设置 =====
        self._section_label(scroll, "⚡ 行为设置", 0)

        behavior_frame = ctk.CTkFrame(scroll)
        behavior_frame.pack(fill="x", pady=5)

        auto_conn_var = ctk.BooleanVar(value=self._config["behavior"]["auto_connect"])
        ctk.CTkCheckBox(
            behavior_frame, text="启动时自动连接", variable=auto_conn_var).grid(
            row=0, column=0, sticky="w", padx=10, pady=8)

        ctk.CTkLabel(behavior_frame, text="刷新间隔(秒):").grid(row=1, column=0, sticky="w", padx=10, pady=8)
        refresh_var = ctk.IntVar(value=self._config["behavior"]["refresh_interval"])
        ctk.CTkSlider(
            behavior_frame, from_=1, to=30, number_of_steps=29, variable=refresh_var,
            command=lambda v: self._update_refresh_label(int(v), refresh_label)).grid(
            row=1, column=1, sticky="ew", padx=10, pady=8)
        refresh_label = ctk.CTkLabel(behavior_frame, text=f"{refresh_var.get()}秒")
        refresh_label.grid(row=1, column=2, padx=10, pady=8)

        confirm_var = ctk.BooleanVar(value=self._config["behavior"]["confirm_before_delete"])
        ctk.CTkCheckBox(
            behavior_frame, text="删除前确认", variable=confirm_var).grid(
            row=2, column=0, sticky="w", padx=10, pady=8)

        # 保存按钮
        ctk.CTkButton(
            scroll, text="💾 保存设置", height=36, fg_color="#2B5B2B",
            hover_color="#3A7A3A",
            command=lambda: self._save_settings(
                theme_var.get(), color_var.get(), scale_var.get(),
                opacity_var.get(), auto_conn_var.get(), refresh_var.get(),
                confirm_var.get())).pack(pady=15)

        return frame

    def _section_label(self, parent, text: str, row: int):
        """节标题"""
        lbl = ctk.CTkLabel(parent, text=text, font=ctk.CTkFont(size=14, weight="bold"),
                           anchor="w")
        lbl.pack(fill="x", pady=(15, 5), padx=5)

    def _on_theme_change(self, theme: str):
        """切换主题"""
        ctk.set_appearance_mode(theme)
        self.after(200, self._apply_background)

    def _on_opacity_change(self, val: float):
        """调整背景透明度"""
        self._config["appearance"]["background_opacity"] = float(val)
        self._apply_background(force=True)

    def _choose_background(self):
        """选择背景图片"""
        path = filedialog.askopenfilename(
            title="选择背景图片",
            filetypes=[("图片文件", "*.jpg *.jpeg *.png *.bmp *.gif"), ("所有文件", "*.*")])
        if path:
            self._config["appearance"]["background_path"] = path
            self._bg_path_label.configure(text=os.path.basename(path))
            self._apply_background(force=True)

    def _clear_background(self):
        """清除背景"""
        self._config["appearance"]["background_path"] = ""
        self._bg_path_label.configure(text="未设置")
        self._clear_all_bg_images()

    def _on_window_resize(self, event=None):
        """窗口大小改变时更新背景（仅当尺寸真正变化）"""
        if not hasattr(self, '_content'):
            return
        cw = self._content.winfo_width()
        ch = self._content.winfo_height()
        if cw < 50 or ch < 50:
            return
        last_size = getattr(self, '_bg_last_size', (0, 0))
        if (cw, ch) == last_size:
            return
        self._bg_last_size = (cw, ch)
        if hasattr(self, '_resize_after_id') and self._resize_after_id:
            self.after_cancel(self._resize_after_id)
        self._resize_after_id = self.after(600, self._apply_background)

    def _apply_background(self, force=False):
        """应用背景 - 加载图片，递归绘制到所有内容区域 Canvas 上"""
        if hasattr(self, '_bg_applying') and self._bg_applying:
            return  # 防止重叠调用
        self._bg_applying = True
        try:
            self._do_apply_background()
        finally:
            self._bg_applying = False

    def _do_apply_background(self):
        self._clear_all_bg_images()

        bg_path = self._config["appearance"].get("background_path", "")
        if not bg_path or not os.path.exists(bg_path):
            return

        try:
            opacity = self._config["appearance"].get("background_opacity", 0.25)
            self.update_idletasks()
            cw = self._content.winfo_width()
            ch = self._content.winfo_height()
            if cw < 50 or ch < 50:
                cw, ch = 850, 660

            img = Image.open(bg_path)
            img = img.resize((cw, ch), Image.LANCZOS)
            if img.mode != "RGBA":
                img = img.convert("RGBA")

            img.putalpha(Image.new("L", img.size, int(255 * opacity)))

            self._bg_image = ImageTk.PhotoImage(img)
            self._draw_bg_on_canvas(self._content)

        except Exception:
            pass

    def _draw_bg_on_canvas(self, widget, count=None):
        """递归在所有 CTkFrame canvas 上绘制裁剪后的背景图"""
        if not self._bg_image:
            return

        if hasattr(widget, '_canvas'):
            try:
                c = widget._canvas
                wx = c.winfo_rootx() - self._content.winfo_rootx()
                wy = c.winfo_rooty() - self._content.winfo_rooty()
                cw = c.winfo_width()
                ch = c.winfo_height()

                if cw > 2 and ch > 2:
                    pil_img = ImageTk.getimage(self._bg_image)
                    left = max(0, wx)
                    top = max(0, wy)
                    right = min(pil_img.width, wx + cw)
                    bottom = min(pil_img.height, wy + ch)

                    if right > left and bottom > top:
                        cropped = pil_img.crop((int(left), int(top), int(right), int(bottom)))
                        tk_img = ImageTk.PhotoImage(cropped)
                        self._bg_refs.append(tk_img)

                        dx = -wx if wx < 0 else 0
                        dy = -wy if wy < 0 else 0
                        c.create_image(dx, dy, anchor="nw", image=tk_img, tags="bg_image")
                        c.tag_lower("bg_image")
                        if count is not None:
                            count[0] += 1
            except Exception:
                pass

        for child in widget.winfo_children():
            self._draw_bg_on_canvas(child, count)

    def _clear_all_bg_images(self):
        """清除所有 canvas 上的背景图"""
        def _clear(widget):
            if hasattr(widget, '_canvas'):
                try:
                    widget._canvas.delete("bg_image")
                except Exception:
                    pass
            for child in widget.winfo_children():
                _clear(child)
        if hasattr(self, '_content'):
            _clear(self._content)
        self._bg_refs.clear()
        self._bg_image = None

    def _update_refresh_label(self, val: int, label):
        """更新刷新间隔标签"""
        label.configure(text=f"{val}秒")

    def _save_settings(self, theme, color_theme, scale, opacity,
                       auto_conn, refresh, confirm):
        """保存设置"""
        self._config["appearance"].update({
            "theme": theme,
            "color_theme": color_theme,
            "font_scale": float(scale),
            "background_opacity": float(opacity),
        })
        self._config["behavior"].update({
            "auto_connect": bool(auto_conn),
            "refresh_interval": int(refresh),
            "confirm_before_delete": bool(confirm),
        })

        try:
            save_config(self._config)
            ctk.set_widget_scaling(float(scale))
            messagebox.showinfo("保存成功", "设置已保存")
        except Exception as e:
            messagebox.showerror("保存失败", str(e))

    # ===== 连接管理 =====

    def _auto_connect(self):
        """自动连接"""
        conn = self._config.get("connections", [{}])[0]
        if not conn:
            return
        self._do_connect(
            conn.get("host", ""),
            conn.get("port", 22),
            conn.get("username", "pi"),
            conn.get("key_path", ""),
            conn.get("password", ""),
            conn.get("use_key", True)
        )

    def _toggle_connection(self):
        """切换连接/断开"""
        if self._ssh.connected:
            self._ssh.disconnect()
            self._on_disconnected()
        else:
            conn = self._config.get("connections", [{}])[0]
            if not conn:
                self._show_conn_settings()
                return
            self._do_connect(
                conn.get("host", ""),
                conn.get("port", 22),
                conn.get("username", "pi"),
                conn.get("key_path", ""),
                conn.get("password", ""),
                conn.get("use_key", True)
            )

    def _do_connect(self, host, port, username, key_path, password, use_key):
        """执行连接"""
        self._status_label.configure(text=f"正在连接 {host}...")
        self._btn_connect.configure(text="⏳ 连接中...", state="disabled")

        def _connect():
            kp = key_path if use_key and key_path else None
            pw = password if not use_key else None
            ok, msg = self._ssh.connect(host, port, username, kp, pw)
            self.after(0, lambda: self._on_connect_result(ok, msg))

        threading.Thread(target=_connect, daemon=True).start()

    def _on_connect_result(self, ok: bool, msg: str):
        """连接结果回调"""
        if ok:
            self._conn_indicator.configure(text="🟢 已连接")
            self._conn_host.configure(text=f"{self._ssh.host}")
            self._btn_connect.configure(text="🔌 断开", state="normal",
                                        fg_color="#8B0000", hover_color="#A00000")
            self._status_label.configure(text="已连接")

            # 刷新当前页面
            if self._current_page == "status":
                self._status_panel.refresh()
                self._status_panel.start_auto_refresh()
            elif self._current_page == "files":
                self._file_browser.refresh()
        else:
            self._conn_indicator.configure(text="🔴 连接失败")
            self._conn_host.configure(text=msg)
            self._btn_connect.configure(text="🔌 连接", state="normal",
                                        fg_color="#2B5B2B", hover_color="#3A7A3A")
            self._status_label.configure(text="连接失败")
            messagebox.showerror("连接失败", msg)

    def _on_disconnected(self):
        """断开连接回调"""
        self._conn_indicator.configure(text="🔴 未连接")
        self._conn_host.configure(text="")
        self._btn_connect.configure(text="🔌 连接", state="normal",
                                    fg_color="#2B5B2B", hover_color="#3A7A3A")
        self._status_label.configure(text="已断开")
        if self._current_page == "status":
            self._status_panel.stop_auto_refresh()

    def _show_conn_settings(self):
        """显示连接设置对话框"""
        dialog = ctk.CTkToplevel(self)
        dialog.title("连接设置")
        dialog.geometry("450x380")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        conn = self._config.get("connections", [{}])[0] if self._config.get("connections") else {}

        content = ctk.CTkFrame(dialog, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=20, pady=20)

        fields = [
            ("连接名称:", "name", conn.get("name", "树莓派")),
            ("主机地址:", "host", conn.get("host", "muchenxi-20081128.local")),
            ("端口:", "port", str(conn.get("port", 22))),
            ("用户名:", "username", conn.get("username", "chenxi")),
        ]

        entries = {}
        for i, (label, key, default) in enumerate(fields):
            ctk.CTkLabel(content, text=label, anchor="w").grid(
                row=i, column=0, sticky="w", pady=6, padx=(0, 10))
            entry = ctk.CTkEntry(content, width=200)
            entry.grid(row=i, column=1, sticky="ew", pady=6)
            entry.insert(0, default)
            entries[key] = entry
            content.grid_columnconfigure(1, weight=1)

        # 密钥路径
        ctk.CTkLabel(content, text="密钥路径:", anchor="w").grid(
            row=4, column=0, sticky="w", pady=6, padx=(0, 10))

        key_frame = ctk.CTkFrame(content, fg_color="transparent")
        key_frame.grid(row=4, column=1, sticky="ew", pady=6)
        key_frame.grid_columnconfigure(0, weight=1)

        key_entry = ctk.CTkEntry(key_frame)
        key_entry.grid(row=0, column=0, sticky="ew")
        key_entry.insert(0, conn.get("key_path", ""))
        entries["key_path"] = key_entry

        ctk.CTkButton(
            key_frame, text="📂", width=36, height=28,
            command=lambda: self._browse_key(key_entry)).grid(
            row=0, column=1, padx=(4, 0))

        # 连接提示
        ctk.CTkLabel(content, text="💡 提示：密钥认证优先，留空密码则使用密钥",
                     text_color="gray", font=ctk.CTkFont(size=11)).grid(
            row=5, column=0, columnspan=2, pady=10, sticky="w")

        # 按钮
        btn_frame = ctk.CTkFrame(content, fg_color="transparent")
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

        ctk.CTkButton(btn_frame, text="💾 保存并连接", command=lambda: (_save(), self._auto_connect())).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="保存", command=_save, fg_color="transparent",
                      border_width=1, border_color=("gray40", "gray30")).pack(side="left", padx=5)

    def _browse_key(self, entry):
        """浏览密钥文件"""
        path = filedialog.askopenfilename(
            title="选择SSH密钥",
            initialdir=os.path.join(os.path.expanduser("~"), ".ssh"),
            filetypes=[("密钥文件", "id_*"), ("PEM文件", "*.pem"), ("所有文件", "*.*")])
        if path:
            entry.delete(0, "end")
            entry.insert(0, path)

    # ===== 关闭 =====

    def _on_close(self):
        """关闭应用"""
        if self._current_page == "status":
            self._status_panel.stop_auto_refresh()
        self._ssh.disconnect()
        self.destroy()
