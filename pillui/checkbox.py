"""
PillowCheckBox — 复选框组件
"""
from PIL import Image, ImageDraw

from .canvas_renderer import BaseComponent
from .renderer import hex_to_rgba, hex_to_rgb, get_font, create_layer


class PillowCheckBox(BaseComponent):
    """复选框 — 小方块 + 勾号 + 标签文字。"""

    def __init__(self, text: str = "", x: int = 0, y: int = 0,
                 w: int = 200, h: int = 24,
                 variable=None, command=None):
        super().__init__(x, y, w, h)
        self.text = text
        self._variable = variable  # tk.BooleanVar
        self.command = command

    def draw(self, cw: int, ch: int) -> Image.Image:
        layer = create_layer(cw, ch)
        draw = ImageDraw.Draw(layer)
        x1, y1, x2, y2 = self.rect

        box_size = 16
        box_y = y1 + (y2 - y1 - box_size) // 2

        checked = self._variable.get() if self._variable else False

        # 复选框背景
        if checked:
            fill = hex_to_rgba("#4CAF50")
        else:
            fill = hex_to_rgba("#1A1A1A")
        draw.rounded_rectangle(
            [(x1, box_y), (x1 + box_size, box_y + box_size)],
            radius=3, fill=fill,
            outline=hex_to_rgba("#555555"), width=1
        )

        # 勾号
        if checked:
            import math
            cx, cy = x1 + box_size // 2, box_y + box_size // 2
            # 简化勾号：用两条短线
            lx = cx - 5
            ly = cy
            mx = cx - 1
            my = cy + 4
            rx = cx + 6
            ry = cy - 4
            pts = [(lx, ly), (mx, my), (rx, ry)]
            for i in range(len(pts) - 1):
                draw.line([pts[i], pts[i + 1]],
                          fill=hex_to_rgba("#FFFFFF"), width=2)

        # 标签文字
        if self.text:
            font = get_font("msyh", 12)
            draw.text(
                (x1 + box_size + 8, y1 + (y2 - y1 - 14) // 2),
                self.text,
                fill=hex_to_rgb("#C9D1D9"), font=font
            )

        return layer

    def hit_test(self, mx: int, my: int) -> bool:
        x1, y1, x2, _ = self.rect
        # 点击区域包括文字
        return x1 <= mx <= x2 and y1 <= my <= y1 + 22

    def on_click(self, event):
        if self._variable:
            self._variable.set(not self._variable.get())
        if self._parent:
            self._parent.mark_dirty()
        if self.command:
            self.command()

    def on_release(self, event):
        pass
