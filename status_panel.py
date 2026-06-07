"""
PiManager 状态监控面板 - 树莓派实时系统状态
"""
import customtkinter as ctk
import threading
from typing import Optional


class StatusPanel(ctk.CTkFrame):
    """系统状态监控面板"""

    def __init__(self, master, ssh_client, config: dict = None):
        super().__init__(master, fg_color="transparent")
        self._ssh = ssh_client
        self._config = config or {}
        self._refresh_job = None
        self._refresh_interval = self._config.get("behavior", {}).get("refresh_interval", 3)

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=0)
        self.grid_rowconfigure(3, weight=0)
        self.grid_rowconfigure(4, weight=0)
        self.grid_rowconfigure(5, weight=1)

        self._build_widgets()
        self._show_disconnected()

    def _build_widgets(self):
        """构建 UI 组件"""
        pad = {"padx": 10, "pady": 6}

        # ===== 系统信息卡片 =====
        info_frame = ctk.CTkFrame(self)
        info_frame.grid(row=0, column=0, columnspan=2, sticky="ew", **pad)
        info_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(info_frame, text="🖥️", font=ctk.CTkFont(size=20)).grid(
            row=0, column=0, rowspan=3, padx=(12, 8), pady=10)

        self._lbl_hostname = ctk.CTkLabel(
            info_frame, text="未连接", font=ctk.CTkFont(size=16, weight="bold"))
        self._lbl_hostname.grid(row=0, column=1, sticky="w", padx=(0, 12), pady=(10, 0))

        self._lbl_os = ctk.CTkLabel(info_frame, text="", text_color="gray")
        self._lbl_os.grid(row=1, column=1, sticky="w", padx=(0, 12))

        self._lbl_kernel = ctk.CTkLabel(info_frame, text="", text_color="gray")
        self._lbl_kernel.grid(row=2, column=1, sticky="w", padx=(0, 12), pady=(0, 10))

        # ===== CPU =====
        self._cpu_frame = self._make_card("🔥 CPU", 0, 0)
        self._cpu_bar = ctk.CTkProgressBar(self._cpu_frame)
        self._cpu_bar.grid(row=1, column=0, columnspan=2, sticky="ew", padx=12, pady=(0, 4))
        self._cpu_bar.set(0)
        self._cpu_pct = ctk.CTkLabel(self._cpu_frame, text="0%", font=ctk.CTkFont(size=24, weight="bold"))
        self._cpu_pct.grid(row=0, column=1, sticky="e", padx=12, pady=(8, 0))

        self._temp_frame = self._make_card("🌡️ 温度", 0, 1)
        self._temp_label = ctk.CTkLabel(
            self._temp_frame, text="--°C", font=ctk.CTkFont(size=28, weight="bold"))
        self._temp_label.grid(row=0, column=1, sticky="e", padx=12, pady=8)

        # ===== 内存 =====
        self._mem_frame = self._make_card("🧠 内存", 1, 0)
        self._mem_bar = ctk.CTkProgressBar(self._mem_frame)
        self._mem_bar.grid(row=1, column=0, columnspan=2, sticky="ew", padx=12, pady=(0, 4))
        self._mem_bar.set(0)
        self._mem_text = ctk.CTkLabel(self._mem_frame, text="0 / 0 MB", font=ctk.CTkFont(size=14))
        self._mem_text.grid(row=0, column=1, sticky="e", padx=12, pady=(8, 0))

        # ===== 磁盘 =====
        self._disk_frame = self._make_card("💾 磁盘", 1, 1)
        self._disk_bar = ctk.CTkProgressBar(self._disk_frame)
        self._disk_bar.grid(row=1, column=0, columnspan=2, sticky="ew", padx=12, pady=(0, 4))
        self._disk_bar.set(0)
        self._disk_text = ctk.CTkLabel(self._disk_frame, text="0 / 0 MB", font=ctk.CTkFont(size=14))
        self._disk_text.grid(row=0, column=1, sticky="e", padx=12, pady=(8, 0))

        # ===== 运行信息 =====
        info2_frame = ctk.CTkFrame(self)
        info2_frame.grid(row=2, column=0, columnspan=2, sticky="ew", **pad)
        info2_frame.grid_columnconfigure(1, weight=1)

        self._lbl_uptime = ctk.CTkLabel(info2_frame, text="⏱ 运行时间: --", anchor="w")
        self._lbl_uptime.grid(row=0, column=0, sticky="w", padx=12, pady=(8, 0))

        self._lbl_load = ctk.CTkLabel(info2_frame, text="📊 负载: --", anchor="w")
        self._lbl_load.grid(row=1, column=0, sticky="w", padx=12, pady=(0, 8))

        # ===== 刷新按钮 =====
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=3, column=0, columnspan=2, sticky="e", **pad)

        self._btn_refresh = ctk.CTkButton(
            btn_frame, text="🔄 刷新", width=100, command=self.refresh,
            fg_color="#2B5B2B", hover_color="#3A7A3A")
        self._btn_refresh.pack(side="right", padx=5)

        self._lbl_last_update = ctk.CTkLabel(btn_frame, text="", text_color="gray")
        self._lbl_last_update.pack(side="right", padx=10)

    def _make_card(self, title: str, row: int, col: int) -> ctk.CTkFrame:
        """创建一张状态卡片"""
        frame = ctk.CTkFrame(self)
        frame.grid(row=row + 1, column=col, sticky="nsew", padx=5, pady=3)
        frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(frame, text=title, font=ctk.CTkFont(size=13, weight="bold"),
                     anchor="w").grid(row=0, column=0, sticky="w", padx=12, pady=(8, 0))
        return frame

    def refresh(self):
        """刷新状态数据"""
        if not self._ssh.connected:
            self._show_disconnected()
            return

        def _fetch():
            status = self._ssh.get_system_status()
            self.after(0, lambda: self._update_ui(status))

        threading.Thread(target=_fetch, daemon=True).start()

    def _update_ui(self, s: dict):
        """更新 UI 显示"""
        if s.get("error") and not s.get("hostname"):
            return

        # 主机信息
        self._lbl_hostname.configure(text=f"🖥️ {s.get('hostname', '?')}")
        self._lbl_os.configure(text=s.get('os_version', ''))
        self._lbl_kernel.configure(text=f"Linux {s.get('kernel', '')}")

        # CPU
        cpu = s.get("cpu_percent", 0)
        self._cpu_bar.set(cpu / 100)
        self._cpu_pct.configure(text=f"{cpu:.1f}%")

        # 温度
        temp = s.get("cpu_temp", 0)
        if temp >= 70:
            temp_color = "#FF4444"
        elif temp >= 50:
            temp_color = "#FFB347"
        else:
            temp_color = "#4CAF50"
        self._temp_label.configure(text=f"{temp:.1f}°C", text_color=temp_color)

        # 内存
        mem_pct = s.get("memory_percent", 0)
        self._mem_bar.set(mem_pct / 100)
        self._mem_text.configure(
            text=f"{s.get('memory_used', 0)} / {s.get('memory_total', 0)} MB")

        # 磁盘
        disk_pct = s.get("disk_percent", 0)
        self._disk_bar.set(disk_pct / 100)
        disk_used = s.get('disk_used', 0)
        disk_total = s.get('disk_total', 0)
        if disk_total >= 1024:
            self._disk_text.configure(
                text=f"{disk_used/1024:.1f} / {disk_total/1024:.1f} GB")
        else:
            self._disk_text.configure(text=f"{disk_used} / {disk_total} MB")

        # 运行信息
        self._lbl_uptime.configure(text=f"⏱ 运行时间: {s.get('uptime', '--')}")
        self._lbl_load.configure(text=f"📊 负载: {s.get('load_avg', '--')}")

        # 时间戳
        import datetime
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self._lbl_last_update.configure(text=f"最后更新: {ts}")

        # 进度条颜色
        self._set_bar_colors(mem_pct, disk_pct)

    def _set_bar_colors(self, mem_pct, disk_pct):
        """根据使用率设置进度条颜色"""
        for bar, pct in [(self._mem_bar, mem_pct), (self._disk_bar, disk_pct)]:
            if pct >= 90:
                bar.configure(progress_color="#FF4444")
            elif pct >= 70:
                bar.configure(progress_color="#FFB347")
            else:
                bar.configure(progress_color="#4CAF50")

    def _show_disconnected(self):
        """显示未连接状态"""
        self._lbl_hostname.configure(text="🔴 未连接")
        self._lbl_os.configure(text="请先连接到树莓派")
        self._lbl_kernel.configure(text="")
        self._cpu_bar.set(0)
        self._cpu_pct.configure(text="--%")
        self._temp_label.configure(text="--°C", text_color="gray")
        self._mem_bar.set(0)
        self._mem_text.configure(text="-- / -- MB")
        self._disk_bar.set(0)
        self._disk_text.configure(text="-- / -- MB")
        self._lbl_uptime.configure(text="⏱ 运行时间: --")
        self._lbl_load.configure(text="📊 负载: --")
        self._lbl_last_update.configure(text="")

    def start_auto_refresh(self, interval_seconds: int = None):
        """启动自动刷新"""
        if interval_seconds is not None:
            self._refresh_interval = interval_seconds
        self.stop_auto_refresh()
        self._do_auto_refresh()

    def _do_auto_refresh(self):
        """执行自动刷新"""
        if self._ssh.connected:
            self.refresh()
        self._refresh_job = self.after(int(self._refresh_interval * 1000), self._do_auto_refresh)

    def stop_auto_refresh(self):
        """停止自动刷新"""
        if self._refresh_job:
            self.after_cancel(self._refresh_job)
            self._refresh_job = None


if __name__ == "__main__":
    import sys
    sys.path.insert(0, "..")
    from pimanager.ssh_client import SSHClient

    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("green")

    class TestWindow(ctk.CTk):
        def __init__(self):
            super().__init__()
            self.title("StatusPanel 测试")
            self.geometry("800x600")
            self.grid_columnconfigure(0, weight=1)
            self.grid_rowconfigure(0, weight=1)

            self.ssh = SSHClient()
            self.panel = StatusPanel(self, self.ssh)
            self.panel.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

            # 测试连接
            ok, msg = self.ssh.connect(
                host="muchenxi-20081128.local",
                username="chenxi",
                key_path=r"C:\Users\m2008\.ssh\id_ed25519"
            )
            print(f"连接: {msg}")
            if ok:
                self.panel.refresh()
                self.panel.start_auto_refresh(3)

        def on_close(self):
            self.panel.stop_auto_refresh()
            self.ssh.disconnect()
            self.destroy()

    app = TestWindow()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()
