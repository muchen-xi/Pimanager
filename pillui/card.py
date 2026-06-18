"""
PillowCard — 圆角卡片容器组件
"""
from PIL import Image, ImageDraw

from .canvas_renderer import BaseComponent
from .renderer import hex_to_rgba, hex_to_rgb, get_font, create_layer


class PillowCard(BaseComponent):
    """圆角矩形卡片容器 — 带有可选的标题栏和内容区。"""

    def __init__(self, x: int = 0, y: int = 0,
                 w: int = 200, h: int = 100,
                 title: str = "",
                 fill: str = "#161B22",
                 border: str = "gray35",
                 radius: int = 10,
                 title_size: int = 13):
        super().__init__(x, y, w, h)
        self.title = title
        self.fill_color = fill
        self.border_color = border
        self.radius = radius
        self.title_size = title_size

    def draw(self, cw: int, ch: int) -> Image.Image:
        layer = create_layer(cw, ch)
        draw = ImageDraw.Draw(layer)
        x1, y1, x2, y2 = self.rect

        # 背景
        fill = hex_to_rgba(self.fill_color)
        outline = hex_to_rgba(self.border_color)
        draw.rounded_rectangle(
            [(x1, y1), (x2, y2)],
            radius=self.radius, fill=fill, outline=outline, width=1
        )

        # 标题
        if self.title:
            font = get_font("msyhbd", self.title_size)
            rgb = hex_to_rgb("#C9D1D9")
            draw.text(
                (x1 + 12, y1 + 10),
                self.title, fill=rgb, font=font
            )

        return layer
