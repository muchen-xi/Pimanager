"""
PillowButton — 带悬停/按下效果的按钮组件
"""
from PIL import Image, ImageDraw

from .canvas_renderer import BaseComponent
from .renderer import hex_to_rgb, hex_to_rgba, get_font, create_layer


class PillowButton(BaseComponent):
    """纯 Pillow 绘制的按钮，支持 hover/pressed 状态。"""

    STYLES = {
        "primary": {
            "bg": "#2B5B2B", "hover": "#3A7A3A",
            "text": "#FFFFFF", "border": None
        },
        "danger": {
            "bg": "#8B0000", "hover": "#A00000",
            "text": "#FFFFFF", "border": None
        },
        "transparent": {
            "bg": "transparent", "hover": "#333333",
            "text": "#C9D1D9", "border": ("gray40", "gray30")
        },
    }

    def __init__(self, text: str = "", x: int = 0, y: int = 0,
                 w: int = 100, h: int = 36,
                 command=None,
                 style: str = "primary",
                 font_size: int = 13,
                 disabled: bool = False):
        super().__init__(x, y, w, h)
        self.text = text
        self.command = command
        self.style = style
        self.font_size = font_size
        self._disabled = disabled
        self._hovered = False
        self._pressed = False

    def draw(self, cw: int, ch: int) -> Image.Image:
        layer = create_layer(cw, ch)
        draw = ImageDraw.Draw(layer)

        s = self.STYLES.get(self.style, self.STYLES["primary"])
        x1, y1, x2, y2 = self.rect

        # 填充色
        if self._disabled:
            fill = hex_to_rgba("#555555")
        elif self._pressed:
            fill = hex_to_rgba(s["hover"])
        elif self._hovered:
            fill = hex_to_rgba(s["hover"])
        elif s["bg"] == "transparent":
            fill = (0, 0, 0, 0)  # 完全透明
        else:
            fill = hex_to_rgba(s["bg"])

        # 圆角矩形
        if fill != (0, 0, 0, 0):
            draw.rounded_rectangle(
                [(x1, y1), (x2, y2)],
                radius=8, fill=fill
            )

        # 边框
        if s.get("border"):
            draw.rounded_rectangle(
                [(x1, y1), (x2, y2)],
                radius=8,
                outline=hex_to_rgba("#555555"),
                width=1
            )

        # 文字（居中）
        text_rgb = hex_to_rgb("#888888" if self._disabled else s["text"])
        font = get_font("msyh", self.font_size)
        bbox = draw.textbbox((0, 0), self.text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text(
            (x1 + (x2 - x1 - tw) / 2, y1 + (y2 - y1 - th) / 2),
            self.text, fill=text_rgb, font=font
        )

        return layer

    # ---- 交互 ----

    def on_click(self, event):
        if self._disabled:
            return
        self._pressed = True
        if self._parent:
            self._parent.mark_dirty()

    def on_release(self, event):
        if self._disabled:
            return
        self._pressed = False
        if self._parent:
            self._parent.mark_dirty()
        if self.command:
            self.command()

    def on_enter(self):
        self._hovered = True

    def on_leave(self):
        self._hovered = False
        self._pressed = False

    # ---- 状态 ----

    def set_disabled(self, disabled: bool):
        self._disabled = disabled
        if self._parent:
            self._parent.mark_dirty()

    def set_text(self, text: str):
        self.text = text
        if self._parent:
            self._parent.mark_dirty()

    def set_style(self, style: str):
        self.style = style
        if self._parent:
            self._parent.mark_dirty()
