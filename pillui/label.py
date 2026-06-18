"""
PillowLabel — 纯文本标签组件
"""
from PIL import Image, ImageDraw

from .canvas_renderer import BaseComponent
from .renderer import hex_to_rgb, hex_to_rgba, get_font, create_layer


class PillowLabel(BaseComponent):
    """纯文本标签，支持左/中/右对齐和多行。"""

    def __init__(self, text: str = "", x: int = 0, y: int = 0,
                 w: int = 100, h: int = 20,
                 font_size: int = 12,
                 color: str = "#C9D1D9",
                 align: str = "left",
                 weight: str = "normal",
                 anchor: str = "nw"):
        """
        align: "left" | "center" | "right"
        weight: "normal" | "bold"
        anchor: "nw" (默认左上角) | "center"
        """
        w = max(w, 1)
        h = max(h, 1)
        super().__init__(x, y, w, h)
        self.text = text
        self.font_size = font_size
        self.color = color
        self.align = align
        self.weight = weight
        self.anchor = anchor

    def draw(self, cw: int, ch: int) -> Image.Image:
        layer = create_layer(cw, ch)
        draw = ImageDraw.Draw(layer)
        rgb = hex_to_rgb(self.color)

        family = "msyh"
        if self.weight == "bold":
            family = "msyhbd"

        font = get_font(family, self.font_size)

        # 多行处理
        lines = self.text.split("\n")
        line_height = self.font_size + 6

        x, y = self.x, self.y
        if self.anchor == "center":
            # 居中锚点：向左上偏移半宽半高
            total_h = len(lines) * line_height
            x = self.x - self.w // 2
            y = self.y - total_h // 2

        for i, line in enumerate(lines):
            ly = y + i * line_height
            if self.align == "center":
                lx = x + self.w // 2
                draw.text((lx, ly), line, fill=rgb, font=font, anchor="ma")
            elif self.align == "right":
                lx = x + self.w - 4
                draw.text((lx, ly), line, fill=rgb, font=font, anchor="ra")
            else:
                draw.text((x + 4, ly), line, fill=rgb, font=font)

        return layer

    def set_text(self, text: str):
        """更新文字。"""
        if self.text != text:
            self.text = text
            if self._parent:
                self._parent.mark_dirty()

    def set_color(self, color: str):
        """更新颜色。"""
        self.color = color
        if self._parent:
            self._parent.mark_dirty()
