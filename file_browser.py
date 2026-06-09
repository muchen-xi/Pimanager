"""
PiManager 文件浏览器 - 远程文件管理（浏览/上传/下载/删除/重命名/运行）
"""
import customtkinter as ctk
import threading
import os
import shlex
import datetime
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, Menu
from .theme import ThemeColors


# ===== Canvas 列表公共基类（消除 CanvasFileList / LocalFileList 重复代码） =====

class _CanvasListBase(ctk.CTkFrame):
    """Canvas 文件列表基类 — 统一滚动、渲染、背景绘制逻辑。

    子类只需实现：refresh/navigate 等数据获取方法。
    """

    @property
    def _row_height(self) -> int:
        """行高（跟随字体缩放动态计算）。"""
        return int(self._base_row_height * ThemeColors.get_font_scale())

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", corner_radius=0, **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # 内部 tk.Canvas（背景色跟随主题）
        self._canvas = tk.Canvas(
            self, highlightthickness=0, bd=0,
            bg=ThemeColors.get("canvas_bg"))
        self._canvas.grid(row=0, column=0, sticky="nsew")

        # 数据
        self._items: list[dict] = []
        self._base_row_height = 32
        self._selected_idx = -1
        self._pad_x = 8
        self._scroll_y = 0

        # 回调（由外部设置）
        self.on_click = None       # (index, item)
        self.on_double_click = None  # (item)
        self.on_right_click = None   # (event, item)

        # ★ 滚轮事件绑定到容器 Frame（修复 Windows 焦点问题）
        self.bind("<MouseWheel>", self._on_mousewheel)
        self._canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.bind("<Button-4>", lambda e: self._scroll(-60))
        self.bind("<Button-5>", lambda e: self._scroll(60))
        self._canvas.bind("<Button-4>", lambda e: self._scroll(-60))
        self._canvas.bind("<Button-5>", lambda e: self._scroll(60))

        # 点击事件
        self._canvas.bind("<Button-1>", self._on_canvas_click)
        self._canvas.bind("<Double-Button-1>", self._on_canvas_double)
        self._canvas.bind("<Button-3>", self._on_canvas_right)
        self.bind("<Configure>", self._on_resize)

        # 背景引用
        self._bg_refs = []

    # ===== 子类覆盖 =====

    def _file_icon(self, item: dict) -> str:
        """文件图标 — 子类可覆盖。"""
        name = item["name"]
        if item["is_dir"]:
            return "📁"
        ext_map = {
            ".py": "🐍", ".py3": "🐍", ".sh": "📜", ".bash": "📜",
            ".txt": "📝", ".md": "📝", ".log": "📝",
            ".conf": "📝", ".cfg": "📝", ".json": "📝",
            ".jpg": "🖼️", ".jpeg": "🖼️", ".png": "🖼️",
            ".gif": "🖼️", ".bmp": "🖼️", ".webp": "🖼️",
            ".zip": "📦", ".tar": "📦", ".gz": "📦",
            ".bz2": "📦", ".xz": "📦", ".7z": "📦",
            ".mp3": "🎵", ".wav": "🎵", ".ogg": "🎵", ".flac": "🎵",
            ".mp4": "🎬", ".avi": "🎬", ".mkv": "🎬", ".mov": "🎬",
        }
        for ext, icon in ext_map.items():
            if name.endswith(ext):
                return icon
        return "📄"

    def _format_size(self, item: dict) -> str:
        """文件大小格式化 — 子类可覆盖。"""
        if item["is_dir"]:
            return "--"
        size = item["size"]
        if size >= 1073741824:
            return f"{size/1073741824:.1f} GB"
        elif size >= 1048576:
            return f"{size/1048576:.1f} MB"
        elif size >= 1024:
            return f"{size/1024:.1f} KB"
        return f"{size} B"

    def _get_name_color(self, item: dict) -> str:
        """文件名颜色 — 子类可覆盖（如本地文件用蓝色）。"""
        return ThemeColors.get("canvas_text")

    def refresh_theme(self):
        """主题切换后刷新 Canvas 背景色。"""
        self._canvas.configure(bg=ThemeColors.get("canvas_bg"))
        self._redraw()

    # ===== 公共 API =====

    def set_items(self, items: list[dict]):
        """设置文件列表数据。"""
        self._items = items
        self._selected_idx = -1
        self._scroll_y = 0
        self._redraw()

    def get_selected(self):
        """返回当前选中项。"""
        if 0 <= self._selected_idx < len(self._items):
            return self._items[self._selected_idx]
        return None

    # ===== 渲染 =====

    def _apply_bg(self):
        """绘制背景图片片段到 canvas。"""
        try:
            from .app import BackgroundManager
            BackgroundManager.make_canvas_transparent(self._canvas)
        except Exception:
            pass

    def _redraw(self):
        """重绘可见行。"""
        c = self._canvas

        if not self._items:
            c.delete("row")
            c.delete("scrollbar")
            return

        # ★ 从容器 frame 取尺寸（CTk保证先layout），Canvas 跟随 sticky=nsew
        cw = self.winfo_width()
        ch = self.winfo_height()
        # 备用：从 canvas 取
        if cw < 20:
            cw = c.winfo_width()
        if ch < 20:
            ch = c.winfo_height()
        # 最后手段：要求尺寸
        if cw < 20:
            cw = self.winfo_reqwidth()
        if ch < 20:
            ch = max(200, self.winfo_reqheight())
        # 还不行就等一帧（极少情况）
        if cw < 20 or ch < 20:
            if not getattr(self, '_size_retry_scheduled', False):
                self._size_retry_scheduled = True
                self.after(30, self._size_retry_redraw)
            return

        c.delete("row")
        c.delete("scrollbar")
        self._apply_bg()

        # 列宽（窄窗口下按比例缩放，防止时间列溢出）
        if cw < 500:
            col_size = max(50, int(cw * 0.18))
            col_time = max(80, int(cw * 0.32))
        else:
            col_size = 90
            col_time = 160
        col_name = max(100, cw - col_size - col_time - self._pad_x * 4)

        total = len(self._items)
        total_h = total * self._row_height
        visible = max(1, ch // self._row_height)

        # 限制滚动范围
        max_scroll = max(0, total_h - ch)
        self._scroll_y = max(0, min(self._scroll_y, max_scroll))

        start_idx = self._scroll_y // self._row_height
        end_idx = min(total, start_idx + visible + 1)
        offset_y = -(self._scroll_y % self._row_height)

        for i in range(start_idx, end_idx):
            y = offset_y + (i - start_idx) * self._row_height
            item = self._items[i]

            is_selected = (i == self._selected_idx)

            # 选中高亮
            if is_selected:
                c.create_rectangle(
                    0, y, cw, y + self._row_height,
                    fill=ThemeColors.get("canvas_selection"), outline="",
                    tags=("row", f"row_{i}"))

            # 图标
            icon = self._file_icon(item)
            name_x = self._pad_x + 4
            name_color = self._get_name_color(item)
            name_font = ThemeColors.scaled_font("Segoe UI", 12)
            dim_font = ThemeColors.scaled_font("Segoe UI", 11)
            c.create_text(
                name_x, y + self._row_height // 2,
                text=f"{icon}  {item['name']}", anchor="w",
                fill=name_color, font=name_font,
                tags=("row", f"row_{i}"))

            # 大小
            dim_color = ThemeColors.get("canvas_text_dim")
            size_x = self._pad_x + col_name + 10
            c.create_text(
                size_x + col_size, y + self._row_height // 2,
                text=self._format_size(item), anchor="e",
                fill=dim_color, font=dim_font,
                tags=("row", f"row_{i}"))

            # 时间
            time_x = size_x + col_size + col_time + 10
            try:
                ts = datetime.datetime.fromtimestamp(item["mtime"]).strftime(
                    "%Y-%m-%d %H:%M")
            except Exception:
                ts = "--"
            c.create_text(
                time_x, y + self._row_height // 2,
                text=ts, anchor="e",
                fill=dim_color, font=dim_font,
                tags=("row", f"row_{i}"))

        # 滚动条指示
        if total > visible:
            bar_w = 4
            bar_x = cw - bar_w - 4
            bar_h = max(20, int(ch * visible / total))
            bar_y = int((ch - bar_h) * self._scroll_y / max(1, max_scroll))
            c.create_rectangle(
                bar_x, bar_y, bar_x + bar_w, bar_y + bar_h,
                fill=ThemeColors.get("scrollbar"), outline="", tags="scrollbar")

    def _size_retry_redraw(self):
        """尺寸不足时的延迟重试（仅一次）。"""
        self._size_retry_scheduled = False
        self._redraw()

    def _on_resize(self, event=None):
        """窗口尺寸变化时防抖重绘（避免瞬间几十次 Configure 事件卡死 UI）。"""
        if event and event.widget is not self:
            return
        if hasattr(self, '_resize_after'):
            self.after_cancel(self._resize_after)
        self._resize_after = self.after(80, self._redraw)

    # ===== 滚动 =====

    def _scroll(self, dy: int):
        self._scroll_y += dy
        self._redraw()

    def _on_mousewheel(self, event):
        """统一鼠标滚轮处理。"""
        if hasattr(event, 'num') and event.num == 4:
            self._scroll(-40)
        elif hasattr(event, 'num') and event.num == 5:
            self._scroll(40)
        elif hasattr(event, 'delta'):
            lines = int(event.delta / 40)
            self._scroll(-lines if lines != 0 else (-1 if event.delta > 0 else 1))

    # ===== 行定位 =====

    def _get_row_at_y(self, y: int) -> int:
        idx = (self._scroll_y + y) // self._row_height
        if 0 <= idx < len(self._items):
            return idx
        return -1

    # ===== 鼠标事件 =====

    def _on_canvas_click(self, event):
        idx = self._get_row_at_y(event.y)
        if idx >= 0:
            self._selected_idx = idx
            self._redraw()
            if self.on_click:
                self.on_click(idx, self._items[idx])

    def _on_canvas_double(self, event):
        idx = self._get_row_at_y(event.y)
        if idx >= 0:
            self._selected_idx = idx
            self._redraw()
            if self.on_double_click:
                self.on_double_click(self._items[idx])

    def _on_canvas_right(self, event):
        idx = self._get_row_at_y(event.y)
        if idx >= 0:
            self._selected_idx = idx
            self._redraw()
            if self.on_right_click:
                self.on_right_click(event, self._items[idx])


# ===== 远程文件列表（Canvas 渲染） =====

class CanvasFileList(_CanvasListBase):
    """远程文件列表 — 基于 Canvas 渲染，真透明看背景。"""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        # 所有核心逻辑已在基类中


# ===== 本地文件列表（Canvas 渲染） =====

class LocalFileList(_CanvasListBase):
    """本地文件列表 — 完全复用基类 Canvas 渲染逻辑，本地文件用蓝色区分。"""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self._current_path = str(Path.home())

    @property
    def current_path(self):
        return self._current_path

    def navigate(self, path: str):
        self._current_path = path
        self.refresh()

    def go_up(self):
        parent = str(Path(self._current_path).parent)
        if parent and parent != self._current_path:
            self.navigate(parent)

    def refresh(self):
        def _load():
            items = []
            try:
                with os.scandir(self._current_path) as it:
                    for entry in it:
                        try:
                            st = entry.stat()
                        except OSError:
                            continue
                        items.append({"name": entry.name, "size": st.st_size,
                                       "mtime": st.st_mtime, "is_dir": entry.is_dir()})
            except (PermissionError, FileNotFoundError, OSError):
                pass  # 无权限 / 路径不存在 / 其他 IO 错误 → 显示为空
            items.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))
            self.after(0, lambda: self.set_items(items))
        threading.Thread(target=_load, daemon=True).start()

    def _get_name_color(self, item: dict) -> str:
        """本地文件名使用蓝色以区分远程。"""
        return ThemeColors.get("local_file_name")


class FileBrowser(ctk.CTkFrame):
    """远程文件管理器 — 支持单栏/双栏模式"""

    def __init__(self, master, ssh_client, config: dict = None, app_ref=None):
        super().__init__(master, fg_color="transparent", corner_radius=0)
        self._ssh = ssh_client
        self._config = config or {}
        self._app = app_ref
        self._current_path = "/home/chenxi"
        self._selected_file = None
        self._selected_item = None
        self._mode = "single"  # single / dual
        self._local_path = str(Path.home())

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)  # 路径栏
        self.grid_rowconfigure(1, weight=0)  # 表头
        self.grid_rowconfigure(2, weight=1)  # 文件列表
        self.grid_rowconfigure(3, weight=0)  # 操作栏
        self.grid_rowconfigure(4, weight=0)  # 进度/状态

        self._build_widgets()

    def _build_widgets(self):
        """构建 UI"""
        # ===== 路径导航栏（卡片包裹） =====
        nav_card = self._make_card("", 0, sticky="ew", pady=(5, 2))
        nav_card.grid_columnconfigure(2, weight=1)

        # ★ 双栏模式切换按钮
        self._btn_mode = ctk.CTkButton(
            nav_card, text="📂 双栏", width=70, height=28,
            font=ctk.CTkFont(size=11), command=self._toggle_mode,
            fg_color="#1E3A5A", hover_color="#2A4A6A")
        self._btn_mode.grid(row=0, column=0, padx=(5, 2), pady=4)

        self._btn_home = ctk.CTkButton(
            nav_card, text="🏠", width=36,
            command=lambda: self.navigate("/home/chenxi"),
            fg_color="transparent", hover_color="#333")
        self._btn_home.grid(row=0, column=1, padx=2, pady=4)

        self._btn_up = ctk.CTkButton(
            nav_card, text="⬆", width=36, command=self._go_up,
            fg_color="transparent", hover_color="#333")
        self._btn_up.grid(row=0, column=2, padx=2, pady=4)

        self._path_frame = ctk.CTkFrame(nav_card, fg_color="transparent", corner_radius=0)
        self._path_frame.grid(row=0, column=3, sticky="ew", padx=5)

        self._btn_refresh = ctk.CTkButton(
            nav_card, text="🔄", width=36, command=self.refresh,
            fg_color="transparent", hover_color="#333")
        self._btn_refresh.grid(row=0, column=4, padx=(2, 5), pady=4)

        # ===== 文件列表头 =====
        header_frame = ctk.CTkFrame(
            self, height=30, fg_color="transparent", border_width=1,
            border_color=("gray55", "gray35"), corner_radius=6)
        header_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=(0, 0))
        header_frame.grid_columnconfigure(0, weight=1)
        header_frame.grid_columnconfigure(1, weight=0)
        header_frame.grid_columnconfigure(2, weight=0)

        ctk.CTkLabel(header_frame, text="  名称", anchor="w",
                     font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=8, pady=2)
        ctk.CTkLabel(header_frame, text="大小", width=90, anchor="e",
                     font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=0, column=1, sticky="e", padx=8, pady=2)
        ctk.CTkLabel(header_frame, text="修改时间", width=160, anchor="e",
                     font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=0, column=2, sticky="e", padx=8, pady=2)

        # ===== 文件列表容器 =====
        self._list_container = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        self._list_container.grid(row=2, column=0, sticky="nsew", padx=2, pady=(0, 5))
        self._list_container.grid_columnconfigure(0, weight=1)
        self._list_container.grid_columnconfigure(1, weight=0)
        self._list_container.grid_rowconfigure(0, weight=1)

        # 远程列表
        self._file_list = CanvasFileList(
            self._list_container, border_width=1, border_color=("gray55", "gray35"))
        self._file_list.grid(row=0, column=0, sticky="nsew")

        # 设置回调
        self._file_list.on_click = self._on_click
        self._file_list.on_double_click = self._on_double_click
        self._file_list.on_right_click = self._on_right_click

        # ★ 本地面板容器（双栏模式专用：nav + list）
        self._dual_pane = ctk.CTkFrame(
            self._list_container, fg_color="transparent", corner_radius=0)
        self._dual_pane.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        self._dual_pane.grid_remove()
        self._dual_pane.grid_columnconfigure(0, weight=1)
        self._dual_pane.grid_rowconfigure(0, weight=0)  # 本地导航
        self._dual_pane.grid_rowconfigure(1, weight=0)  # 本地表头
        self._dual_pane.grid_rowconfigure(2, weight=1)  # 本地列表

        # 本地导航栏
        self._local_nav = self._build_local_nav(self._dual_pane)

        # 本地列表头（精简版）
        local_header = ctk.CTkFrame(
            self._dual_pane, height=22, fg_color="transparent", corner_radius=0)
        local_header.grid(row=1, column=0, sticky="ew")
        ctk.CTkLabel(local_header, text="💻 本地文件", anchor="w",
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color=ThemeColors.get("local_file_name")).pack(
            side="left", padx=8)

        # 本地文件列表
        self._local_list = LocalFileList(
            self._dual_pane, border_width=1, border_color=("gray55", "gray35"))
        self._local_list.grid(row=2, column=0, sticky="nsew")
        self._local_list.on_click = self._on_local_click
        self._local_list.on_double_click = self._on_local_double
        self._local_list.on_right_click = self._on_local_right

        # ===== 操作按钮栏 =====
        btn_card = self._make_card("", 3, sticky="ew", pady=(0, 5))
        btn_card.grid_columnconfigure(0, weight=1)

        btn_left = ctk.CTkFrame(btn_card, fg_color="transparent", corner_radius=0)
        btn_left.pack(side="left", padx=4, pady=4)

        btn_mid = ctk.CTkFrame(btn_card, fg_color="transparent", corner_radius=0)
        btn_mid.pack(side="left", padx=4, pady=4)

        btn_right = ctk.CTkFrame(btn_card, fg_color="transparent", corner_radius=0)
        btn_right.pack(side="right", padx=4, pady=4)

        btn_style = {"width": 85, "height": 28, "font": ctk.CTkFont(size=12)}

        self._btn_upload = ctk.CTkButton(
            btn_left, text="📤 上传", command=self._upload_file, **btn_style)
        self._btn_upload.pack(side="left", padx=2)

        self._btn_download = ctk.CTkButton(
            btn_left, text="📥 下载", command=self._download_selected, **btn_style)
        self._btn_download.pack(side="left", padx=2)

        self._btn_run = ctk.CTkButton(
            btn_left, text="▶ 运行", command=self._run_selected, **btn_style,
            fg_color="#1E5A1E", hover_color="#2A6A2A")
        self._btn_run.pack(side="left", padx=2)

        # ★ 双栏传输按钮（默认隐藏）
        self._btn_to_local = ctk.CTkButton(
            btn_mid, text="← 下载到本地", command=self._download_to_local,
            width=110, height=28, font=ctk.CTkFont(size=12),
            fg_color="#1E3A5A", hover_color="#2A4A6A")
        self._btn_to_local.pack(side="left", padx=2)
        self._btn_to_local.pack_forget()

        self._btn_to_remote = ctk.CTkButton(
            btn_mid, text="上传到树莓派 →", command=self._upload_from_local,
            width=110, height=28, font=ctk.CTkFont(size=12),
            fg_color="#1E3A5A", hover_color="#2A4A6A")
        self._btn_to_remote.pack(side="left", padx=2)
        self._btn_to_remote.pack_forget()

        self._btn_mkdir = ctk.CTkButton(
            btn_right, text="📁 新建文件夹", command=self._create_dir, **btn_style)
        self._btn_mkdir.pack(side="left", padx=2)

        self._btn_rename = ctk.CTkButton(
            btn_right, text="✏️ 重命名", command=self._rename_selected, **btn_style)
        self._btn_rename.pack(side="left", padx=2)

        self._btn_delete = ctk.CTkButton(
            btn_right, text="🗑 删除", command=self._delete_selected, **btn_style,
            fg_color="#8B0000", hover_color="#A00000")
        self._btn_delete.pack(side="left", padx=2)

        # ===== 进度条 + 状态 =====
        self._progress = ctk.CTkProgressBar(self)
        self._progress.grid(row=4, column=0, sticky="ew", padx=10, pady=(0, 2))
        self._progress.set(0)
        self._progress.grid_remove()

        self._lbl_progress = ctk.CTkLabel(self, text="", text_color="gray",
                                          font=ctk.CTkFont(size=11))
        self._lbl_progress.grid(row=4, column=0, sticky="e", padx=15, pady=(0, 2))

    def _make_card(self, title: str, row: int, sticky="ew", **grid_kw):
        """统一卡片容器 — 透明背景 + 细边框，背景图穿透"""
        frame = ctk.CTkFrame(
            self, fg_color="transparent", border_width=1,
            border_color=("gray55", "gray35"), corner_radius=8)
        frame.grid(row=row, column=0, sticky=sticky, **grid_kw)
        if title:
            ctk.CTkLabel(frame, text=title,
                         font=ctk.CTkFont(size=12, weight="bold"),
                         anchor="w").pack(anchor="w", padx=10, pady=(6, 2))
        return frame

    # ===== 导航 =====

    def navigate(self, path: str):
        """导航到指定路径"""
        self._current_path = path
        self._selected_file = None
        self._selected_item = None
        self.refresh()

    def _go_up(self):
        """返回上级目录"""
        parent = os.path.dirname(self._current_path)
        if parent and parent != self._current_path:
            self.navigate(parent)

    def refresh(self):
        """刷新当前目录"""
        if not self._ssh.connected:
            self._show_empty("🔴 未连接到树莓派，请先连接")
            return

        def _fetch():
            items = self._ssh.list_dir(self._current_path)
            self.after(0, lambda: self._render_files(items))

        threading.Thread(target=_fetch, daemon=True).start()

    def _render_files(self, items: list):
        """渲染文件列表"""
        self._selected_file = None
        self._selected_item = None

        self._update_breadcrumb()

        if not items:
            # 显示空状态
            self._file_list._items = []
            self._file_list._redraw()
            return

        self._file_list.set_items(items)

    def _update_breadcrumb(self):
        """更新面包屑导航"""
        for w in self._path_frame.winfo_children():
            w.destroy()

        parts = self._current_path.strip("/").split("/")
        path_so_far = ""

        # 根
        btn = ctk.CTkButton(
            self._path_frame, text=" / ", width=30, height=24,
            font=ctk.CTkFont(size=12), fg_color="transparent",
            hover_color="#333", command=lambda: self.navigate("/"))
        btn.pack(side="left", padx=1)

        for part in parts:
            if not part:
                continue
            path_so_far += "/" + part
            lbl = ctk.CTkLabel(self._path_frame, text="›", text_color="gray")
            lbl.pack(side="left")
            btn = ctk.CTkButton(
                self._path_frame, text=f" {part} ", height=24,
                font=ctk.CTkFont(size=12), fg_color="transparent",
                hover_color="#333", command=lambda p=path_so_far: self.navigate(p))
            btn.pack(side="left", padx=1)

    def _show_empty(self, msg: str):
        """显示空状态（CanvasFileList 中处理）"""
        self._file_list._items = []
        self._file_list._redraw()

    # ===== 点击事件 =====

    def _on_click(self, index: int, item: dict):
        """单击选择"""
        self._selected_file = item["name"]
        self._selected_item = item

    def _on_double_click(self, item: dict):
        """双击进入目录或下载文件"""
        if item["is_dir"]:
            new_path = os.path.join(self._current_path, item["name"]).replace("\\", "/")
            self.navigate(new_path)
        else:
            self._selected_file = item["name"]
            self._selected_item = item
            self._download_selected()

    def _on_right_click(self, event, item: dict):
        """右键菜单"""
        self._selected_file = item["name"]
        self._selected_item = item
        menu = Menu(self, tearoff=0, bg="#2B2B2B", fg="white",
                    activebackground="#444", activeforeground="white")
        menu.add_command(label="📥 下载", command=self._download_selected)
        if not item["is_dir"]:
            menu.add_command(label="▶ 运行", command=self._run_selected)
        menu.add_separator()
        if item["is_dir"]:
            menu.add_command(label="📁 进入",
                             command=lambda: self._on_double_click(item))
        menu.add_command(label="✏️ 重命名", command=self._rename_selected)
        menu.add_command(label="🗑 删除", command=self._delete_selected)
        menu.add_separator()
        menu.add_command(label="📂 新建文件夹", command=self._create_dir)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    # ===== 文件操作 =====

    def _upload_file(self):
        """上传文件"""
        if not self._ssh.connected:
            messagebox.showwarning("未连接", "请先连接到树莓派")
            return
        files = filedialog.askopenfilenames(title="选择要上传的文件")
        if not files:
            return
        for local_path in files:
            fname = os.path.basename(local_path)
            remote_path = f"{self._current_path}/{fname}"
            self._do_transfer("upload", local_path, remote_path)

    def _download_selected(self):
        """下载选中的文件/目录"""
        if not self._ssh.connected:
            messagebox.showwarning("未连接", "请先连接到树莓派")
            return
        if not self._selected_file:
            messagebox.showinfo("提示", "请先选择要下载的文件")
            return
        remote_path = f"{self._current_path}/{self._selected_file}"
        info = self._ssh.get_file_info(remote_path)
        if info and info["is_dir"]:
            messagebox.showinfo(
                "提示", "暂不支持下载目录，请使用终端执行 tar 打包后下载")
            return
        local_dir = filedialog.askdirectory(title="选择保存位置")
        if not local_dir:
            return
        local_path = os.path.join(local_dir, self._selected_file)
        self._do_transfer("download", remote_path, local_path)

    def _run_selected(self):
        """在树莓派上执行选中的脚本文件"""
        if not self._ssh.connected:
            messagebox.showwarning("未连接", "请先连接到树莓派")
            return
        if not self._selected_file:
            messagebox.showinfo("提示", "请先选择要运行的文件")
            return
        if self._selected_item and self._selected_item.get("is_dir"):
            messagebox.showinfo("提示", "不能运行目录，请选择一个脚本文件")
            return

        remote_path = f"{self._current_path}/{self._selected_file}"

        # 根据扩展名确定执行方式（shlex.quote 防注入）
        rp = shlex.quote(remote_path)
        ext = os.path.splitext(self._selected_file)[1].lower()
        if ext in (".py", ".py3"):
            run_cmd = f"python3 {rp}"
        elif ext in (".sh", ".bash"):
            run_cmd = f"bash {rp}"
        else:
            run_cmd = f"chmod +x {rp} && {rp}"

        # 切换到终端页面并执行
        if self._app and hasattr(self._app, '_terminal_page'):
            self._app._show_page("terminal")
            # 新建一个终端标签来执行
            self._app._terminal_page._add_session(f"运行: {self._selected_file[:12]}")
            # 将命令填入当前终端
            if self._app._terminal_page._tabs:
                tab = self._app._terminal_page._tabs[-1]
                tab._entry.insert(0, run_cmd)
                tab._entry.focus_set()
        else:
            # 直接在当前页面执行并显示结果
            self._lbl_progress.configure(text=f"执行: {self._selected_file}...")
            self._progress.grid()
            self._progress.set(0)
            self._progress.configure(mode="indeterminate")
            self._progress.start()

            def _run():
                code, out, err = self._ssh.exec_command(run_cmd, timeout=120)
                self.after(0, lambda: self._on_run_result(out, err, code))

            threading.Thread(target=_run, daemon=True).start()

    def _on_run_result(self, stdout: str, stderr: str, exit_code: int):
        """运行结果回调"""
        self._progress.stop()
        self._progress.configure(mode="determinate")
        self._progress.grid_remove()
        status = "✓ 成功" if exit_code == 0 else f"✗ 退出码: {exit_code}"
        self._lbl_progress.configure(text=status)

        # 弹出结果对话框
        result = f"━━━ 标准输出 ━━━\n{stdout or '(无输出)'}"
        if stderr:
            result += f"\n\n━━━ 错误输出 ━━━\n{stderr}"
        result += f"\n\n退出码: {exit_code}"

        dialog = ctk.CTkToplevel(self)
        dialog.title(f"运行结果: {self._selected_file}")
        dialog.geometry("700x500")
        dialog.transient(self)

        output = ctk.CTkTextbox(
            dialog, font=ctk.CTkFont(family="Consolas", size=12),
            fg_color="#0D1117", text_color="#C9D1D9", wrap="word")
        output.pack(fill="both", expand=True, padx=10, pady=10)
        output.insert("1.0", result)
        output.configure(state="disabled")

        ctk.CTkButton(
            dialog, text="关闭", command=dialog.destroy, width=80
        ).pack(pady=(0, 10))

    def _do_transfer(self, direction: str, src: str, dst: str):
        """执行文件传输"""
        self._progress.set(0)
        self._progress.grid()
        self._lbl_progress.configure(
            text=f"{'📤 上传' if direction == 'upload' else '📥 下载'}中...")

        def _progress_cb(transferred, total):
            if total > 0:
                pct = transferred / total
                self.after(0, lambda: self._progress.set(pct))

        def _run():
            if direction == "upload":
                ok, msg = self._ssh.upload_file(src, dst, _progress_cb)
            else:
                ok, msg = self._ssh.download_file(src, dst, _progress_cb)
            self.after(0, lambda: self._on_transfer_done(ok, msg))

        threading.Thread(target=_run, daemon=True).start()

    def _on_transfer_done(self, ok: bool, msg: str):
        """传输完成回调"""
        self._progress.grid_remove()
        if ok:
            self._lbl_progress.configure(text="✓ 传输完成")
        else:
            self._lbl_progress.configure(text=f"✗ {msg}")
        self.after(3000, lambda: self._lbl_progress.configure(text=""))
        if ok:
            self.refresh()
            if self._mode == "dual":
                self._local_list.refresh()

    def _create_dir(self):
        """创建远程目录"""
        if not self._ssh.connected:
            messagebox.showwarning("未连接", "请先连接到树莓派")
            return
        dialog = ctk.CTkInputDialog(text="输入文件夹名称:", title="新建文件夹")
        name = dialog.get_input()
        if name:
            path = f"{self._current_path}/{name}"
            ok, msg = self._ssh.create_remote_dir(path)
            if ok:
                self.refresh()
            else:
                messagebox.showerror("创建失败", msg)

    def _delete_selected(self):
        """删除选中项"""
        if not self._ssh.connected:
            messagebox.showwarning("未连接", "请先连接到树莓派")
            return
        if not self._selected_file:
            messagebox.showinfo("提示", "请先选择要删除的文件")
            return
        if messagebox.askyesno(
            "确认删除",
            f"确定要删除 \"{self._selected_file}\" 吗？\n此操作不可恢复！"
        ):
            path = f"{self._current_path}/{self._selected_file}"
            ok, msg = self._ssh.delete_remote(path)
            if ok:
                self.refresh()
            else:
                messagebox.showerror("删除失败", msg)

    def _rename_selected(self):
        """重命名选中项"""
        if not self._ssh.connected:
            messagebox.showwarning("未连接", "请先连接到树莓派")
            return
        if not self._selected_file:
            messagebox.showinfo("提示", "请先选择要重命名的文件")
            return
        dialog = ctk.CTkInputDialog(text="输入新名称:", title="重命名")
        new_name = dialog.get_input()
        if new_name and new_name != self._selected_file:
            old_path = f"{self._current_path}/{self._selected_file}"
            new_path = f"{self._current_path}/{new_name}"
            ok, msg = self._ssh.rename_remote(old_path, new_path)
            if ok:
                self.refresh()
            else:
                messagebox.showerror("重命名失败", msg)

    # ===== 本地导航栏 =====

    def _build_local_nav(self, parent):
        """构建本地面板导航栏（仅双栏模式可见）。"""
        nav = ctk.CTkFrame(parent, fg_color="transparent", corner_radius=0)
        nav.grid(row=0, column=0, sticky="ew", pady=(0, 2))

        ctk.CTkButton(
            nav, text="🏠", width=32, height=22,
            font=ctk.CTkFont(size=11),
            fg_color="transparent", hover_color="#333",
            command=lambda: self._local_navigate(str(Path.home()))
        ).pack(side="left", padx=1)

        ctk.CTkButton(
            nav, text="⬆", width=32, height=22,
            font=ctk.CTkFont(size=11),
            fg_color="transparent", hover_color="#333",
            command=self._local_go_up
        ).pack(side="left", padx=1)

        self._local_path_label = ctk.CTkLabel(
            nav, text="", anchor="w",
            font=ctk.CTkFont(size=10), text_color="gray")
        self._local_path_label.pack(side="left", fill="x", expand=True, padx=4)

        ctk.CTkButton(
            nav, text="🔄", width=32, height=22,
            font=ctk.CTkFont(size=11),
            fg_color="transparent", hover_color="#333",
            command=lambda: self._local_list.refresh()
        ).pack(side="right", padx=1)

        return nav

    def _local_navigate(self, path: str):
        """本地导航到指定路径。"""
        self._local_path = path
        self._local_path_label.configure(
            text=path if len(path) < 50 else "…" + path[-47:])
        self._local_list.navigate(path)

    def _local_go_up(self):
        """本地返回上级目录。"""
        parent = str(Path(self._local_path).parent)
        if parent and parent != self._local_path:
            self._local_navigate(parent)

    # ===== 双栏模式 =====

    def _toggle_mode(self):
        """切换单栏/双栏模式。"""
        if self._mode == "single":
            self._mode = "dual"
            self._btn_mode.configure(text="📂 单栏", fg_color="#2A5A2A", hover_color="#3A6A3A")
            self._list_container.grid_columnconfigure(1, weight=1)
            self._dual_pane.grid()
            self._btn_to_local.pack(side="left", padx=2)
            self._btn_to_remote.pack(side="left", padx=2)
            self._local_navigate(self._local_path)
            # 强制 layout → 两栏各得 50% 宽度 → 重绘
            self._list_container.update_idletasks()
            self._file_list._redraw()
        else:
            self._mode = "single"
            self._btn_mode.configure(text="📂 双栏", fg_color="#1E3A5A", hover_color="#2A4A6A")
            self._dual_pane.grid_remove()
            self._btn_to_local.pack_forget()
            self._btn_to_remote.pack_forget()
            self._list_container.grid_columnconfigure(1, weight=0)
            # 强制 layout → 让远程列表扩展填满 → 重绘
            self._list_container.update_idletasks()
            self._file_list._redraw()

    # ===== 本地文件事件 =====

    def _on_local_click(self, index, item):
        pass

    def _on_local_double(self, item):
        if item["is_dir"]:
            self._local_navigate(
                os.path.join(self._local_path, item["name"]))
        else:
            # 双击本地文件 → 直接上传到树莓派
            self._upload_specific(
                os.path.join(self._local_path, item["name"]))

    def _on_local_right(self, event, item):
        full = os.path.join(self._local_path, item["name"])
        menu = Menu(self, tearoff=0, bg="#2B2B2B", fg="white",
                    activebackground="#444", activeforeground="white")
        menu.add_command(label="→ 上传到树莓派",
                         command=lambda: self._upload_specific(full))
        menu.add_command(label="📋 复制路径",
                         command=lambda: self.clipboard_append(full))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    # ===== 双栏传输 =====

    def _download_to_local(self):
        """远程选中文件 → 本地当前目录。"""
        if not self._selected_file or not self._ssh.connected:
            return
        remote_path = f"{self._current_path}/{self._selected_file}"
        local_path = os.path.join(self._local_path, self._selected_file)
        if os.path.exists(local_path):
            if not messagebox.askyesno("覆盖确认", f"本地 {self._selected_file} 已存在，覆盖？"):
                return
        self._do_transfer("download", remote_path, local_path)

    def _upload_from_local(self):
        """本地选中文件 → 远程当前目录。"""
        sel = self._local_list.get_selected()
        if not sel or not self._ssh.connected:
            return
        local_path = os.path.join(self._local_path, sel["name"])
        remote_path = f"{self._current_path}/{sel['name']}"
        self._do_transfer("upload", local_path, remote_path)

    def _upload_specific(self, local_path: str):
        """上传指定本地文件到远程。"""
        if not self._ssh.connected:
            return
        self._do_transfer("upload", local_path,
                          f"{self._current_path}/{os.path.basename(local_path)}")
