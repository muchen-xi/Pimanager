"""
PiManager 状态监控面板 v2 — Pillow Canvas 渲染
"""
import tkinter as tk
import threading
import datetime

from .theme import ThemeColors
from .pillui import PageCanvas, PillowButton, PillowLabel, PillowProgressBar, PillowCard
from .app import BackgroundManager


class StatusPanel(tk.Frame):
    """系统状态监控 — 全 Pillow 渲染。"""

    def __init__(self, master, ssh_client, config: dict = None):
        super().__init__(master, bg=ThemeColors.get("bg"))
        self._ssh = ssh_client
        self._config = config or {}
        self._refresh_job = None
        self._refresh_interval = self._config.get("behavior", {}).get("refresh_interval", 3)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # PageCanvas
        self._canvas = PageCanvas(self, width=800, height=600,
                                  bg=ThemeColors.get("bg"))
        self._canvas.grid(row=0, column=0, sticky="nsew")
        BackgroundManager.register(self._canvas)

        self._build()

    def _build(self):
        """构建所有 Pillow 组件。"""
        c = self._canvas

        # ---- 系统信息卡片 ----
        c.add("info_card", PillowCard(10, 10, 540, 70, title="🖥️ 系统信息",
                                      fill="#161B22", border="gray30"))
        self._lbl_hostname = PillowLabel("🔴 未连接", 24, 38, 250, 24,
                                         font_size=16, weight="bold",
                                         color="#C9D1D9")
        c.add("hostname", self._lbl_hostname)
        self._lbl_os = PillowLabel("请先连接到树莓派", 24, 58, 400, 18,
                                   font_size=11, color="#8B949E")
        c.add("os", self._lbl_os)
        self._lbl_kernel = PillowLabel("", 400, 58, 160, 18,
                                       font_size=11, color="#8B949E", align="right")
        c.add("kernel", self._lbl_kernel)

        # ---- CPU 卡片 ----
        c.add("cpu_card", PillowCard(10, 90, 265, 100, title="🔥 CPU",
                                     fill="#161B22", border="gray30"))
        self._cpu_bar = PillowProgressBar(24, 125, 220, 16)
        c.add("cpu_bar", self._cpu_bar)
        self._cpu_pct = PillowLabel("--%", 180, 108, 80, 28,
                                    font_size=22, weight="bold",
                                    color="#C9D1D9", align="right")
        c.add("cpu_pct", self._cpu_pct)

        # ---- 温度卡片 ----
        c.add("temp_card", PillowCard(285, 90, 265, 100, title="🌡️ 温度",
                                      fill="#161B22", border="gray30"))
        self._temp_label = PillowLabel("--°C", 180, 108, 80, 28,
                                       font_size=26, weight="bold",
                                       color="#8B949E", align="right")
        c.add("temp", self._temp_label)

        # ---- 内存卡片 ----
        c.add("mem_card", PillowCard(10, 200, 265, 100, title="🧠 内存",
                                     fill="#161B22", border="gray30"))
        self._mem_bar = PillowProgressBar(24, 235, 220, 16)
        c.add("mem_bar", self._mem_bar)
        self._mem_text = PillowLabel("-- / -- MB", 24, 215, 220, 20,
                                     font_size=13, color="#C9D1D9", align="right")
        c.add("mem_text", self._mem_text)

        # ---- 磁盘卡片 ----
        c.add("disk_card", PillowCard(285, 200, 265, 100, title="💾 磁盘",
                                      fill="#161B22", border="gray30"))
        self._disk_bar = PillowProgressBar(24, 235, 220, 16)
        c.add("disk_bar", self._disk_bar)
        self._disk_text = PillowLabel("-- / -- MB", 24, 215, 220, 20,
                                      font_size=13, color="#C9D1D9", align="right")
        c.add("disk_text", self._disk_text)

        # ---- 运行信息 ----
        c.add("info2_card", PillowCard(10, 310, 540, 50, fill="#161B22", border="gray30"))
        self._lbl_uptime = PillowLabel("⏱ 运行时间: --", 24, 322, 250, 22,
                                       font_size=12, color="#C9D1D9")
        c.add("uptime", self._lbl_uptime)
        self._lbl_load = PillowLabel("📊 负载: --", 290, 322, 250, 22,
                                     font_size=12, color="#C9D1D9")
        c.add("load", self._lbl_load)

        # ---- 刷新按钮 ----
        self._btn_refresh = PillowButton("🔄 刷新", 440, 380, 110, 34,
                                        command=self.refresh, font_size=12)
        c.add("btn_refresh", self._btn_refresh)
        self._lbl_update = PillowLabel("", 10, 385, 420, 24,
                                       font_size=10, color="#8B949E")
        c.add("last_update", self._lbl_update)

        c.render()

    def refresh(self):
        """刷新状态数据。"""
        if not self._ssh.connected:
            self._show_disconnected()
            return

        def _fetch():
            status = self._ssh.get_system_status()
            self.after(0, lambda: self._update_ui(status))

        threading.Thread(target=_fetch, daemon=True).start()

    def _update_ui(self, s: dict):
        if s.get("error") and not s.get("hostname"):
            return

        c = self._canvas

        # 主机信息
        self._lbl_hostname.set_text(f"🖥️ {s.get('hostname', '?')}")
        self._lbl_os.set_text(s.get('os_version', ''))
        self._lbl_kernel.set_text(f"Linux {s.get('kernel', '')}")

        # CPU
        cpu = s.get("cpu_percent", 0)
        self._cpu_bar.set(cpu / 100)
        self._cpu_pct.set_text(f"{cpu:.1f}%")

        # 温度
        temp = s.get("cpu_temp", 0)
        if temp >= 70:
            t_color = ThemeColors.get("warning_strong")
        elif temp >= 50:
            t_color = ThemeColors.get("warning")
        else:
            t_color = ThemeColors.get("status_ok")
        self._temp_label.set_text(f"{temp:.1f}°C")
        self._temp_label.set_color(t_color)

        # 内存
        mem_pct = s.get("memory_percent", 0)
        self._mem_bar.set(mem_pct / 100)
        self._mem_text.set_text(
            f"{s.get('memory_used', 0)} / {s.get('memory_total', 0)} MB")

        # 磁盘
        disk_pct = s.get("disk_percent", 0)
        disk_used = s.get('disk_used', 0)
        disk_total = s.get('disk_total', 0)
        self._disk_bar.set(disk_pct / 100)
        if disk_total >= 1024:
            self._disk_text.set_text(
                f"{disk_used/1024:.1f} / {disk_total/1024:.1f} GB")
        else:
            self._disk_text.set_text(f"{disk_used} / {disk_total} MB")

        # 运行信息
        self._lbl_uptime.set_text(f"⏱ 运行时间: {s.get('uptime', '--')}")
        self._lbl_load.set_text(f"📊 负载: {s.get('load_avg', '--')}")

        # 时间戳
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self._lbl_update.set_text(f"最后更新: {ts}")

        # 进度条颜色
        ok, warn, danger = (ThemeColors.get(k) for k in
                            ("status_ok", "warning", "warning_strong"))
        for bar, pct in [(self._cpu_bar, cpu), (self._mem_bar, mem_pct),
                          (self._disk_bar, disk_pct)]:
            bar.set_color(ok if pct < 50 else (warn if pct < 80 else danger))

    def _show_disconnected(self):
        self._lbl_hostname.set_text("🔴 未连接")
        self._lbl_os.set_text("请先连接到树莓派")
        self._lbl_kernel.set_text("")
        self._cpu_bar.set(0)
        self._cpu_pct.set_text("--%")
        self._temp_label.set_text("--°C")
        self._temp_label.set_color("#8B949E")
        self._mem_bar.set(0)
        self._mem_text.set_text("-- / -- MB")
        self._disk_bar.set(0)
        self._disk_text.set_text("-- / -- MB")
        self._lbl_uptime.set_text("⏱ 运行时间: --")
        self._lbl_load.set_text("📊 负载: --")
        self._lbl_update.set_text("")

    def refresh_theme(self):
        """主题切换时重绘。"""
        self._canvas.set_bg_color(ThemeColors.get("bg"))
        self._canvas.render()

    def start_auto_refresh(self, interval_seconds: int = None):
        if interval_seconds is not None:
            self._refresh_interval = interval_seconds
        self.stop_auto_refresh()
        self._do_auto_refresh()

    def _do_auto_refresh(self):
        if self._ssh.connected:
            self.refresh()
        self._refresh_job = self.after(
            int(self._refresh_interval * 1000), self._do_auto_refresh)

    def stop_auto_refresh(self):
        if self._refresh_job:
            self.after_cancel(self._refresh_job)
            self._refresh_job = None
