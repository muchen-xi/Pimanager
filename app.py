"""
PiManager 主应用窗口
"""
import customtkinter as ctk
import threading
import os
import logging
from pathlib import Path
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk

from .config import load_config, save_config
from .ssh_client import SSHClient
from .status_panel import StatusPanel
from .file_browser import FileBrowser
from .terminal_page import TerminalPage
from .settings_page import SettingsPage
from .theme import ThemeColors


# ============================================================
#  BackgroundManager — 全局背景管理
#  原理：拦截所有 CTk 控件 _draw()，将 inner_parts 透明化
#  并把背景图片片段绘制到 canvas 底部。
#  对所有处于 _content 区域内的控件自动生效。
# ============================================================
class BackgroundManager:
    """全局背景管理器 — Canvas 统一背景绘制。

    通过 monkey-patch CTk 控件 _draw()，在控件绘制后：
    1) 清除控件 canvas 上的不透明背景项（inner_parts 等）
    2) 从混合背景图裁剪对应位置的片段，绘制到控件 canvas 底部
    3) 同步 CTkTextbox/CTkEntry 内部 tk widget 的背景色

    只作用于 _content 区域内（排除侧边栏、对话框、以及 exclude_widget 标记的控件）。
    Canvas 自绘组件（CanvasTerminalOutput / CanvasFileList）自行调用
    _make_canvas_transparent 绘制背景片段。
    """

    _bg_path: str = ""
    _bg_pil = None
    _bg_tk_full = None
    _bg_opacity: float = 0.15
    _content_frame = None
    _refs: list = []
    _enabled: bool = False
    _original_draws: dict = {}
    _excluded_widgets: set = set()
    _processed_canvases: dict = {}  # canvas id → (width, height) 缓存
    _blended_cache: dict = {}  # ★ (bg_path, opacity, size) → PIL Image 缓存
    _batch_mode: bool = False  # ★ 批量模式：跳过逐控件回调，最后统一刷新

    # ========== 公开 API ==========

    @classmethod
    def setup(cls, content_frame):
        """应用启动时调用一次：拦截所有 CTk 控件 _draw()。"""
        cls._content_frame = content_frame
        if not cls._original_draws:
            for wc in (
                ctk.CTkFrame, ctk.CTkTextbox, ctk.CTkEntry,
                ctk.CTkButton, ctk.CTkLabel, ctk.CTkOptionMenu,
                ctk.CTkComboBox, ctk.CTkCheckBox, ctk.CTkSlider,
                ctk.CTkProgressBar, ctk.CTkSwitch,
            ):
                if wc in cls._original_draws:
                    continue
                _orig = wc._draw
                cls._original_draws[wc] = _orig

                def _patched(_o):
                    def _draw(self_w, no_color_updates=False):
                        _o(self_w, no_color_updates)
                        cls._on_widget_draw(self_w)
                    return _draw

                wc._draw = _patched(_orig)

    @classmethod
    def set_background(cls, path: str, opacity: float):
        """设置/更换背景图片。"""
        cls._bg_path = path
        cls._bg_opacity = opacity
        cls._refs.clear()
        if path and os.path.exists(path):
            try:
                # ★ 验证图片文件是否可正常打开
                cls._bg_pil = Image.open(path)
                cls._bg_pil.verify()  # 验证图片完整性
                cls._bg_pil = Image.open(path)  # verify 后需要重新打开
                cls._enabled = True
                cls._processed_canvases.clear()
                cls._blended_cache.clear()  # ★ 清除混合缓存
                cls._prepare_full_image()
                cls._refresh_all()
            except Exception as e:
                cls._enabled = False
                cls._bg_pil = None
                logging.warning(f"无法加载背景图片 {path}: {e}")
                messagebox.showwarning("背景加载失败",
                    f"无法加载图片文件，文件可能已损坏。\n{os.path.basename(path)}\n错误: {e}")
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
        cls._blended_cache.clear()
        if cls._content_frame:
            cls._clear_all(cls._content_frame)
            cls._refresh_all()

    @classmethod
    def refresh_size(cls):
        """窗口大小改变后重新缩放并重绘背景。"""
        if cls._enabled and cls._bg_pil:
            cls._processed_canvases.clear()
            cls._blended_cache.clear()
            cls._prepare_full_image()
            # ★ 延迟清理尺寸缓存，避免频繁重复绘制
            cls._content_frame.after(100, lambda: cls._processed_canvases.clear())
            cls._refresh_all()

    @classmethod
    def exclude_widget(cls, widget):
        """将控件及其后代排除出背景处理（如设置页）。"""
        cls._excluded_widgets.add(widget)

    @classmethod
    def get_blended_image(cls):
        """返回混合后的 PIL Image 引用（供 Canvas 组件使用）。"""
        return getattr(cls, '_bg_pil_blended', None)

    @classmethod
    def get_content_frame(cls):
        """返回内容区引用（供 Canvas 组件计算坐标）。"""
        return cls._content_frame

    # ========== 核心：Canvas 透明化 + 背景片段绘制 ==========

    @classmethod
    def make_canvas_transparent(cls, canvas, force: bool = False):
        """对一个 tk.Canvas 进行透明化 + 绘制背景片段。

        force=True 时跳过尺寸缓存，强制重绘（用于 resize 等场景）。
        """
        if not cls._enabled or not cls._content_frame:
            return
        try:
            if not canvas.winfo_exists():
                return
            pw, ph = canvas.winfo_width(), canvas.winfo_height()
            if pw < 3 or ph < 3:
                return

            # ★ 尺寸缓存：同尺寸跳过，减少重复绘制
            cid = id(canvas)
            cached = cls._processed_canvases.get(cid)
            if not force and cached == (pw, ph):
                return
            cls._processed_canvases[cid] = (pw, ph)

            # ★ 优化：只清除实际存在的 tag
            for tag in ("inner_parts", "bg_parts", "background_parts", "background", "bg"):
                try:
                    # 检查 tag 是否存在再操作
                    if canvas.find_withtag(tag):
                        canvas.itemconfig(tag, fill="", outline="")
                except Exception:
                    pass
            canvas.delete("background_parts")

            # 坐标换算 → 裁剪背景片段 → 绘制
            wx = canvas.winfo_rootx() - cls._content_frame.winfo_rootx()
            wy = canvas.winfo_rooty() - cls._content_frame.winfo_rooty()
            pil_full = getattr(cls, '_bg_pil_blended', None)
            if pil_full is None:
                return
            left, top = max(0, int(wx)), max(0, int(wy))
            right = min(pil_full.width, int(wx + pw))
            bottom = min(pil_full.height, int(wy + ph))
            if right <= left or bottom <= top:
                return

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
    def sample_bg_color(cls, wx, wy, cw, ch) -> str:
        """从混合背景图采样颜色 (hex)，供外部组件使用。"""
        pil_full = getattr(cls, '_bg_pil_blended', None)
        if pil_full is None:
            return "#0D1117"
        try:
            left, top = max(0, int(wx)), max(0, int(wy))
            right = min(pil_full.width, int(wx + cw))
            bottom = min(pil_full.height, int(wy + ch))
            if right <= left or bottom <= top:
                return "#0D1117"
            region = pil_full.crop((left, top, right, bottom))
            region = region.resize((1, 1), Image.LANCZOS)
            pixel = region.getpixel((0, 0))
            r, g, b = pixel[0], pixel[1], pixel[2]
            return f'#{r:02x}{g:02x}{b:02x}'
        except Exception:
            return "#0D1117"

    # ========== 内部实现 ==========

    @classmethod
    def _prepare_full_image(cls):
        if not cls._bg_pil or not cls._content_frame:
            return
        cw = cls._content_frame.winfo_width()
        ch = cls._content_frame.winfo_height()
        if cw < 50 or ch < 50:
            cw, ch = 900, 660

        # ★ 缓存混合结果：相同 (路径, 透明度, 尺寸) 不重复混合
        cache_key = (cls._bg_path, cls._bg_opacity, cw, ch)
        cached = cls._blended_cache.get(cache_key)
        if cached is not None:
            cls._bg_pil_blended = cached
            cls._bg_tk_full = ImageTk.PhotoImage(cached)
            return

        bg = cls._bg_pil.resize((cw, ch), Image.LANCZOS).convert("RGBA")
        dark = Image.new("RGBA", (cw, ch), (13, 17, 23, 255))
        blended = Image.blend(dark.convert("RGB"), bg.convert("RGB"), cls._bg_opacity)
        cls._bg_pil_blended = blended
        cls._blended_cache[cache_key] = blended  # ★ 缓存
        cls._bg_tk_full = ImageTk.PhotoImage(blended)

    @classmethod
    def _on_widget_draw(cls, widget):
        """控件 _draw() 后回调：透明化 canvas + 绘制背景片段 + 同步内部 widget bg。

        批量模式下跳过（由 _force_draw 最后统一处理），避免 N 次递归触发。
        """
        if cls._batch_mode:
            return
        if not cls._enabled or not cls._bg_tk_full:
            return
        if not cls._content_frame:
            return
        if not cls._is_descendant_of_content(widget):
            return

        if not hasattr(widget, '_canvas'):
            return

        try:
            c = widget._canvas
            if not c.winfo_exists():
                return
            cw, ch = c.winfo_width(), c.winfo_height()
            if cw < 3 or ch < 3:
                return

            cls.make_canvas_transparent(c)

            wx = c.winfo_rootx() - cls._content_frame.winfo_rootx()
            wy = c.winfo_rooty() - cls._content_frame.winfo_rooty()
            cls._sync_inner_widget_bg(widget, wx, wy, cw, ch)
        except Exception:
            pass

    @classmethod
    def _sync_inner_widget_bg(cls, widget, wx, wy, cw, ch):
        """同步 CTkTextbox/CTkEntry 内部 tk widget 背景色。"""
        color = cls.sample_bg_color(wx, wy, cw, ch)
        insert_color = ThemeColors.get("canvas_text")
        if isinstance(widget, ctk.CTkTextbox) and hasattr(widget, '_textbox'):
            try:
                widget._textbox.configure(
                    bg=color, highlightthickness=0, borderwidth=0,
                    insertbackground=insert_color)
            except Exception:
                pass
        if isinstance(widget, ctk.CTkEntry) and hasattr(widget, '_entry'):
            try:
                widget._entry.configure(
                    bg=color, highlightthickness=0, borderwidth=0,
                    insertbackground=insert_color, relief="flat")
            except Exception:
                pass

    @classmethod
    def _refresh_all(cls):
        if cls._content_frame:
            cls._force_draw(cls._content_frame)

    @classmethod
    def _force_draw(cls, widget):
        """递归触发所有后代控件 _draw()，批量模式避免 N 次背景重绘。"""
        cls._batch_mode = True
        try:
            cls._force_draw_impl(widget)
        finally:
            cls._batch_mode = False
            # 批量完成后统一刷新一次所有背景
            cls._batch_refresh_backgrounds(widget)

    @classmethod
    def _force_draw_impl(cls, widget):
        """递归 _draw()（不触发逐控件背景重绘）。"""
        try:
            if hasattr(widget, '_draw'):
                widget._draw()
        except Exception:
            pass
        if hasattr(widget, 'winfo_children'):
            for child in widget.winfo_children():
                cls._force_draw_impl(child)

    @classmethod
    def _batch_refresh_backgrounds(cls, widget):
        """_force_draw 完成后统一刷新所有 Canvas 背景（一次遍历）。"""
        try:
            if hasattr(widget, '_canvas'):
                try:
                    c = widget._canvas
                    if c.winfo_exists():
                        cw, ch = c.winfo_width(), c.winfo_height()
                        if cw >= 3 and ch >= 3:
                            cls.make_canvas_transparent(c, force=True)
                            wx = c.winfo_rootx() - cls._content_frame.winfo_rootx()
                            wy = c.winfo_rooty() - cls._content_frame.winfo_rooty()
                            cls._sync_inner_widget_bg(widget, wx, wy, cw, ch)
                except Exception:
                    pass
        except Exception:
            pass
        if hasattr(widget, 'winfo_children'):
            for child in widget.winfo_children():
                cls._batch_refresh_backgrounds(child)

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
    def _clear_all(cls, widget):
        if hasattr(widget, '_canvas'):
            try:
                widget._canvas.delete("bg_image")
            except Exception:
                pass
        if hasattr(widget, 'winfo_children'):
            for child in widget.winfo_children():
                cls._clear_all(child)


# ============================================================
#  统一卡片工厂函数
# ============================================================

def make_card(master, title: str = "", row: int = 0, column: int = 0,
              sticky: str = "ew", columnspan: int = 1, **grid_kw) -> ctk.CTkFrame:
    """创建统一的卡片容器 — 透明背景 + 细边框，背景图穿透。

    Returns:
        CTkFrame: 卡片容器（已 grid 到 master）
    """
    frame = ctk.CTkFrame(
        master, fg_color="transparent", border_width=1,
        border_color=ThemeColors.get("card_border"), corner_radius=8)
    frame.grid(row=row, column=column, columnspan=columnspan,
               sticky=sticky, **grid_kw)
    if title:
        ctk.CTkLabel(
            frame, text=title,
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w",
        ).pack(anchor="w", padx=10, pady=(6, 2))
    return frame


# ============================================================
#  PiManagerApp — 主应用窗口
# ============================================================

class PiManagerApp(ctk.CTk):
    """PiManager 主应用"""

    def __init__(self):
        super().__init__()

        # 初始化日志
        self._setup_logging()

        # 初始化
        self._config = load_config()
        self._ssh = SSHClient()
        self._resize_after_id = None
        self._connect_time = None  # ★ 连接时间

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
        self._build_status_bar()

        # 显示首页
        self._show_page("status")

        # 自动连接
        if self._config.get("behavior", {}).get("auto_connect", False):
            self.after(500, self._auto_connect)

        # ★ 启动状态栏时钟
        self._update_status_clock()

    def _setup_logging(self):
        """配置日志系统。"""
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
    #  侧边栏
    # ============================================================

    def _build_sidebar(self):
        """构建侧边栏"""
        sidebar = self._sidebar

        # ---- Row 0: Logo / 标题 ----
        title_frame = ctk.CTkFrame(sidebar)
        title_frame.grid(row=0, column=0, sticky="ew", padx=15, pady=(20, 8))
        ctk.CTkLabel(title_frame, text="🥧", font=ctk.CTkFont(size=36)).pack(pady=(0, 5))
        ctk.CTkLabel(title_frame, text="PiManager",
                     font=ctk.CTkFont(size=18, weight="bold")).pack()

        # ---- Row 1: 连接状态 ----
        status_frame = ctk.CTkFrame(
            sidebar, fg_color=("gray85", "gray17"), corner_radius=8)
        status_frame.grid(row=1, column=0, sticky="ew", padx=15, pady=(0, 8))
        self._conn_indicator = ctk.CTkLabel(
            status_frame, text="🔴 未连接", font=ctk.CTkFont(size=12))
        self._conn_indicator.pack(pady=(8, 2))
        self._conn_host = ctk.CTkLabel(
            status_frame, text="", font=ctk.CTkFont(size=11), text_color="gray")
        self._conn_host.pack(pady=(0, 8))

        # ---- Row 2: 连接按钮 ----
        btn_frame = ctk.CTkFrame(sidebar)
        btn_frame.grid(row=2, column=0, sticky="ew", padx=15, pady=(0, 6))
        self._btn_connect = ctk.CTkButton(
            btn_frame, text="🔌 连接", command=self._toggle_connection,
            height=32, fg_color="#2B5B2B", hover_color="#3A7A3A")
        self._btn_connect.pack(fill="x", pady=2)
        self._btn_settings_conn = ctk.CTkButton(
            btn_frame, text="⚙️ 连接设置", command=self._show_conn_settings,
            height=28, fg_color="transparent", border_width=1,
            border_color=("gray40", "gray30"), font=ctk.CTkFont(size=12))
        self._btn_settings_conn.pack(fill="x", pady=2)

        # ---- Row 3: 分隔线 ----
        ctk.CTkFrame(sidebar, height=1, fg_color=("gray70", "gray30")).grid(
            row=3, column=0, sticky="ew", padx=20, pady=5)

        # ---- Row 4: 系统状态卡片（连接后显示实时数据） ----
        self._sys_card = ctk.CTkFrame(sidebar, corner_radius=8)
        self._sys_card.grid(row=4, column=0, sticky="ew", padx=15, pady=(0, 5))
        ctk.CTkLabel(self._sys_card, text="📡 实时状态",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     anchor="w").pack(anchor="w", padx=10, pady=(8, 4))

        # CPU
        cpu_row = ctk.CTkFrame(self._sys_card, fg_color="transparent")
        cpu_row.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(cpu_row, text="🔥 CPU", font=ctk.CTkFont(size=11),
                     width=55, anchor="w").pack(side="left")
        self._sidebar_cpu = ctk.CTkProgressBar(cpu_row, width=90, height=8)
        self._sidebar_cpu.pack(side="left", padx=4)
        self._sidebar_cpu.set(0)
        self._sidebar_cpu_pct = ctk.CTkLabel(cpu_row, text="--", width=36,
                                              font=ctk.CTkFont(size=10), anchor="e")
        self._sidebar_cpu_pct.pack(side="left")

        # RAM
        ram_row = ctk.CTkFrame(self._sys_card, fg_color="transparent")
        ram_row.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(ram_row, text="🧠 RAM", font=ctk.CTkFont(size=11),
                     width=55, anchor="w").pack(side="left")
        self._sidebar_ram = ctk.CTkProgressBar(ram_row, width=90, height=8)
        self._sidebar_ram.pack(side="left", padx=4)
        self._sidebar_ram.set(0)
        self._sidebar_ram_text = ctk.CTkLabel(ram_row, text="--", width=36,
                                               font=ctk.CTkFont(size=10), anchor="e")
        self._sidebar_ram_text.pack(side="left")

        # 网络 IP
        net_row = ctk.CTkFrame(self._sys_card, fg_color="transparent")
        net_row.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(net_row, text="🌐 IP", font=ctk.CTkFont(size=11),
                     width=55, anchor="w").pack(side="left")
        self._sidebar_ip = ctk.CTkLabel(net_row, text="--",
                                         font=ctk.CTkFont(size=10), anchor="w",
                                         text_color="gray")
        self._sidebar_ip.pack(side="left", padx=4)

        # 温度
        temp_row = ctk.CTkFrame(self._sys_card, fg_color="transparent")
        temp_row.pack(fill="x", padx=10, pady=(2, 6))
        ctk.CTkLabel(temp_row, text="🌡️ 温度", font=ctk.CTkFont(size=11),
                     width=55, anchor="w").pack(side="left")
        self._sidebar_temp = ctk.CTkLabel(temp_row, text="--°C",
                                           font=ctk.CTkFont(size=11, weight="bold"),
                                           anchor="w")
        self._sidebar_temp.pack(side="left", padx=4)
        self._sys_card.grid_remove()  # 未连接时隐藏

        # ---- Row 5: 分隔线 ----
        self._sep2 = ctk.CTkFrame(sidebar, height=1, fg_color=("gray70", "gray30"))
        self._sep2.grid(row=5, column=0, sticky="ew", padx=20, pady=5)

        # ---- Row 6-9: 导航按钮 ----
        nav_items = [
            ("📊  系统状态", "status"),
            ("📁  文件管理", "files"),
            ("💻  命令终端", "terminal"),
            ("⚙️  应用设置", "settings"),
        ]
        self._nav_buttons = {}
        for i, (text, page_id) in enumerate(nav_items):
            btn = ctk.CTkButton(
                sidebar, text=text, anchor="w", height=36,
                fg_color="transparent", hover_color=("gray75", "gray25"),
                font=ctk.CTkFont(size=13),
                command=lambda p=page_id: self._show_page(p))
            btn.grid(row=6 + i, column=0, sticky="ew", padx=15, pady=2)
            self._nav_buttons[page_id] = btn

        # ---- Row 10+: 电源按钮 ----
        power_frame = ctk.CTkFrame(sidebar)
        power_frame.grid(row=11, column=0, sticky="ew", padx=15, pady=(8, 2))
        self._btn_reboot = ctk.CTkButton(
            power_frame, text="🔄 重启", command=self._reboot_pi,
            height=28, fg_color="transparent", border_width=1,
            border_color=("gray40", "gray30"), font=ctk.CTkFont(size=12),
            state="disabled")
        self._btn_reboot.pack(side="left", fill="x", expand=True, padx=(0, 2))
        self._btn_shutdown = ctk.CTkButton(
            power_frame, text="⏻ 关机", command=self._shutdown_pi,
            height=28, fg_color="#8B0000", hover_color="#A00000",
            font=ctk.CTkFont(size=12), state="disabled")
        self._btn_shutdown.pack(side="right", fill="x", expand=True, padx=(2, 0))

        # ---- Row 12: 版本 ----
        ctk.CTkLabel(sidebar, text="v1.3.3", text_color="gray",
                     font=ctk.CTkFont(size=10)).grid(
            row=12, column=0, pady=(6, 10))

        # 侧边栏滚动
        sidebar.grid_rowconfigure(13, weight=1)

    def _highlight_nav(self, page_id: str):
        """高亮当前导航按钮 — 使用主题颜色"""
        for pid, btn in self._nav_buttons.items():
            if pid == page_id:
                btn.configure(fg_color=ThemeColors.get("nav_active"))
            else:
                btn.configure(fg_color="transparent")

    # ============================================================
    #  状态栏
    # ============================================================

    def _build_status_bar(self):
        """构建增强状态栏 — 左侧状态 + 中间连接时长 + 右侧时钟"""
        self._status_bar = ctk.CTkFrame(self, height=32, corner_radius=0)
        self._status_bar.grid(row=1, column=1, sticky="ew")
        self._status_bar.grid_columnconfigure(1, weight=1)

        # 左侧：状态文字
        self._status_label = ctk.CTkLabel(
            self._status_bar, text="就绪", anchor="w",
            font=ctk.CTkFont(size=11))
        self._status_label.grid(row=0, column=0, padx=(10, 5), sticky="w")

        # 中间：连接时长
        self._status_duration = ctk.CTkLabel(
            self._status_bar, text="", anchor="w",
            font=ctk.CTkFont(size=10), text_color="gray")
        self._status_duration.grid(row=0, column=1, padx=5, sticky="w")

        # 右侧：时钟
        self._status_clock = ctk.CTkLabel(
            self._status_bar, text="", anchor="e",
            font=ctk.CTkFont(size=11), text_color="gray")
        self._status_clock.grid(row=0, column=2, padx=10, sticky="e")

    def _update_status_clock(self):
        """更新状态栏时钟（每分钟）。"""
        import datetime
        now = datetime.datetime.now()
        self._status_clock.configure(text=now.strftime("%Y-%m-%d %H:%M"))

        # 更新连接时长
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
            self.after(50, lambda: BackgroundManager._force_draw(page))

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
        """窗口大小改变时更新背景（防抖 250ms）。"""
        if not hasattr(self, '_content'):
            return
        try:
            cw = self._content.winfo_width()
            ch = self._content.winfo_height()
        except Exception:
            return  # 窗口已销毁
        if cw < 50 or ch < 50:
            return
        last_size = getattr(self, '_bg_last_size', (0, 0))
        if (cw, ch) == last_size:
            return
        self._bg_last_size = (cw, ch)
        if hasattr(self, '_resize_after_id') and self._resize_after_id:
            self.after_cancel(self._resize_after_id)
        # ★ 防抖 250ms（从 150ms 增加）
        self._resize_after_id = self.after(250, lambda: BackgroundManager.refresh_size())

    def _apply_background(self, force=False):
        """应用背景图片"""
        bg_path = self._config["appearance"].get("background_path", "")
        opacity = self._config["appearance"].get("background_opacity", 0.15)
        BackgroundManager.set_background(bg_path, float(opacity))

    def _refresh_all_canvas(self):
        """主题/字体变更后强制刷新所有 Canvas 渲染组件。"""
        # 强制 BackgroundManager 重绘（清除缓存）
        BackgroundManager._processed_canvases.clear()
        BackgroundManager._blended_cache.clear()
        if BackgroundManager._enabled:
            BackgroundManager._prepare_full_image()
            BackgroundManager._refresh_all()
        # 强制所有页面 Canvas 文本内容重绘
        self.update_idletasks()
        for page in self._pages.values():
            if page.winfo_ismapped():
                BackgroundManager._force_draw(page)
        # Canvas 自绘组件统一刷新主题（bg + 文本颜色）
        if hasattr(self, '_file_browser') and self._file_browser.winfo_exists():
            self._file_browser._file_list.refresh_theme()
            if self._file_browser._mode == "dual":
                self._file_browser._local_list.refresh_theme()
        if hasattr(self, '_terminal_page') and self._terminal_page.winfo_exists():
            for tab in self._terminal_page._tabs:
                try:
                    tab._output.refresh_theme()
                except Exception:
                    pass

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
        import datetime
        if ok:
            self._connect_time = datetime.datetime.now()  # ★ 记录连接时间
            self._conn_indicator.configure(text="🟢 已连接")
            self._conn_host.configure(text=f"{self._ssh.host}")
            self._btn_connect.configure(text="🔌 断开", state="normal",
                                        fg_color="#8B0000", hover_color="#A00000")
            self._status_label.configure(text="已连接")
            self._sys_card.grid()  # 显示系统状态卡片
            self._btn_reboot.configure(state="normal")
            self._btn_shutdown.configure(state="normal")
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
            self._conn_indicator.configure(text="🔴 连接失败")
            self._conn_host.configure(text=msg)
            self._btn_connect.configure(text="🔌 连接", state="normal",
                                        fg_color="#2B5B2B", hover_color="#3A7A3A")
            self._status_label.configure(text="连接失败")
            logging.warning(f"连接失败: {msg}")
            messagebox.showerror("连接失败", msg)

    def _on_disconnected(self):
        """断开连接回调"""
        self._connect_time = None
        self._status_duration.configure(text="")
        self._conn_indicator.configure(text="🔴 未连接")
        self._conn_host.configure(text="")
        self._btn_connect.configure(text="🔌 连接", state="normal",
                                    fg_color="#2B5B2B", hover_color="#3A7A3A")
        self._status_label.configure(text="已断开")
        self._sys_card.grid_remove()
        self._btn_reboot.configure(state="disabled")
        self._btn_shutdown.configure(state="disabled")
        self._stop_sidebar_refresh()
        if self._current_page == "status":
            self._status_panel.stop_auto_refresh()
        logging.info("已断开连接")

    # ============================================================
    #  侧边栏系统状态刷新
    # ============================================================

    def _refresh_sidebar_stats(self):
        """刷新侧边栏 CPU/RAM/IP/温度（1 次 SSH 往返）"""
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
        """更新侧边栏 UI"""
        ok, warn, danger = (ThemeColors.get(k) for k in
                            ("status_ok", "warning", "warning_strong"))

        # CPU
        self._sidebar_cpu.set(cpu / 100)
        self._sidebar_cpu_pct.configure(text=f"{cpu:.0f}%")
        self._sidebar_cpu.configure(progress_color=(
            ok if cpu < 50 else warn if cpu < 80 else danger))

        # RAM
        self._sidebar_ram.set(mem_pct / 100)
        self._sidebar_ram_text.configure(text=f"{mem_pct:.0f}%")
        self._sidebar_ram.configure(progress_color=(
            ok if mem_pct < 50 else warn if mem_pct < 80 else danger))

        # IP
        self._sidebar_ip.configure(text=ip_addr)

        # 温度
        if temp >= 70:
            temp_color = danger
        elif temp >= 50:
            temp_color = warn
        else:
            temp_color = ok
        self._sidebar_temp.configure(text=f"{temp:.1f}°C", text_color=temp_color)

    def _start_sidebar_refresh(self):
        """启动侧边栏自动刷新（每 3 秒）"""
        self._stop_sidebar_refresh()
        self._do_sidebar_refresh()

    def _do_sidebar_refresh(self):
        """执行自动刷新"""
        if self._ssh.connected:
            self._refresh_sidebar_stats()
        self._sidebar_refresh_job = self.after(3000, self._do_sidebar_refresh)

    def _stop_sidebar_refresh(self):
        """停止侧边栏自动刷新"""
        if hasattr(self, '_sidebar_refresh_job') and self._sidebar_refresh_job:
            self.after_cancel(self._sidebar_refresh_job)
            self._sidebar_refresh_job = None

    # ============================================================
    #  电源控制
    # ============================================================

    def _shutdown_pi(self):
        """关机"""
        if not self._ssh.connected:
            return
        if not messagebox.askyesno(
            "⚠️ 确认关机",
            "确定要关闭树莓派吗？\n\n关机后需手动重新上电才能启动。",
            icon="warning"):
            return
        def _do():
            self._ssh.exec_command("sudo shutdown -h now", timeout=5)
        threading.Thread(target=_do, daemon=True).start()
        self._status_label.configure(text="已发送关机命令")
        logging.info("发送关机命令")
        messagebox.showinfo("已发送", "关机命令已发送，树莓派即将关闭")

    def _reboot_pi(self):
        """重启"""
        if not self._ssh.connected:
            return
        if not messagebox.askyesno(
            "⚠️ 确认重启",
            "确定要重启树莓派吗？\n\n重启期间连接将断开，约 30 秒后可重新连接。",
            icon="warning"):
            return
        def _do():
            self._ssh.exec_command("sudo shutdown -r now", timeout=5)
        threading.Thread(target=_do, daemon=True).start()
        self._status_label.configure(text="已发送重启命令")
        logging.info("发送重启命令")
        messagebox.showinfo("已发送", "重启命令已发送，树莓派即将重启")

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
        self._stop_sidebar_refresh()
        if hasattr(self, '_status_clock_job'):
            self.after_cancel(self._status_clock_job)
        if hasattr(self, '_resize_after_id') and self._resize_after_id:
            self.after_cancel(self._resize_after_id)
        self.unbind("<Configure>")  # 防止关闭后触发 _on_window_resize
        if self._current_page == "status":
            self._status_panel.stop_auto_refresh()
        self._ssh.disconnect()
        logging.info("应用关闭")
        self.destroy()
