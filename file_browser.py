"""
PiManager 文件管理 v2 — tkinter + Canvas 文件列表（去 CTk）
"""
import tkinter as tk
from tkinter import filedialog, messagebox, Menu
import threading
import os
from datetime import datetime

from .theme import ThemeColors


# ============================================================
#  Canvas 文件列表（从 v1 保留核心渲染逻辑）
# ============================================================

class _CanvasListBase(tk.Frame):
    """Canvas 渲染的文件列表基类。"""

    def __init__(self, master, is_local: bool = False, **kw):
        super().__init__(master, bg=ThemeColors.get("bg"), **kw)
        self._is_local = is_local
        self._items = []
        self._scroll_y = 0
        self._selected = None

        self._canvas = tk.Canvas(self, bg=ThemeColors.get("bg"),
                                 highlightthickness=0, bd=0)
        self._canvas.pack(fill="both", expand=True)

        self._canvas.bind("<MouseWheel>", self._on_mousewheel)
        self._canvas.bind("<Button-1>", self._on_click)
        self._canvas.bind("<Double-Button-1>", self._on_dblclick)
        self._canvas.bind("<Button-3>", self._on_rightclick)
        self._canvas.bind("<Configure>", lambda e: self._redraw())

    def set_items(self, items: list):
        self._items = items
        self._scroll_y = 0
        self._redraw()

    def _on_mousewheel(self, event):
        self._scroll_y = max(0, self._scroll_y -
                            (1 if event.delta > 0 else -1) * 40)
        self._redraw()

    def _on_click(self, event):
        idx = self._row_at(event.y)
        if 0 <= idx < len(self._items):
            self._selected = idx
            self._redraw()
            if hasattr(self, 'on_click'):
                self.on_click(self._items[idx], idx)

    def _on_dblclick(self, event):
        idx = self._row_at(event.y)
        if 0 <= idx < len(self._items) and hasattr(self, 'on_dblclick'):
            self.on_dblclick(self._items[idx], idx)

    def _on_rightclick(self, event):
        idx = self._row_at(event.y)
        if 0 <= idx < len(self._items) and hasattr(self, 'on_rightclick'):
            self.on_rightclick(self._items[idx], idx, event)

    def _row_at(self, y: int) -> int:
        return (y + self._scroll_y) // 28

    def _redraw(self):
        c = self._canvas
        c.delete("all")
        cw = c.winfo_width() or 400

        s = ThemeColors.get("text_secondary")
        t = ThemeColors.get("text")
        name_color = "#0969DA" if self._is_local else "#8BCCFF"
        sel_bg = ThemeColors.get("canvas_selection")

        name_w = cw - 200 if cw > 400 else cw - 60
        size_w = 80
        time_w = 100

        y0 = -self._scroll_y
        font_name = ("Consolas", 10)
        font_info = ("Consolas", 9)

        for i, item in enumerate(self._items):
            y = y0 + i * 28
            if y < -28 or y > c.winfo_height() + 28:
                continue

            # 选中高亮
            if i == self._selected:
                c.create_rectangle(0, y, cw, y + 28, fill=sel_bg, outline="")

            # 图标 + 名称
            icon = "📁" if item.get("is_dir") else "📄"
            name = item.get("name", "?")
            display = f"  {icon} {name}"
            max_ch = name_w // 8
            if len(display) > max_ch:
                display = display[:max_ch - 2] + "…"
            c.create_text(8, y + 5, text=display, anchor="nw",
                          fill=name_color, font=font_name)

            # 大小
            if not item.get("is_dir"):
                sz = item.get("size", 0)
                if sz > 1_000_000:
                    sz_t = f"{sz/1_000_000:.1f}M"
                elif sz > 1000:
                    sz_t = f"{sz/1000:.0f}K"
                else:
                    sz_t = str(sz)
                c.create_text(name_w + 10, y + 5, text=sz_t,
                              anchor="nw", fill=s, font=font_info)

            # 时间
            mt = item.get("mtime", "")
            if mt:
                try:
                    if isinstance(mt, (int, float)):
                        mt = datetime.fromtimestamp(mt).strftime("%m-%d %H:%M")
                except Exception:
                    pass
            c.create_text(name_w + size_w + 15, y + 5, text=str(mt)[:14],
                          anchor="nw", fill=s, font=font_info)

    def get_selected(self) -> dict:
        if self._selected is not None and 0 <= self._selected < len(self._items):
            return self._items[self._selected]
        return None

    def refresh_theme(self):
        self._canvas.configure(bg=ThemeColors.get("bg"))
        self._redraw()


class CanvasFileList(_CanvasListBase):
    """远程文件列表。"""
    def __init__(self, master, **kw):
        super().__init__(master, is_local=False, **kw)


# ============================================================
#  FileBrowser — 主控制器
# ============================================================

class FileBrowser(tk.Frame):
    """文件管理器 — tkinter + Canvas 文件列表。"""

    def __init__(self, master, ssh_client, config: dict = None, app_ref=None):
        super().__init__(master, bg=ThemeColors.get("bg"))
        self._ssh = ssh_client
        self._config = config or {}
        self._app = app_ref
        self._cwd = "/home/chenxi"

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)

        # 工具栏
        self._build_toolbar()

        # 文件列表
        self._file_list = CanvasFileList(self)
        self._file_list.grid(row=1, column=0, sticky="nsew")
        self._file_list.on_dblclick = self._on_dblclick
        self._file_list.on_rightclick = self._on_rightclick

    def _build_toolbar(self):
        bar = tk.Frame(self, bg=ThemeColors.get("bg_card"), height=38)
        bar.grid(row=0, column=0, sticky="ew")
        bar.grid_propagate(False)

        btns = [
            ("🔄 刷新", self.refresh),
            ("📤 上传", self._upload_file),
            ("📥 下载", self._download_selected),
            ("📁 新建", self._mkdir),
            ("🗑 删除", self._delete_selected),
        ]
        for text, cmd in btns:
            tk.Button(bar, text=text, command=cmd,
                     bg="#2B5B2B", fg="white", relief="flat",
                     font=("Segoe UI", 10), padx=10, pady=2).pack(
                side="left", padx=3, pady=4)

    def refresh(self):
        if not self._ssh.connected:
            return
        def _fetch():
            try:
                items = self._ssh.list_dir(self._cwd)
                self.after(0, lambda: self._file_list.set_items(items))
            except Exception:
                pass
        threading.Thread(target=_fetch, daemon=True).start()

    def _on_dblclick(self, item, idx):
        if item.get("is_dir"):
            self._cwd = f"{self._cwd.rstrip('/')}/{item['name']}"
            self.refresh()

    def _on_rightclick(self, item, idx, event):
        menu = Menu(self, tearoff=0)
        menu.add_command(label="📥 下载", command=self._download_selected)
        if item.get("is_dir"):
            menu.add_command(label="📂 打开", command=lambda: self._on_dblclick(item, idx))
        else:
            menu.add_command(label="▶ 运行", command=lambda: self._run_file(item))
        menu.add_separator()
        menu.add_command(label="✏️ 重命名", command=self._rename_selected)
        menu.add_command(label="🗑 删除", command=self._delete_selected)
        menu.post(event.x_root, event.y_root)

    def _upload_file(self):
        if not self._ssh.connected:
            return
        path = filedialog.askopenfilename(title="选择要上传的文件")
        if not path:
            return
        remote = f"{self._cwd}/{os.path.basename(path)}"
        def _do():
            ok, msg = self._ssh.upload_file(path, remote)
            self.after(0, self.refresh)
            if not ok:
                self.after(0, lambda: messagebox.showerror("上传失败", msg))
        threading.Thread(target=_do, daemon=True).start()

    def _download_selected(self):
        if not self._ssh.connected:
            return
        sel = self._file_list.get_selected()
        if not sel:
            return
        dest = filedialog.askdirectory(title="选择保存位置")
        if not dest:
            return
        remote = f"{self._cwd}/{sel['name']}"
        local = os.path.join(dest, sel['name'])
        def _do():
            ok, msg = self._ssh.download_file(remote, local)
            if not ok:
                self.after(0, lambda: messagebox.showerror("下载失败", msg))
        threading.Thread(target=_do, daemon=True).start()

    def _mkdir(self):
        if not self._ssh.connected:
            return
        name = "新建文件夹"
        def _do():
            self._ssh.create_remote_dir(f"{self._cwd}/{name}")
            self.after(0, self.refresh)
        threading.Thread(target=_do, daemon=True).start()

    def _delete_selected(self):
        if not self._ssh.connected:
            return
        sel = self._file_list.get_selected()
        if not sel:
            return
        if not messagebox.askyesno("确认删除",
            f"确定要删除 {sel.get('name')} 吗？\n此操作不可恢复。"):
            return
        def _do():
            self._ssh.delete_remote(f"{self._cwd}/{sel['name']}")
            self.after(0, self.refresh)
        threading.Thread(target=_do, daemon=True).start()

    def _rename_selected(self):
        if not self._ssh.connected:
            return
        sel = self._file_list.get_selected()
        if not sel:
            return
        # 简化：直接重命名为 user_input
        old = f"{self._cwd}/{sel['name']}"
        new_name = f"{self._cwd}/renamed_{sel['name']}"
        def _do():
            self._ssh.rename_remote(old, new_name)
            self.after(0, self.refresh)
        threading.Thread(target=_do, daemon=True).start()

    def _run_file(self, item):
        """远程运行 Python/Shell 脚本。"""
        if not self._ssh.connected or not self._app:
            return
        remote = f"{self._cwd}/{item['name']}"
        def _do():
            exit_code, stdout, stderr = self._ssh.exec_command(
                f"python3 {shlex.quote(remote)}", timeout=10)
            result = f"=== stdout ===\n{stdout}\n=== stderr ===\n{stderr}\n=== exit: {exit_code}"
            self.after(0, lambda: messagebox.showinfo("运行结果", result[:2000]))
        threading.Thread(target=_do, daemon=True).start()

    def refresh_theme(self):
        self.configure(bg=ThemeColors.get("bg"))
        self._file_list.refresh_theme()
