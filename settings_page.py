"""
PiManager 设置页面 v2 — Pillow Canvas 渲染
"""
import tkinter as tk
from tkinter import filedialog, messagebox
import os

from . import __version__
from .theme import ThemeColors
from .pillui import (PageCanvas, PillowButton, PillowLabel,
                     PillowProgressBar, PillowCard)
from .pillui.slider import PillowSlider
from .pillui.checkbox import PillowCheckBox
from .pillui.option_menu import PillowOptionMenu
from .app import BackgroundManager


# 应用设置页面 — 全 Pillow 渲染
class SettingsPage(tk.Frame):

    def __init__(self, master, config, ssh_client=None, app_ref=None):
        super().__init__(master, bg=ThemeColors.get("bg"))
        self._config = config
        self._ssh = ssh_client
        self._app = app_ref

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._canvas = PageCanvas(self, width=800, height=650,
                                  bg=ThemeColors.get("bg"))
        self._canvas.grid(row=0, column=0, sticky="nsew")
        BackgroundManager.register(self._canvas)

        self._build_appearance_card()
        self._build_background_card()
        self._build_behavior_card()
        self._build_about_card()

    # ===== 外观卡片 =====

    def _build_appearance_card(self):
        c = self._canvas
        y0 = 10

        c.add("appearance_card",
              PillowCard(10, y0, 540, 170, title="外观设置",
                         fill="#161B22", border="#4D4D4D"))

        # 主题模式
        self._theme_var = tk.StringVar(
            value=self._config["appearance"]["theme"])
        c.add("theme_label",
              PillowLabel("主题模式", 24, y0 + 40, 100, 24,
                          font_size=12, color="#C9D1D9"))
        c.add("theme_menu",
              PillowOptionMenu(380, y0 + 37, 120, 28,
                               values=["dark", "light"],
                               variable=self._theme_var,
                               command=self._on_theme_change))

        # 颜色主题
        self._color_var = tk.StringVar(
            value=self._config["appearance"]["color_theme"])
        c.add("color_label",
              PillowLabel("颜色主题", 24, y0 + 80, 100, 24,
                          font_size=12, color="#C9D1D9"))
        c.add("color_menu",
              PillowOptionMenu(380, y0 + 77, 120, 28,
                               values=["green", "blue", "dark-blue"],
                               variable=self._color_var,
                               command=self._on_color_theme_change))

        # 字体缩放
        self._scale_var = tk.DoubleVar(
            value=self._config["appearance"]["font_scale"])
        c.add("scale_label",
              PillowLabel("字体缩放", 24, y0 + 120, 100, 24,
                          font_size=12, color="#C9D1D9"))
        c.add("scale_slider",
              PillowSlider(140, y0 + 122, 260, 24,
                           from_val=0.8, to_val=1.5, steps=7,
                           variable=self._scale_var,
                           command=self._on_scale_change))
        self._scale_pct = PillowLabel("1.0x", 410, y0 + 120, 60, 24,
                                      font_size=12, color="#8B949E")
        c.add("scale_pct", self._scale_pct)

    # ===== 背景卡片 =====

    def _build_background_card(self):
        c = self._canvas
        y0 = 190

        c.add("bg_card",
              PillowCard(10, y0, 540, 190, title="背景设置",
                         fill="#161B22", border="#4D4D4D"))

        # 当前背景
        bg_path = self._config["appearance"].get("background_path", "")
        display = os.path.basename(bg_path) if bg_path else "未设置"
        self._bg_label = PillowLabel(f"当前: {display}", 24, y0 + 36, 300, 24,
                                     font_size=12, color="#8B949E")
        c.add("bg_path", self._bg_label)

        # 选择/清除按钮
        c.add("btn_choose_bg",
              PillowButton("选择图片...", 24, y0 + 62, 120, 28,
                           command=self._choose_bg, font_size=11))
        c.add("btn_clear_bg",
              PillowButton("清除背景", 154, y0 + 62, 120, 28,
                           command=self._clear_bg,
                           style="transparent", font_size=11))

        # 透明度
        self._opacity_var = tk.DoubleVar(
            value=self._config["appearance"]["background_opacity"])
        c.add("opacity_label",
              PillowLabel("背景透明度", 24, y0 + 96, 100, 24,
                          font_size=12, color="#C9D1D9"))
        c.add("opacity_slider",
              PillowSlider(140, y0 + 98, 260, 24,
                           from_val=0.05, to_val=0.5, steps=9,
                           variable=self._opacity_var,
                           command=self._on_opacity_change))
        self._opacity_pct = PillowLabel("15%", 410, y0 + 96, 60, 24,
                                        font_size=12, color="#8B949E")
        c.add("opacity_pct", self._opacity_pct)

        # 背景适配模式
        fit_mode = self._config["appearance"].get("background_fit_mode", "cover")
        self._fit_var = tk.StringVar(value=fit_mode)
        c.add("fit_label",
              PillowLabel("适配模式", 24, y0 + 128, 100, 24,
                          font_size=12, color="#C9D1D9"))
        c.add("fit_menu",
              PillowOptionMenu(140, y0 + 126, 130, 28,
                               values=["cover", "contain", "fill", "tile"],
                               variable=self._fit_var,
                               command=self._on_fit_change))

    # ===== 行为卡片 =====

    def _build_behavior_card(self):
        c = self._canvas
        y0 = 390

        c.add("behavior_card",
              PillowCard(10, y0, 540, 155, title="行为设置",
                         fill="#161B22", border="#4D4D4D"))

        # 自动连接
        self._auto_var = tk.BooleanVar(
            value=self._config["behavior"]["auto_connect"])
        c.add("auto_check",
              PillowCheckBox("启动时自动连接树莓派", 24, y0 + 40, 300, 24,
                             variable=self._auto_var))

        # 刷新间隔
        self._refresh_var = tk.IntVar(
            value=self._config["behavior"]["refresh_interval"])
        c.add("refresh_label",
              PillowLabel("状态刷新间隔", 24, y0 + 74, 110, 24,
                          font_size=12, color="#C9D1D9"))
        c.add("refresh_slider",
              PillowSlider(140, y0 + 76, 260, 24,
                           from_val=1, to_val=30, steps=29,
                           variable=self._refresh_var,
                           command=self._on_refresh_change))
        self._refresh_pct = PillowLabel("3秒", 410, y0 + 74, 60, 24,
                                         font_size=12, color="#8B949E")
        c.add("refresh_pct", self._refresh_pct)

        # 删除确认
        self._confirm_var = tk.BooleanVar(
            value=self._config["behavior"]["confirm_before_delete"])
        c.add("confirm_check",
              PillowCheckBox("删除文件前弹出确认对话框", 24, y0 + 108, 300, 24,
                             variable=self._confirm_var))

    # ===== 关于卡片 =====

    def _build_about_card(self):
        c = self._canvas
        y0 = 555

        c.add("about_card",
              PillowCard(10, y0, 540, 100, title="关于",
                         fill="#161B22", border="#4D4D4D"))

        info = 'PiManager v' + __version__ + '\n轻量级树莓派 Zero W 桌面管理器\nPython + tkinter + Pillow + Paramiko\n深色/浅色双主题 · Canvas 原生渲染'
        c.add("about_text",
              PillowLabel(info, 24, y0 + 38, 400, 70,
                          font_size=11, color="#8B949E"))

        c.add("btn_save",
              PillowButton("保存所有设置", 380, y0 + 50, 150, 34,
                           command=self._save_all, font_size=12))

    # ===== 事件处理 =====

    def _on_theme_change(self, theme):
        """主题切换 — 立即应用，无延迟，消除闪烁。"""
        ThemeColors.set_mode(theme)
        if self._app:
            self._app._apply_background()
            self._app.refresh_all_canvases()

    def _on_color_theme_change(self, color_name):
        """颜色主题切换。"""
        ThemeColors.set_color_theme(color_name)
        if self._app:
            self._app.refresh_all_canvases()

    def _on_scale_change(self, val):
        self._scale_pct.set_text(f"{val:.1f}x")
        ThemeColors.set_font_scale(float(val))
        if self._app:
            # 防抖 100ms，避免拖拽时频繁全量渲染导致卡死
            if hasattr(self, '_scale_debounce_id') and self._scale_debounce_id:
                self.after_cancel(self._scale_debounce_id)
            self._scale_debounce_id = self.after(100, self._app.refresh_all_canvases)

    def _on_opacity_change(self, val):
        self._opacity_pct.set_text(f"{int(val * 100)}%")
        self._config["appearance"]["background_opacity"] = float(val)
        if self._app:
            self._app._apply_background()

    def _on_fit_change(self, mode):
        self._config["appearance"]["background_fit_mode"] = mode
        BackgroundManager.set_fit_mode(mode)

    def _on_refresh_change(self, val):
        self._refresh_pct.set_text(f"{int(val)}秒")

    def _choose_bg(self):
        path = filedialog.askopenfilename(
            title="选择背景图片",
            filetypes=[("图片文件", "*.jpg *.jpeg *.png *.bmp *.gif"),
                       ("所有文件", "*.*")])
        if path:
            self._config["appearance"]["background_path"] = path
            self._bg_label.set_text(f"当前: {os.path.basename(path)}")
            if self._app:
                self._app._apply_background()

    def _clear_bg(self):
        self._config["appearance"]["background_path"] = ""
        self._bg_label.set_text("当前: 未设置")
        BackgroundManager.clear()

    def _save_all(self):
        from .config import save_config

        self._config["appearance"].update({
            "theme": self._theme_var.get(),
            "color_theme": self._color_var.get(),
            "font_scale": float(self._scale_var.get()),
            "background_opacity": float(self._opacity_var.get()),
            "background_fit_mode": self._fit_var.get(),
        })
        self._config["behavior"].update({
            "auto_connect": bool(self._auto_var.get()),
            "refresh_interval": int(self._refresh_var.get()),
            "confirm_before_delete": bool(self._confirm_var.get()),
        })

        try:
            save_config(self._config)
            messagebox.showinfo("保存成功", "所有设置已保存")
        except Exception as e:
            messagebox.showerror("保存失败", str(e))

    def refresh_theme(self):
        """主题切换时重绘所有组件。"""
        self._canvas.apply_theme()
        self._canvas.set_bg_color(ThemeColors.get("bg"))
        self._canvas.render()
