"""
PiManager 文件管理 v3 — tkinter + Canvas + 双栏模式 + 进度 + 运行
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, Menu
import threading
import shlex
import os
from datetime import datetime

from .theme import ThemeColors
from .app import BackgroundManager

# ============================================================
#  Canvas 文件列表
# ============================================================

# Canvas 渲染的文件列表基类
class _CanvasListBase(tk.Frame):

    def __init__(self, master, is_local=False, **kw):
        super().__init__(master, bg=ThemeColors.get("bg"), **kw)
        self._is_local = is_local
        self._items = []
        self._scroll_y = 0
        self._selected = None

        self._canvas = tk.Canvas(self, bg=ThemeColors.get("bg"),
                                 highlightthickness=0, bd=0)
        self._canvas.pack(fill="both", expand=True)
        self._bg_cache_key = None

        self._canvas.bind("<MouseWheel>", self._on_mousewheel)
        self._canvas.bind("<Button-1>", self._on_click)
        self._canvas.bind("<Double-Button-1>", self._on_dblclick)
        self._canvas.bind("<Button-3>", self._on_rightclick)
        self._canvas.bind("<Configure>", lambda e: self._redraw())
        # 背景由 FileBrowser._list_container 统一管理，不单独注册

    def set_items(self, items):
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

    def _row_at(self, y):
        return (y + self._scroll_y) // 28

    def _apply_background(self):
        """位置感知背景裁剪 — 每个 Canvas 显示背景图的对应区域"""
        c = self._canvas
        cw = c.winfo_width()
        ch = c.winfo_height()
        if cw < 20 or ch < 20:
            return

        # 容器尺寸
        container = self.master
        container_w = container.winfo_width()
        container_h = container.winfo_height()
        if container_w < 20 or container_h < 20:
            return

        # 本 Canvas 在容器内的偏移
        offset_x = self.winfo_x() + c.winfo_x()
        offset_y = self.winfo_y() + c.winfo_y()

        # 缓存检查：布局/图片不变则跳过
        cache_key = (container_w, container_h, offset_x, offset_y, cw, ch,
                     id(BackgroundManager._blended))
        if cache_key == self._bg_cache_key:
            return
        self._bg_cache_key = cache_key

        if BackgroundManager._blended is None:
            c.delete("bg_image")
            return

        BackgroundManager.apply_to_canvas_positioned(
            c, (container_w, container_h), (offset_x, offset_y))

    def _redraw(self):
        """使用原始 tk.Canvas 绘制文件列表（非 pillui，因为是逐行列表项 + 自定义选中高亮）。"""
        c = self._canvas
        c.delete("list_item")
        cw = c.winfo_width() or 400
        self._apply_background()
        # Canvas uses solid theme background color — no background image applied
        s = ThemeColors.get("text_secondary")
        name_color = "#0969DA" if self._is_local else "#8BCCFF"
        sel_bg = ThemeColors.get("canvas_selection")

        name_w = cw - 200 if cw > 400 else cw - 60
        size_w = 80
        time_w = 100

        y0 = -self._scroll_y
        font_name = ("Microsoft YaHei", 10)
        font_info = ("Microsoft YaHei", 9)

        for i, item in enumerate(self._items):
            y = y0 + i * 28
            if y < -28 or y > c.winfo_height() + 28:
                continue

            if i == self._selected:
                c.create_rectangle(0, y, cw, y + 28, fill=sel_bg, outline="", tags="list_item")

            icon = "DIR" if item.get("is_dir") else "   "
            name = item.get("name", "?")
            display = f" {icon}  {name}"
            max_ch = name_w // 8
            if len(display) > max_ch:
                display = display[:max_ch - 1] + ".."
            c.create_text(8, y + 5, text=display, anchor="nw",
                          fill=name_color, font=font_name, tags="list_item")

            if not item.get("is_dir"):
                sz = item.get("size", 0)
                if sz > 1_000_000:
                    sz_t = f"{sz/1_000_000:.1f}M"
                elif sz > 1000:
                    sz_t = f"{sz/1000:.0f}K"
                else:
                    sz_t = str(sz)
                c.create_text(name_w + 10, y + 5, text=sz_t,
                              anchor="nw", fill=s, font=font_info, tags="list_item")

            mt = item.get("mtime", "")
            if mt:
                try:
                    if isinstance(mt, (int, float)):
                        mt = datetime.fromtimestamp(mt).strftime("%m-%d %H:%M")
                except Exception:
                    pass
            c.create_text(name_w + size_w + 10, y + 5, text=str(mt)[:14],
                          anchor="nw", fill=s, font=font_info, tags="list_item")

    def get_selected(self):
        if self._selected is not None and 0 <= self._selected < len(self._items):
            return self._items[self._selected]
        return None

    def refresh_theme(self):
        self._canvas.configure(bg=ThemeColors.get("bg"))
        self._bg_cache_key = None
        self._redraw()


# 远程文件列表（Canvas 渲染，非 pillui）
class CanvasFileList(_CanvasListBase):
    def __init__(self, master, **kw):
        super().__init__(master, is_local=False, **kw)


# 本地文件列表（Canvas 渲染，非 pillui）
class LocalFileList(_CanvasListBase):
    def __init__(self, master, **kw):
        super().__init__(master, is_local=True, **kw)
        self.current_path = os.path.expanduser("~")
        self._load_token = 0
        self._load()

    def _load(self):
        """线程安全加载本地目录。"""
        self._load_token += 1
        token = self._load_token
        path = self.current_path

        def _do():
            try:
                entries = []
                for entry in os.scandir(path):
                    st = entry.stat()
                    entries.append({
                        "name": entry.name,
                        "is_dir": entry.is_dir(),
                        "size": st.st_size if not entry.is_dir() else 0,
                        "mtime": st.st_mtime,
                    })
                entries.sort(key=lambda e: (not e["is_dir"], e["name"].lower()))
                if self._load_token == token:
                    self.after(0, lambda: self.set_items(entries))
            except Exception as e:
                print(f"本地目录加载失败: {e}")
                if self._load_token == token:
                    self.after(0, lambda: self.set_items([]))

        threading.Thread(target=_do, daemon=True).start()

    def navigate(self, path):
        if os.path.isdir(path):
            self.current_path = path
            self._load()

    def go_up(self):
        parent = os.path.dirname(self.current_path)
        if parent and parent != self.current_path:
            self.navigate(parent)

    def refresh(self):
        self._load()


# ============================================================
#  FileBrowser — 主控制器 (v3: 双栏 + 进度 + 运行)
# ============================================================

# 文件管理器 — 双栏模式 + 进度回调 + 一键运行
class FileBrowser(tk.Frame):

    def __init__(self, master, ssh_client, config=None, app_ref=None):
        super().__init__(master, bg=ThemeColors.get("bg"))
        self._ssh = ssh_client
        self._config = config or {}
        self._app = app_ref
        self._cwd = "/home/pi"
        self._mode = "single"
        self._local_path = os.path.expanduser("~")

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=0)

        self._build_toolbar()
        self._build_content()
        self._build_statusbar()

    # ===== 工具栏 =====

    def _build_toolbar(self):
        bar = tk.Frame(self, bg=ThemeColors.get("bg_card"), height=38)
        bar.grid(row=0, column=0, sticky="ew")
        bar.grid_propagate(False)

        # 双栏切换
        self._btn_mode = tk.Button(bar, text="双栏", command=self._toggle_mode,
                                   bg="#1E3A5A", fg="white", relief="flat",
                                   font=("Segoe UI", 10), padx=8)
        self._btn_mode.pack(side="left", padx=3, pady=4)

        # 跨栏传输按钮（单栏时隐藏）
        self._btn_to_local = tk.Button(bar, text="下载到本地",
                                       command=self._download_to_local,
                                       bg="#1E3A5A", fg="white", relief="flat",
                                       font=("Segoe UI", 9), padx=6)
        self._btn_to_remote = tk.Button(bar, text="上传到树莓派",
                                        command=self._upload_from_local,
                                        bg="#1E3A5A", fg="white", relief="flat",
                                        font=("Segoe UI", 9), padx=6)

        # 操作按钮
        for text, cmd in [
            ("上传", self._upload_file),
            ("下载", self._download_selected),
            ("运行", self._run_selected),
            ("新建", self._mkdir),
            ("重命名", self._rename_selected),
            ("删除", self._delete_selected),
        ]:
            bg = "#2B5B2B" if text == "运行" else "#333333"
            tk.Button(bar, text=text, command=cmd,
                     bg=bg, fg="white", relief="flat",
                     font=("Segoe UI", 10), padx=8).pack(
                side="left", padx=2, pady=4)

    # ===== 内容区 =====

    def _build_content(self):
        self._list_container = tk.Frame(self, bg=ThemeColors.get("bg"))
        self._list_container.grid(row=1, column=0, sticky="nsew")
        self._list_container.grid_columnconfigure(0, weight=1)
        self._list_container.grid_columnconfigure(1, weight=0)
        self._list_container.grid_rowconfigure(0, weight=1)

        # Canvas backgrounds use solid theme color (no background image applied here)


        # 远程列表
        self._file_list = CanvasFileList(self._list_container)
        self._file_list.grid(row=0, column=0, sticky="nsew")
        self._file_list.on_dblclick = self._on_remote_dblclick
        self._file_list.on_rightclick = self._on_remote_rightclick

        # 本地列表（双栏时显示）
        self._local_list = LocalFileList(self._list_container)
        self._local_list.on_dblclick = self._on_local_dblclick
        self._local_list.on_rightclick = self._on_local_rightclick

    def _toggle_mode(self):
        if self._mode == "single":
            self._mode = "dual"
            self._btn_mode.configure(text="单栏", bg="#2A5A2A")
            self._list_container.grid_columnconfigure(1, weight=1)
            self._local_list.grid(row=0, column=1, sticky="nsew")
            self._btn_to_local.pack(side="left", padx=2, pady=4)
            self._btn_to_remote.pack(side="left", padx=2, pady=4)
            # 强制几何更新，让 Canvas 拿到真实宽度后再加载
            self._list_container.update_idletasks()
            self._local_list.navigate(self._local_list.current_path)
            self.after(50, lambda: (self._local_list._redraw(), self._file_list._redraw()))
        else:
            self._mode = "single"
            self._btn_mode.configure(text="双栏", bg="#1E3A5A")
            self._list_container.grid_columnconfigure(1, weight=0)
            self._local_list.grid_remove()
            self._btn_to_local.pack_forget()
            self._btn_to_remote.pack_forget()
            self.after(50, self._file_list._redraw)

    # ===== 状态栏 =====

    def _build_statusbar(self):
        bar = tk.Frame(self, bg=ThemeColors.get("bg_card"), height=28)
        bar.grid(row=2, column=0, sticky="ew")
        bar.grid_propagate(False)

        self._progress = ttk.Progressbar(bar, mode="determinate", length=200)
        self._status_label = tk.Label(bar, text="", bg=ThemeColors.get("bg_card"),
                                      fg=ThemeColors.get("text_secondary"),
                                      font=("Segoe UI", 9))
        self._status_label.pack(side="left", padx=10)

    # ===== 远程操作 =====

    def refresh(self):
        if not self._ssh.connected:
            return
        def _fetch():
            try:
                items = self._ssh.list_dir(self._cwd)
                self.after(0, lambda: self._file_list.set_items(items))
            except Exception as e:
                print(f"远程目录列表获取失败: {e}")
        threading.Thread(target=_fetch, daemon=True).start()

    def _on_remote_dblclick(self, item, idx):
        if item.get("is_dir"):
            self._cwd = f"{self._cwd.rstrip('/')}/{item['name']}"
            self.refresh()

    def _on_remote_rightclick(self, item, idx, event):
        menu = Menu(self, tearoff=0)
        menu.add_command(label="下载", command=self._download_selected)
        if not item.get("is_dir"):
            menu.add_command(label="运行", command=self._run_selected)
        menu.add_separator()
        menu.add_command(label="重命名", command=self._rename_selected)
        menu.add_command(label="删除", command=self._delete_selected)
        menu.add_separator()
        menu.add_command(label="新建文件夹", command=self._mkdir)
        menu.post(event.x_root, event.y_root)

    # ===== 本地操作 =====

    def _on_local_dblclick(self, item, idx):
        if item.get("is_dir"):
            new_path = os.path.join(self._local_list.current_path, item["name"])
            self._local_list.navigate(new_path)

    def _on_local_rightclick(self, item, idx, event):
        menu = Menu(self, tearoff=0)
        menu.add_command(label="上传到树莓派", command=self._upload_from_local)
        menu.post(event.x_root, event.y_root)

    # ===== 文件操作 =====

    def _upload_file(self):
        if not self._ssh.connected:
            return
        paths = filedialog.askopenfilenames(title="选择要上传的文件")
        if not paths:
            return
        def _do():
            for path in paths:
                remote = f"{self._cwd}/{os.path.basename(path)}"
                ok, msg = self._ssh.upload_file(path, remote)
                if not ok:
                    self.after(0, lambda m=msg: messagebox.showerror("上传失败", m))
            self.after(0, self.refresh)
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
        self._do_transfer("download", f"{self._cwd}/{sel['name']}",
                          os.path.join(dest, sel['name']))

    def _download_to_local(self):
        if not self._ssh.connected or self._mode != "dual":
            return
        sel = self._file_list.get_selected()
        if not sel:
            return
        self._do_transfer("download", f"{self._cwd}/{sel['name']}",
                          os.path.join(self._local_list.current_path, sel['name']))

    def _upload_from_local(self):
        if not self._ssh.connected or self._mode != "dual":
            return
        sel = self._local_list.get_selected()
        if not sel:
            return
        local = os.path.join(self._local_list.current_path, sel['name'])
        self._do_transfer("upload", local, f"{self._cwd}/{sel['name']}")

    def _do_transfer(self, direction, src, dst):
        self._progress.pack(side="right", padx=10, pady=2)
        self._progress.configure(value=0)
        self._status_label.configure(text="上传中..." if direction == "upload" else "下载中...")

        def _progress_cb(transferred, total):
            if total > 0:
                self.after(0, lambda: self._progress.configure(
                    value=int(transferred / total * 100)))

        def _do():
            if direction == "upload":
                ok, msg = self._ssh.upload_file(src, dst, _progress_cb)
            else:
                ok, msg = self._ssh.download_file(src, dst, _progress_cb)
            self.after(0, lambda: self._on_transfer_done(ok, msg))

        threading.Thread(target=_do, daemon=True).start()

    def _on_transfer_done(self, ok, msg):
        self._progress.pack_forget()
        self._status_label.configure(text="传输完成" if ok else f"失败: {msg}")
        self.after(3000, lambda: self._status_label.configure(text=""))
        if ok:
            self.refresh()
            if self._mode == "dual":
                self._local_list.refresh()

    def _run_selected(self):
        if not self._ssh.connected:
            return
        sel = self._file_list.get_selected()
        if not sel or sel.get("is_dir"):
            return
        name = sel['name']
        ext = os.path.splitext(name)[1].lower()
        remote = f"{self._cwd}/{name}"

        if ext in (".py", ".py3"):
            cmd = f"python3 {shlex.quote(remote)}"
        elif ext in (".sh", ".bash"):
            cmd = f"bash {shlex.quote(remote)}"
        else:
            cmd = f"chmod +x {shlex.quote(remote)} && {shlex.quote(remote)}"

        # 优先推送到终端页
        if self._app and hasattr(self._app, '_terminal_page'):
            tp = self._app._terminal_page
            self._app._show_page("terminal")
            tp._add_session(f"运行: {name[:12]}")
            tab = tp._active_tab()
            if tab:
                tab._entry.delete(0, "end")
                tab._entry.insert(0, cmd)
                tab._on_send()
            return

        # 兜底：弹窗显示结果
        def _do():
            ec, out, err = self._ssh.exec_command(cmd, timeout=120)
            self.after(0, lambda: self._show_run_result(out, err, ec))

        threading.Thread(target=_do, daemon=True).start()

    def _show_run_result(self, stdout, stderr, exit_code):
        dialog = tk.Toplevel(self)
        dialog.title("运行结果")
        dialog.geometry("700x500")
        dialog.configure(bg=ThemeColors.get("bg"))

        text = tk.Text(dialog, bg=ThemeColors.get("bg_card"),
                       fg=ThemeColors.get("text"),
                       insertbackground=ThemeColors.get("text"),
                       font=("Consolas", 10), relief="flat")
        text.pack(fill="both", expand=True, padx=10, pady=10)
        text.insert("end", f"=== stdout ===\n{stdout}\n")
        text.insert("end", f"=== stderr ===\n{stderr}\n")
        text.insert("end", f"=== exit code: {exit_code} ===\n")
        text.configure(state="disabled")

        tk.Button(dialog, text="关闭", command=dialog.destroy,
                 bg="#333333", fg="white", relief="flat").pack(pady=10)

    def _mkdir(self):
        if not self._ssh.connected:
            return
        def _do():
            self._ssh.create_remote_dir(f"{self._cwd}/新建文件夹")
            self.after(0, self.refresh)
        threading.Thread(target=_do, daemon=True).start()

    def _delete_selected(self):
        if not self._ssh.connected:
            return
        sel = self._file_list.get_selected()
        if not sel:
            return
        if not messagebox.askyesno("确认删除", f"删除 {sel.get('name')}？"):
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
        old = f"{self._cwd}/{sel['name']}"
        new = f"{self._cwd}/renamed_{sel['name']}"
        def _do():
            self._ssh.rename_remote(old, new)
            self.after(0, self.refresh)
        threading.Thread(target=_do, daemon=True).start()

    def refresh_theme(self):
        self.configure(bg=ThemeColors.get("bg"))
        self._file_list.refresh_theme()
        if self._mode == "dual":
            self._local_list.refresh_theme()
