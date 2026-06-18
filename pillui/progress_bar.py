"""
PillowProgressBar — 水平进度条组件
"""
from PIL import Image, ImageDraw

from .canvas_renderer import BaseComponent
from .renderer import hex_to_rgba, create_layer


class PillowProgressBar(BaseComponent):
    """Gradient-like 水平进度条。"""

    def __init__(self, x: int = 0, y: int = 0,
                 w: int = 200, h: int = 12,
                 value: float = 0.0,  # 0.0 ~ 1.0
                 color: str = "#4CAF50"):
        super().__init__(x, y, w, h)
        self._value = value
        self.color = color

    def draw(self, cw: int, ch: int) -> Image.Image:
        layer = create_layer(cw, ch)
        draw = ImageDraw.Draw(layer)
        x1, y1, x2, y2 = self.rect
        value = max(0.0, min(1.0, self._value))

        # 背景轨道（深色 + 圆角）
        track_fill = hex_to_rgba("#1A1A1A")
        draw.rounded_rectangle(
            [(x1, y1), (x2, y2)], radius=4, fill=track_fill
        )

        # 填充条
        if value > 0:
            fill_w = int((x2 - x1) * value)
            if fill_w > 3:
                draw.rounded_rectangle(
                    [(x1, y1), (x1 + fill_w, y2)],
                    radius=4, fill=hex_to_rgba(self.color)
                )

        return layer

    def set(self, value: float):
        """设置进度 0.0~1.0。"""
        self._value = max(0.0, min(1.0, value))
        if self._parent:
            self._parent.mark_dirty()

    def set_color(self, color: str):
        """设置颜色。"""
        self.color = color
        if self._parent:
            self._parent.mark_dirty()

    @property
    def value(self) -> float:
        return self._value
