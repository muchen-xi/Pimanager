"""
PiManager 主应用窗口
"""
import customtkinter as ctk
import threading
import os
from pathlib import Path
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk

from .config import load_config, save_config
from .ssh_client import SSHClient
from .status_panel import StatusPanel
from .file_browser import FileBrowser
from .terminal_page import TerminalPage
from .settings_page import SettingsPage


# ============================================================
#  BackgroundManager — 全局背景管理
#  原理：拦截所有 CTk 控件 _draw()，将 inner_parts 透明化
#  并把背景图片片段绘制到 canvas 底部。
#  对所有处于 _content 区域内的控件自动生效。
# ============================================================
class BackgroundManager:
    """全局背景管理器。

    通过 monkey-patch 所有 CTk 控件的 _draw() 实现背景穿透。
    拦截的控件: CTkFrame, CTkTextbox, CTkEntry, CTkButton,
    CTkLabel, CTkOptionMenu, CTkComboBox, CTkCheckBox,
    CTkSlider, CTkProgressBar, CTkSwitch。
    只作用于 _content 区域内，不影响侧边栏和对话框。
    """

    _bg_path: str = ""
    _bg_pil = None          # 完整的混合后背景 PIL Image（缓存，避免 getimage）
    _bg_tk_full = None      # 完整的 PhotoImage
    _bg_opacity: float = 0.15
    _content_frame = None
    _refs: list = []
    _enabled: bool = False
    _original_draws: dict = {}  # {widget_class: original_draw_method}
    _excluded_widgets: set = set()  # 不应用背景的控件（如设置页）

    @classmethod
    def setup(cls, content_frame):
        """在应用启动时调用一次：拦截所有 CTk 控件 _draw()。"""
        cls._content_frame = content_frame
        if not cls._original_draws:
            _PATCH_CLASSES = [
                ctk.CTkFrame,
                ctk.CTkTextbox,
                ctk.CTkEntry,
                ctk.CTkButton,
                ctk.CTkLabel,
                ctk.CTkOptionMenu,
                ctk.CTkComboBox,
                ctk.CTkCheckBox,
                ctk.CTkSlider,
                ctk.CTkProgressBar,
                ctk.CTkSwitch,
            ]
            for wc in _PATCH_CLASSES:
                if wc in cls._original_draws:
                    continue
                original = wc._draw
                cls._original_draws[wc] = original

                def _make_patched(_orig):
                    def _draw_patched(self_widget, no_color_updates=False):
                        _orig(self_widget, no_color_updates)
                        cls._on_widget_draw(self_widget)
                    return _draw_patched

                wc._draw = _make_patched(original)

    @classmethod
    def set_background(cls, path: str, opacity: float):
        """设置/更换背景图片。"""
        cls._bg_path = path
        cls._bg_opacity = opacity
        cls._refs.clear()
        if path and os.path.exists(path):
            try:
                cls._bg_pil = Image.open(path)
                cls._enabled = True
                cls._prepare_full_image()
                cls._refresh_all_frames()
            except Exception:
                cls._enabled = False
                cls._bg_pil = None
        else:
            cls._bg_pil = None
            cls._bg_tk_full = None
            cls._enabled = False

    @classmethod
    def clear(cls):
        """清除背景图片。"""
        cls._bg_path = ""
        cls._bg_pil = None
        cls._bg_tk_full = None
        cls._enabled = False
        cls._refs.clear()
        if cls._content_frame:
            cls._clear_all(cls._content_frame)
            cls._force_draw_descendants(cls._content_frame)

    @classmethod
    def refresh_size(cls):
        """窗口大小改变后重新缩放并重绘背景。"""
        if cls._enabled and cls._bg_pil:
            cls._prepare_full_image()
            cls._refresh_all_frames()

    # ---- 内部实现 ----

    @classmethod
    def _prepare_full_image(cls):
        """缩放背景图并叠加暗色基底（混合后在内存中保留 PIL Image）。"""
        if not cls._bg_pil or not cls._content_frame:
            return
        cw = cls._content_frame.winfo_width()
        ch = cls._content_frame.winfo_height()
        if cw < 50 or ch < 50:
            cw, ch = 900, 660
        bg = cls._bg_pil.resize((cw, ch), Image.LANCZOS).convert("RGBA")
        dark = Image.new("RGBA", (cw, ch), (13, 17, 23, 255))
        # 混合暗色基底与背景图
        blended = Image.blend(dark.convert("RGB"), bg.convert("RGB"), cls._bg_opacity)
        cls._bg_pil_blended = blended   # ★ 缓存 PIL Image，避免 ImageTk.getimage()
        cls._bg_tk_full = ImageTk.PhotoImage(blended)

    @classmethod
    def _on_widget_draw(cls, widget):
        """在控件 _draw() 完成后执行：透明化 + 画背景片段。"""
        if not cls._enabled or not cls._bg_tk_full:
            return
        if not cls._content_frame:
            return
        if not cls._is_descendant_of_content(widget):
            return

        # 处理 CTkScrollableFrame（无 _canvas）或包含 scrollable frame 的容器
        cls._handle_scrollable_frame(widget)

        if not hasattr(widget, '_canvas'):
            return

        try:
            c = widget._canvas
            if not c.winfo_exists():
                return
            cw = c.winfo_width()
            ch = c.winfo_height()
            if cw < 3 or ch < 3:
                return

            # ★ 彻底透明化 canvas + 绘制背景片段
            cls._make_canvas_transparent(c)

            # 计算控件在内容区中的坐标（用于内部 widget 同步）
            wx = c.winfo_rootx() - cls._content_frame.winfo_rootx()
            wy = c.winfo_rooty() - cls._content_frame.winfo_rooty()

            # ★ CTkTextbox/CTkEntry 内部 widget 背景同步
            cls._sync_inner_widget_bg(widget, wx, wy, cw, ch)

        except Exception:
            pass

    @classmethod
    def _handle_scrollable_frame(cls, widget):
        """递归清除 CTkScrollableFrame 所有内部层的背景（不画片段，交子控件处理）。"""
        try:
            # 清除 _parent_canvas 上的不透明背景项
            if hasattr(widget, '_parent_canvas'):
                pc = widget._parent_canvas
                if pc.winfo_exists() and pc.winfo_width() >= 3:
                    for tag in ("inner_parts", "bg_parts", "background_parts", "background"):
                        try:
                            pc.itemconfig(tag, fill="", outline="")
                        except Exception:
                            pass

            # 递归处理内部所有子控件
            if hasattr(widget, 'winfo_children'):
                for child in widget.winfo_children():
                    if hasattr(child, '_canvas'):
                        cls._on_widget_draw(child)
                    else:
                        cls._handle_scrollable_frame(child)
        except Exception:
            pass

    @classmethod
    def _make_canvas_transparent(cls, canvas):
        """彻底透明化一个 canvas：清除所有背景项 + 绘制背景图片片段。"""
        try:
            if not canvas.winfo_exists():
                return
            pw = canvas.winfo_width()
            ph = canvas.winfo_height()
            if pw < 3 or ph < 3:
                return

            # 清除所有可能的背景标签
            for tag in ("inner_parts", "bg_parts", "background_parts", "background", "bg"):
                try:
                    canvas.itemconfig(tag, fill="", outline="")
                except Exception:
                    pass
            canvas.delete("background_parts")

            # 计算坐标并绘制背景片段
            wx = canvas.winfo_rootx() - cls._content_frame.winfo_rootx()
            wy = canvas.winfo_rooty() - cls._content_frame.winfo_rooty()
            pil_full = getattr(cls, '_bg_pil_blended', None)
            if pil_full is None:
                return
            left = max(0, int(wx))
            top = max(0, int(wy))
            right = min(pil_full.width, int(wx + pw))
            bottom = min(pil_full.height, int(wy + ph))
            if right > left and bottom > top:
                cropped = pil_full.crop((left, top, right, bottom))
                tk_img = ImageTk.PhotoImage(cropped)
                cls._refs.append(tk_img)
                if len(cls._refs) > 500:
                    cls._refs = cls._refs[-200:]
                canvas.delete("bg_image")
                dx = -int(wx) if wx < 0 else 0
                dy = -int(wy) if wy < 0 else 0
                canvas.create_image(dx, dy, anchor="nw", image=tk_img, tags="bg_image")
                canvas.tag_lower("bg_image")
        except Exception:
            pass

    @classmethod
    def _sync_inner_widget_bg(cls, widget, wx, wy, cw, ch):
        """同步 CTkTextbox._textbox / CTkEntry._entry 的背景色，去除边框感。"""
        if isinstance(widget, ctk.CTkTextbox) and hasattr(widget, '_textbox'):
            avg = cls._sample_color(wx, wy, cw, ch)
            try:
                widget._textbox.configure(
                    bg=avg, highlightthickness=0, borderwidth=0,
                    insertbackground="#C9D1D9")
            except Exception:
                pass
        if isinstance(widget, ctk.CTkEntry) and hasattr(widget, '_entry'):
            avg = cls._sample_color(wx, wy, cw, ch)
            try:
                widget._entry.configure(
                    bg=avg, highlightthickness=0, borderwidth=0,
                    insertbackground="#C9D1D9", relief="flat")
            except Exception:
                pass

    @classmethod
    def _sample_color(cls, wx, wy, cw, ch) -> str:
        """从混合背景图采样颜色，返回适合文本区域背景的深色调。"""
        pil_full = getattr(cls, '_bg_pil_blended', None)
        if pil_full is None:
            return "#0D1117"
        try:
            left = max(0, int(wx))
            top = max(0, int(wy))
            right = min(pil_full.width, int(wx + cw))
            bottom = min(pil_full.height, int(wy + ch))
            if right <= left or bottom <= top:
                return "#0D1117"
            region = pil_full.crop((left, top, right, bottom))
            region = region.resize((1, 1), Image.LANCZOS)
            pixel = region.getpixel((0, 0))
            if len(pixel) >= 4:
                r, g, b = pixel[0], pixel[1], pixel[2]
            else:
                r, g, b = pixel
            # 直接匹配背景图颜色，让文字区域融入背景
            r, g, b = int(r * 1.0), int(g * 1.0), int(b * 1.0)
            return f'#{r:02x}{g:02x}{b:02x}'
        except Exception:
            return "#0D1117"

    @classmethod
    def _refresh_all_frames(cls):
        if cls._content_frame:
            cls._force_draw_descendants(cls._content_frame)

    @classmethod
    def _force_draw_descendants(cls, widget):
        """递归触发所有后代控件的 _draw()，确保背景刷新。"""
        try:
            if hasattr(widget, '_draw'):
                widget._draw()
            # CTkScrollableFrame: 也刷新其内部 canvas
            if hasattr(widget, '_parent_canvas'):
                cls._handle_scrollable_frame(widget)
            if hasattr(widget, '_canvas'):
                cls._on_widget_draw(widget)
        except Exception:
            pass
        if hasattr(widget, 'winfo_children'):
            for child in widget.winfo_children():
                cls._force_draw_descendants(child)

    @classmethod
    def exclude_widget(cls, widget):
        """将某个控件及其所有后代排除出背景处理（如设置页）。"""
        cls._excluded_widgets.add(widget)

    @classmethod
    def _is_descendant_of_content(cls, widget) -> bool:
        try:
            parent = widget.master
            while parent:
                if parent in cls._excluded_widgets:
                    return False
                if parent is cls._content_frame:
                    return True
                parent = parent.master
        except Exception:
            pass
        return False

    @classmethod
    def _is_inside_scrollable(cls, widget) -> bool:
        """判断控件是否在 CTkScrollableFrame 内部（避免每个子控件单独画背景导致滚动跳动）。"""
        try:
            parent = widget.master
            while parent:
                if parent is cls._content_frame:
                    return False
                if hasattr(parent, '_parent_canvas'):
                    return True  # 找到了最近的一个 scrollable frame
                parent = parent.master
        except Exception:
            pass
        return False

    @classmethod
    def _clear_all(cls, widget):
        if hasattr(widget, '_canvas'):
            try:
                widget._canvas.delete("bg_image")
            except Exception:
                pass
        for child in widget.winfo_children():
            cls._clear_all(child)


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

        # 图标
        icon_path = Path(__file__).parent / "assets" / "icon.ico"
        if icon_path.exists():
            try:
                self.iconbitmap(str(icon_path))
            except Exception:
                pass

        # 布局
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)

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
        BackgroundManager.setup(self._content)
        self.after(500, self._apply_background)
        self.bind("<Configure>", self._on_window_resize)

        # ===== 页面容器 =====
        self._pages = {}
        self._current_page = None
        self._build_pages()

        # ===== 状态栏 =====
        self._status_bar = ctk.CTkFrame(self, height=28, corner_radius=0)
        self._status_bar.grid(row=1, column=1, sticky="ew")
        self._status_bar.grid_columnconfigure(1, weight=1)
        self._status_label = ctk.CTkLabel(
            self._status_bar, text="就绪", anchor="w",
            font=ctk.CTkFont(size=11))
        self._status_label.grid(row=0, column=0, padx=10, sticky="w")
        self._status_right = ctk.CTkLabel(
            self._status_bar, text="", anchor="e",
            font=ctk.CTkFont(size=11), text_color="gray")
        self._status_right.grid(row=0, column=1, padx=10, sticky="e")

        # 显示首页
        self._show_page("status")

        # 自动连接
        if self._config.get("behavior", {}).get("auto_connect", False):
            self.after(500, self._auto_connect)

    # ============================================================
    #  侧边栏
    # ============================================================

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
            border_color=("gray40", "gray30"), font=ctk.CTkFont(size=12))
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
        ctk.CTkLabel(bottom_frame, text="v1.1.0", text_color="gray",
                     font=ctk.CTkFont(size=10)).pack(side="bottom")

    def _highlight_nav(self, page_id: str):
        """高亮当前导航按钮"""
        for pid, btn in self._nav_buttons.items():
            if pid == page_id:
                btn.configure(fg_color=("gray80", "gray28"))
            else:
                btn.configure(fg_color="transparent")

    # ============================================================
    #  页面管理
    # ============================================================

    def _build_pages(self):
        """构建所有页面"""
        # 状态页
        self._status_panel = StatusPanel(self._content, self._ssh, self._config)
        self._pages["status"] = self._status_panel

        # 文件管理页
        self._file_browser = FileBrowser(self._content, self._ssh, self._config, app_ref=self)
        self._pages["files"] = self._file_browser

        # 终端页（多标签多 Agent）
        self._terminal_page = TerminalPage(self._content, self._ssh, self._config, app_ref=self)
        self._pages["terminal"] = self._terminal_page

        # 设置页（排除背景处理）
        self._settings_page = SettingsPage(self._content, self._config, self._ssh, app_ref=self)
        self._pages["settings"] = self._settings_page
        BackgroundManager.exclude_widget(self._settings_page)

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

        # 强制刷新背景（确保新显示的页面所有控件都被重绘）
        self.update_idletasks()
        if BackgroundManager._enabled:
            self.after(50, lambda: BackgroundManager._force_draw_descendants(page))

        # 页面切换时刷新
        if page_id == "status":
            if self._ssh.connected:
                self._status_panel.refresh()
        elif page_id == "files":
            if self._ssh.connected:
                self._file_browser.refresh()

    # ============================================================
    #  背景管理
    # ============================================================

    def _on_window_resize(self, event=None):
        """窗口大小改变时更新背景（防抖 400ms）"""
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
        self._resize_after_id = self.after(400, lambda: BackgroundManager.refresh_size())

    def _apply_background(self, force=False):
        """应用背景图片"""
        bg_path = self._config["appearance"].get("background_path", "")
        opacity = self._config["appearance"].get("background_opacity", 0.15)
        BackgroundManager.set_background(bg_path, float(opacity))

    # ============================================================
    #  连接管理
    # ============================================================

    def _auto_connect(self):
        """自动连接"""
        conn = self._config.get("connections", [{}])[0]
        if not conn or not conn.get("host"):
            return
        self._do_connect(
            conn.get("host", ""),
            conn.get("port", 22),
            conn.get("username", "pi"),
            conn.get("key_path", ""),
            conn.get("password", ""),
            conn.get("use_key", True),
        )

    def _toggle_connection(self):
        """切换连接/断开"""
        if self._ssh.connected:
            self._ssh.disconnect()
            self._on_disconnected()
        else:
            conn = self._config.get("connections", [{}])[0]
            if not conn or not conn.get("host"):
                self._show_conn_settings()
                return
            self._do_connect(
                conn.get("host", ""),
                conn.get("port", 22),
                conn.get("username", "pi"),
                conn.get("key_path", ""),
                conn.get("password", ""),
                conn.get("use_key", True),
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
            command=lambda: self._browse_key(key_entry)).grid(row=0, column=1, padx=(4, 0))

        ctk.CTkLabel(content, text="💡 提示：密钥认证优先，留空密码则使用密钥",
                     text_color="gray", font=ctk.CTkFont(size=11)).grid(
            row=5, column=0, columnspan=2, pady=10, sticky="w")

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

        ctk.CTkButton(
            btn_frame, text="💾 保存并连接",
            command=lambda: (_save(), self._auto_connect())
        ).pack(side="left", padx=5)
        ctk.CTkButton(
            btn_frame, text="保存", command=_save,
            fg_color="transparent", border_width=1,
            border_color=("gray40", "gray30")
        ).pack(side="left", padx=5)

    def _browse_key(self, entry):
        """浏览密钥文件"""
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
        """关闭应用"""
        if self._current_page == "status":
            self._status_panel.stop_auto_refresh()
        self._ssh.disconnect()
        self.destroy()
