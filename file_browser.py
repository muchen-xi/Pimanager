"""
PiManager 文件浏览器 - 远程文件管理（浏览/上传/下载/删除/重命名）
"""
import customtkinter as ctk
import threading
import os
import datetime
from tkinter import filedialog, messagebox, Menu


class FileBrowser(ctk.CTkFrame):
    """远程文件管理器"""

    def __init__(self, master, ssh_client, config: dict = None):
        super().__init__(master, fg_color="transparent", corner_radius=0)
        self._ssh = ssh_client
        self._config = config or {}
        self._current_path = "/home/chenxi"
        self._selected_file = None
        self._history = []  # 导航历史

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)  # 路径栏
        self.grid_rowconfigure(1, weight=0)  # 表头
        self.grid_rowconfigure(2, weight=1)  # 文件列表
        self.grid_rowconfigure(3, weight=0)  # 操作栏
        self.grid_rowconfigure(4, weight=0)  # 进度条

        self._build_widgets()

    def _build_widgets(self):
        """构建 UI"""
        # ===== 路径导航栏 =====
        nav_frame = ctk.CTkFrame(self)
        nav_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=(5, 2))
        nav_frame.grid_columnconfigure(1, weight=1)

        self._btn_home = ctk.CTkButton(
            nav_frame, text="🏠", width=36, command=lambda: self.navigate("/home/chenxi"),
            fg_color="transparent", hover_color="#333")
        self._btn_home.grid(row=0, column=0, padx=(5, 2), pady=5)

        self._btn_up = ctk.CTkButton(
            nav_frame, text="⬆", width=36, command=self._go_up,
            fg_color="transparent", hover_color="#333")
        self._btn_up.grid(row=0, column=1, padx=2, pady=5)

        self._path_frame = ctk.CTkFrame(nav_frame, fg_color="transparent", corner_radius=0)
        self._path_frame.grid(row=0, column=2, sticky="ew", padx=5)

        self._btn_refresh = ctk.CTkButton(
            nav_frame, text="🔄", width=36, command=self.refresh,
            fg_color="transparent", hover_color="#333")
        self._btn_refresh.grid(row=0, column=3, padx=(2, 5), pady=5)

        # ===== 文件列表头 =====
        header_frame = ctk.CTkFrame(
            self, height=30, fg_color="transparent", corner_radius=0,
            border_width=1, border_color=("gray70", "gray35"))
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

        # ===== 文件列表滚动区 =====
        self._file_scroll = ctk.CTkScrollableFrame(self, fg_color="transparent", corner_radius=0)
        self._file_scroll.grid(row=2, column=0, sticky="nsew", padx=5, pady=(0, 5))
        self._file_scroll.grid_columnconfigure(0, weight=1)

        self._file_rows = []
        self._selected_row = None

        # ===== 操作按钮栏 =====
        btn_frame = ctk.CTkFrame(self)
        btn_frame.grid(row=3, column=0, sticky="ew", padx=5, pady=(0, 5))

        btn_style = {"width": 90, "height": 30}
        self._btn_upload = ctk.CTkButton(
            btn_frame, text="📤 上传", command=self._upload_file, **btn_style)
        self._btn_upload.pack(side="left", padx=3)

        self._btn_download = ctk.CTkButton(
            btn_frame, text="📥 下载", command=self._download_selected, **btn_style)
        self._btn_download.pack(side="left", padx=3)

        self._btn_mkdir = ctk.CTkButton(
            btn_frame, text="📁 新建文件夹", command=self._create_dir, **btn_style)
        self._btn_mkdir.pack(side="left", padx=3)

        self._btn_delete = ctk.CTkButton(
            btn_frame, text="🗑 删除", command=self._delete_selected, **btn_style,
            fg_color="#8B0000", hover_color="#A00000")
        self._btn_delete.pack(side="left", padx=3)

        self._btn_rename = ctk.CTkButton(
            btn_frame, text="✏️ 重命名", command=self._rename_selected, **btn_style)
        self._btn_rename.pack(side="left", padx=3)

        # ===== 进度条 =====
        self._progress = ctk.CTkProgressBar(self)
        self._progress.grid(row=4, column=0, sticky="ew", padx=10, pady=(0, 5))
        self._progress.set(0)
        self._progress.grid_remove()  # 默认隐藏

        self._lbl_progress = ctk.CTkLabel(self, text="", text_color="gray")
        self._lbl_progress.grid(row=4, column=0, sticky="e", padx=15, pady=(0, 5))

    # ===== 导航 =====

    def navigate(self, path: str):
        """导航到指定路径"""
        self._current_path = path
        self._selected_file = None
        self.refresh()

    def _go_up(self):
        """返回上级目录"""
        parent = os.path.dirname(self._current_path)
        if parent and parent != self._current_path:
            self.navigate(parent)

    def refresh(self):
        """刷新当前目录"""
        if not self._ssh.connected:
            self._show_empty("未连接到树莓派")
            return

        self._show_empty("加载中...")

        def _fetch():
            items = self._ssh.list_dir(self._current_path)
            self.after(0, lambda: self._render_files(items))

        threading.Thread(target=_fetch, daemon=True).start()

    def _render_files(self, items: list):
        """渲染文件列表"""
        # 清除旧行
        for row in self._file_rows:
            row.destroy()
        self._file_rows.clear()
        self._selected_row = None
        self._selected_file = None

        # 更新面包屑
        self._update_breadcrumb()

        if not items:
            self._show_empty("目录为空")
            return

        for i, item in enumerate(items):
            row_frame = ctk.CTkFrame(
                self._file_scroll, fg_color="transparent",
                corner_radius=0)
            row_frame.grid(row=i, column=0, sticky="ew", pady=1)
            row_frame.grid_columnconfigure(0, weight=1)

            # 图标 + 名称
            icon = "📁" if item["is_dir"] else "📄"
            name_label = ctk.CTkLabel(
                row_frame, text=f" {icon}  {item['name']}", anchor="w",
                font=ctk.CTkFont(size=13))
            name_label.grid(row=0, column=0, sticky="w", padx=8, pady=3)

            # 大小
            if item["is_dir"]:
                size_str = "--"
            else:
                size = item["size"]
                if size >= 1073741824:
                    size_str = f"{size/1073741824:.1f} GB"
                elif size >= 1048576:
                    size_str = f"{size/1048576:.1f} MB"
                elif size >= 1024:
                    size_str = f"{size/1024:.1f} KB"
                else:
                    size_str = f"{size} B"
            ctk.CTkLabel(row_frame, text=size_str, width=90, anchor="e",
                         font=ctk.CTkFont(size=12)).grid(
                row=0, column=1, sticky="e", padx=8)

            # 修改时间
            try:
                mtime = datetime.datetime.fromtimestamp(item["mtime"]).strftime("%Y-%m-%d %H:%M")
            except Exception:
                mtime = "--"
            ctk.CTkLabel(row_frame, text=mtime, width=160, anchor="e",
                         font=ctk.CTkFont(size=12)).grid(
                row=0, column=2, sticky="e", padx=8)

            # 绑定点击事件
            for widget in [row_frame, name_label]:
                widget.bind("<Button-1>", lambda e, idx=i, it=item: self._on_click(e, idx, it))
                widget.bind("<Double-Button-1>", lambda e, it=item: self._on_double_click(it))
                widget.bind("<Button-3>", lambda e, it=item: self._on_right_click(e, it))

            self._file_rows.append(row_frame)

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
            hover_color="#333",
            command=lambda: self.navigate("/"))
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
                hover_color="#333",
                command=lambda p=path_so_far: self.navigate(p))
            btn.pack(side="left", padx=1)

    def _show_empty(self, msg: str):
        """显示空状态"""
        for row in self._file_rows:
            row.destroy()
        self._file_rows.clear()
        lbl = ctk.CTkLabel(self._file_scroll, text=msg, text_color="gray",
                           font=ctk.CTkFont(size=14))
        lbl.grid(row=0, column=0, pady=30)
        self._file_rows.append(lbl)

    # ===== 点击事件 =====

    def _on_click(self, event, index: int, item: dict):
        """单击选择"""
        self._select_row(index)
        self._selected_file = item["name"]

    def _on_double_click(self, item: dict):
        """双击进入目录或下载文件"""
        if item["is_dir"]:
            new_path = os.path.join(self._current_path, item["name"]).replace("\\", "/")
            self.navigate(new_path)
        else:
            self._selected_file = item["name"]
            self._download_selected()

    def _on_right_click(self, event, item: dict):
        """右键菜单"""
        self._selected_file = item["name"]
        menu = Menu(self, tearoff=0, bg="#2B2B2B", fg="white",
                    activebackground="#444", activeforeground="white")
        menu.add_command(label="📥 下载", command=self._download_selected)
        menu.add_separator()
        if item["is_dir"]:
            menu.add_command(label="📁 进入", command=lambda: self._on_double_click(item))
        menu.add_command(label="✏️ 重命名", command=self._rename_selected)
        menu.add_command(label="🗑 删除", command=self._delete_selected)
        menu.add_separator()
        menu.add_command(label="📁 新建文件夹", command=self._create_dir)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _select_row(self, index: int):
        """高亮选中行"""
        for i, row in enumerate(self._file_rows):
            if isinstance(row, ctk.CTkFrame):
                row.configure(fg_color="#2A5A2A" if i == index else "transparent")

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
            messagebox.showinfo("提示", "暂不支持下载目录，请使用 tar 打包后下载")
            return
        local_dir = filedialog.askdirectory(title="选择保存位置")
        if not local_dir:
            return
        local_path = os.path.join(local_dir, self._selected_file)
        self._do_transfer("download", remote_path, local_path)

    def _do_transfer(self, direction: str, src: str, dst: str):
        """执行文件传输"""
        self._progress.set(0)
        self._progress.grid()
        self._lbl_progress.configure(text=f"{'上传' if direction == 'upload' else '下载'}中...")

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
        self._lbl_progress.configure(text="")
        if ok:
            self.refresh()
        else:
            messagebox.showerror("传输失败", msg)

    def _create_dir(self):
        """创建远程目录"""
        if not self._ssh.connected:
            messagebox.showwarning("未连接", "请先连接到树莓派")
            return
        dialog = ctk.CTkInputDialog(
            text="输入文件夹名称:", title="新建文件夹")
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
        if messagebox.askyesno("确认删除", f"确定要删除 \"{self._selected_file}\" 吗？\n此操作不可恢复！"):
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
        dialog = ctk.CTkInputDialog(
            text="输入新名称:", title="重命名")
        new_name = dialog.get_input()
        if new_name and new_name != self._selected_file:
            old_path = f"{self._current_path}/{self._selected_file}"
            new_path = f"{self._current_path}/{new_name}"
            ok, msg = self._ssh.rename_remote(old_path, new_path)
            if ok:
                self.refresh()
            else:
                messagebox.showerror("重命名失败", msg)


if __name__ == "__main__":
    import sys
    sys.path.insert(0, "..")
    from pimanager.ssh_client import SSHClient

    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("green")

    class TestWindow(ctk.CTk):
        def __init__(self):
            super().__init__()
            self.title("FileBrowser 测试")
            self.geometry("900x650")
            self.grid_columnconfigure(0, weight=1)
            self.grid_rowconfigure(0, weight=1)

            self.ssh = SSHClient()
            self.browser = FileBrowser(self, self.ssh)
            self.browser.grid(row=0, column=0, sticky="nsew")

            ok, msg = self.ssh.connect(
                host="muchenxi-20081128.local",
                username="chenxi",
                key_path=r"C:\Users\m2008\.ssh\id_ed25519"
            )
            print(f"连接: {msg}")
            if ok:
                self.browser.refresh()

        def on_close(self):
            self.ssh.disconnect()
            self.destroy()

    app = TestWindow()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()
