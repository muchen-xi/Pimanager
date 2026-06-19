"""
PillowProgressBar — 水平进度条组件
"""
from PIL import Image, ImageDraw

from .canvas_renderer import BaseComponent
from .renderer import hex_to_rgba, create_layer


# 进度条轨道颜色 — 模块级，apply_theme() 时更新
_TRACK_COLOR = '#1A1A1A'


class PillowProgressBar(BaseComponent):
    """水平进度条，带渐变填充效果。"""

    def __init__(self, x=0, y=0, w=200, h=12,
                 value=0.0, color='#4CAF50'):
        super().__init__(x, y, w, h)
        self._value = value
        self.color = color

    def draw(self, cw, ch, font_scale=1.0):
        layer = create_layer(cw, ch)
        draw = ImageDraw.Draw(layer)
        x1, y1, x2, y2 = self.rect
        value = max(0.0, min(1.0, self._value))

        # 背景轨道
        track_fill = hex_to_rgba(_TRACK_COLOR)
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

    def apply_theme(self, theme_colors):
        """
        从 ThemeColors 更新进度条轨道颜色
        :param theme_colors: ThemeColors 类
        """
        global _TRACK_COLOR
        _TRACK_COLOR = theme_colors.get('bg_card')

    def set(self, value):
        """
        设置进度值
        :param value: 0.0 ~ 1.0
        """
        self._value = max(0.0, min(1.0, value))
        if self._parent:
            self._parent.mark_dirty()

    def set_color(self, color):
        """
        设置填充颜色
        :param color: hex 颜色字符串
        """
        self.color = color
        if self._parent:
            self._parent.mark_dirty()

    @property
    def value(self):
        return self._value
