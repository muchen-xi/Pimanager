"""
PillowOptionMenu — 下拉选择框（Pillow 显示 + tk.Menu 弹窗）
"""
import tkinter as tk
from PIL import Image, ImageDraw

from .canvas_renderer import BaseComponent
from .renderer import hex_to_rgba, hex_to_rgb, get_font, create_layer


class PillowOptionMenu(BaseComponent):
    """下拉选择框 — Pillow 绘制外观，tk.Menu 做弹窗。"""

    def __init__(self, x: int = 0, y: int = 0,
                 w: int = 120, h: int = 30,
                 values: list = None, variable=None, command=None):
        super().__init__(x, y, w, h)
        self.values = values or []
        self._variable = variable  # tk.StringVar
        self.command = command

    def draw(self, cw: int, ch: int) -> Image.Image:
        layer = create_layer(cw, ch)
        draw = ImageDraw.Draw(layer)
        x1, y1, x2, y2 = self.rect

        # 背景
        draw.rounded_rectangle(
            [(x1, y1), (x2, y2)], radius=6,
            fill=hex_to_rgba("#1A1A1A"),
            outline=hex_to_rgba("#555555"), width=1
        )

        # 当前值
        current = self._variable.get() if self._variable else ""
        font = get_font("msyh", 12)
        draw.text((x1 + 10, y1 + (y2 - y1 - 14) // 2),
                  current, fill=hex_to_rgb("#C9D1D9"), font=font)

        # 下拉箭头 ▼
        arrow = "▼"
        ab = draw.textbbox((0, 0), arrow, font=font)
        aw = ab[2] - ab[0]
        draw.text((x2 - aw - 10, y1 + (y2 - y1 - 14) // 2),
                  arrow, fill=hex_to_rgb("#8B949E"), font=font)

        return layer

    def on_click(self, event):
        """弹出 tk.Menu 让用户选择。"""
        if not self._parent:
            return
        menu = tk.Menu(self._parent, tearoff=0,
                       bg=ThemeColors_hex("bg_card"),
                       fg=ThemeColors_hex("text"))
        for v in self.values:
            menu.add_command(
                label=v, command=lambda val=v: self._select(val))
        # 在组件下方弹出
        x = self._parent.winfo_rootx() + self.x
        y = self._parent.winfo_rooty() + self.y + self.h
        menu.post(x, y)

    def _select(self, value: str):
        if self._variable:
            self._variable.set(value)
        if self._parent:
            self._parent.mark_dirty()
        if self.command:
            self.command(value)


def ThemeColors_hex(key: str) -> str:
    """获取 ThemeColors 颜色（hex 格式），供 tk.Menu 使用。"""
    try:
        from pimanager.theme import ThemeColors
        return ThemeColors.get(key)
    except ImportError:
        pass
    # 回退：硬编码常见键
    defaults = {"bg_card": "#161B22", "text": "#C9D1D9",
                "bg": "#0D1117", "accent": "#4CAF50"}
    return defaults.get(key, "#000000")
