"""
PiManager 设置页面 - 卡片式布局，对齐 StatusPanel 视觉风格
"""
import customtkinter as ctk
import os
from tkinter import filedialog, messagebox
from PIL import Image


class SettingsPage(ctk.CTkFrame):
    """应用设置页面"""

    def __init__(self, master, config: dict, ssh_client=None, app_ref=None):
        super().__init__(master, fg_color="transparent", corner_radius=0)
        self._config = config
        self._ssh = ssh_client
        self._app = app_ref

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # 可滚动容器
        self._scroll = ctk.CTkScrollableFrame(
            self, fg_color="transparent", corner_radius=0
        )
        self._scroll.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self._scroll.grid_columnconfigure(0, weight=1)

        self._build_appearance_card()
        self._build_background_card()
        self._build_behavior_card()
        self._build_about_card()

    # ===== 外观卡片 =====

    def _build_appearance_card(self):
        card = self._make_card("🎨 外观设置")
        card.grid_columnconfigure(1, weight=1)

        row = 1  # row=0 已被标题占据

        # 主题模式
        ctk.CTkLabel(card, text="主题模式", anchor="w").grid(
            row=row, column=0, sticky="w", padx=12, pady=8
        )
        theme_var = ctk.StringVar(value=self._config["appearance"]["theme"])
        ctk.CTkOptionMenu(
            card,
            values=["dark", "light"],
            variable=theme_var,
            width=120,
            command=lambda v: self._on_theme_change(v),
        ).grid(row=row, column=1, sticky="e", padx=12, pady=8)
        row += 1

        # 颜色主题
        ctk.CTkLabel(card, text="颜色主题", anchor="w").grid(
            row=row, column=0, sticky="w", padx=12, pady=8
        )
        color_var = ctk.StringVar(value=self._config["appearance"]["color_theme"])
        ctk.CTkOptionMenu(
            card,
            values=["green", "blue", "dark-blue"],
            variable=color_var,
            width=120,
            command=lambda v: ctk.set_default_color_theme(v),
        ).grid(row=row, column=1, sticky="e", padx=12, pady=8)
        row += 1

        # 字体缩放
        ctk.CTkLabel(card, text="字体缩放", anchor="w").grid(
            row=row, column=0, sticky="w", padx=12, pady=8
        )
        scale_var = ctk.DoubleVar(value=self._config["appearance"]["font_scale"])
        scale_frame = ctk.CTkFrame(card, fg_color="transparent", corner_radius=0)
        scale_frame.grid(row=row, column=1, sticky="e", padx=12, pady=8)
        ctk.CTkSlider(
            scale_frame,
            from_=0.8,
            to=1.5,
            number_of_steps=7,
            variable=scale_var,
            width=180,
            command=lambda v: ctk.set_widget_scaling(float(v)),
        ).pack(side="left", padx=(0, 8))
        self._scale_label = ctk.CTkLabel(scale_frame, text=f"{scale_var.get():.1f}x", width=35)
        self._scale_label.pack(side="left")
        row += 1

        self._theme_var = theme_var
        self._color_var = color_var
        self._scale_var = scale_var

    # ===== 背景卡片 =====

    def _build_background_card(self):
        card = self._make_card("🖼️ 背景设置")
        card.grid_columnconfigure(1, weight=1)

        row = 1  # row=0 已被标题占据

        # 当前背景
        ctk.CTkLabel(card, text="当前背景", anchor="w").grid(
            row=row, column=0, sticky="w", padx=12, pady=8
        )
        bg_path = self._config["appearance"].get("background_path", "")
        display = os.path.basename(bg_path) if bg_path else "未设置"
        self._bg_label = ctk.CTkLabel(card, text=display, text_color="gray", anchor="e")
        self._bg_label.grid(row=row, column=1, sticky="e", padx=12, pady=8)
        row += 1

        # 选择/清除按钮
        btn_frame = ctk.CTkFrame(card, fg_color="transparent", corner_radius=0)
        btn_frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=12, pady=(0, 6))
        ctk.CTkButton(
            btn_frame,
            text="📂 选择图片",
            width=100,
            height=28,
            command=self._choose_bg,
            fg_color="#2B5B2B",
            hover_color="#3A7A3A",
        ).pack(side="left", padx=2)
        ctk.CTkButton(
            btn_frame,
            text="🗑 清除背景",
            width=100,
            height=28,
            fg_color="transparent",
            border_width=1,
            border_color=("gray40", "gray30"),
            command=self._clear_bg,
        ).pack(side="left", padx=2)
        row += 1

        # 透明度
        ctk.CTkLabel(card, text="背景透明度", anchor="w").grid(
            row=row, column=0, sticky="w", padx=12, pady=8
        )
        opacity_var = ctk.DoubleVar(value=self._config["appearance"]["background_opacity"])
        opacity_frame = ctk.CTkFrame(card, fg_color="transparent")
        opacity_frame.grid(row=row, column=1, sticky="e", padx=12, pady=8)
        ctk.CTkSlider(
            opacity_frame,
            from_=0.05,
            to=0.5,
            number_of_steps=9,
            variable=opacity_var,
            width=180,
            command=lambda v: self._on_opacity_change(float(v)),
        ).pack(side="left", padx=(0, 8))
        self._opacity_label = ctk.CTkLabel(opacity_frame, text=f"{int(opacity_var.get()*100)}%", width=35)
        self._opacity_label.pack(side="left")
        row += 1

        self._opacity_var = opacity_var

    # ===== 行为卡片 =====

    def _build_behavior_card(self):
        card = self._make_card("⚡ 行为设置")
        card.grid_columnconfigure(1, weight=1)

        row = 1  # row=0 已被标题占据

        # 自动连接
        auto_var = ctk.BooleanVar(value=self._config["behavior"]["auto_connect"])
        ctk.CTkCheckBox(
            card, text="启动时自动连接树莓派", variable=auto_var
        ).grid(row=row, column=0, columnspan=2, sticky="w", padx=12, pady=8)
        row += 1

        # 刷新间隔
        ctk.CTkLabel(card, text="状态刷新间隔", anchor="w").grid(
            row=row, column=0, sticky="w", padx=12, pady=8
        )
        refresh_var = ctk.IntVar(value=self._config["behavior"]["refresh_interval"])
        refresh_frame = ctk.CTkFrame(card, fg_color="transparent")
        refresh_frame.grid(row=row, column=1, sticky="e", padx=12, pady=8)
        ctk.CTkSlider(
            refresh_frame,
            from_=1,
            to=30,
            number_of_steps=29,
            variable=refresh_var,
            width=180,
        ).pack(side="left", padx=(0, 8))
        self._refresh_label = ctk.CTkLabel(refresh_frame, text=f"{refresh_var.get()}秒", width=35)
        self._refresh_label.pack(side="left")
        row += 1

        # 删除确认
        confirm_var = ctk.BooleanVar(value=self._config["behavior"]["confirm_before_delete"])
        ctk.CTkCheckBox(
            card, text="删除文件前弹出确认对话框", variable=confirm_var
        ).grid(row=row, column=0, columnspan=2, sticky="w", padx=12, pady=8)
        row += 1

        self._auto_var = auto_var
        self._refresh_var = refresh_var
        self._confirm_var = confirm_var

    # ===== 关于卡片 =====

    def _build_about_card(self):
        card = self._make_card("ℹ️ 关于")
        card.grid_columnconfigure(0, weight=1)

        info = (
            "PiManager v1.1.0\n"
            "轻量级树莓派 Zero W 桌面管理器\n"
            "Python + CustomTkinter + Paramiko\n"
            "支持多标签命令终端 · 密钥认证 · 自定义背景"
        )
        ctk.CTkLabel(
            card,
            text=info,
            justify="left",
            anchor="w",
            text_color="gray",
            font=ctk.CTkFont(size=11),
        ).grid(row=1, column=0, sticky="w", padx=12, pady=10)

        # 保存按钮
        ctk.CTkButton(
            card,
            text="💾 保存所有设置",
            height=34,
            fg_color="#2B5B2B",
            hover_color="#3A7A3A",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._save_all,
        ).grid(row=2, column=0, pady=(5, 12), padx=12)

    # ===== 卡片工厂 =====

    def _make_card(self, title: str) -> ctk.CTkFrame:
        """创建一致风格的卡片容器（纯 grid 布局，标题占 row=0）"""
        card = ctk.CTkFrame(self._scroll)
        card.pack(fill="x", padx=2, pady=6)

        ctk.CTkLabel(
            card,
            text=title,
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=12, pady=(10, 4))

        return card

    # ===== 事件处理 =====

    def _on_theme_change(self, theme: str):
        ctk.set_appearance_mode(theme)
        if self._app and hasattr(self._app, '_apply_background'):
            self._app.after(200, lambda: self._app._apply_background(force=True))

    def _on_opacity_change(self, val: float):
        self._config["appearance"]["background_opacity"] = float(val)
        self._opacity_label.configure(text=f"{int(val*100)}%")
        if self._app and hasattr(self._app, '_apply_background'):
            self._app._apply_background(force=True)

    def _choose_bg(self):
        path = filedialog.askopenfilename(
            title="选择背景图片",
            filetypes=[("图片文件", "*.jpg *.jpeg *.png *.bmp *.gif"), ("所有文件", "*.*")],
        )
        if path:
            self._config["appearance"]["background_path"] = path
            self._bg_label.configure(text=os.path.basename(path))
            if self._app and hasattr(self._app, '_apply_background'):
                self._app._apply_background(force=True)

    def _clear_bg(self):
        self._config["appearance"]["background_path"] = ""
        self._bg_label.configure(text="未设置")
        if self._app and hasattr(self._app, 'BackgroundManager'):
            from .app import BackgroundManager
            BackgroundManager.clear()

    def _save_all(self):
        """保存所有设置"""
        from .config import save_config

        self._config["appearance"].update(
            {
                "theme": self._theme_var.get(),
                "color_theme": self._color_var.get(),
                "font_scale": float(self._scale_var.get()),
                "background_opacity": float(self._opacity_var.get()),
            }
        )
        self._config["behavior"].update(
            {
                "auto_connect": bool(self._auto_var.get()),
                "refresh_interval": int(self._refresh_var.get()),
                "confirm_before_delete": bool(self._confirm_var.get()),
            }
        )

        try:
            save_config(self._config)
            messagebox.showinfo("保存成功", "所有设置已保存 ✓")
        except Exception as e:
            messagebox.showerror("保存失败", str(e))

    def update_labels(self):
        """更新滑块对应的标签文本"""
        self._scale_label.configure(text=f"{self._scale_var.get():.1f}x")
        self._opacity_label.configure(text=f"{int(self._opacity_var.get()*100)}%")
        self._refresh_label.configure(text=f"{self._refresh_var.get()}秒")
