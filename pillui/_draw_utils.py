"""
共享绘图工具 — 圆角矩形 / 文字对齐 / 文字测量
"""
from PIL import ImageDraw, ImageFont


def draw_rounded_rect(draw: ImageDraw.Draw,
                      x1: int, y1: int, x2: int, y2: int,
                      radius: int,
                      fill: tuple = None,
                      outline: tuple = None,
                      width: int = 1):
    """在 ImageDraw 上绘制圆角矩形。"""
    draw.rounded_rectangle(
        [(x1, y1), (x2, y2)],
        radius=radius, fill=fill, outline=outline, width=width
    )


def text_bbox(text: str, font: ImageFont.FreeTypeFont) -> tuple:
    """获取文字包围盒 (width, height)。"""
    # 用一个临时 draw 来测量
    from PIL import Image
    dummy = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    d = ImageDraw.Draw(dummy)
    bb = d.textbbox((0, 0), text, font=font)
    return (bb[2] - bb[0], bb[3] - bb[1])


def draw_text_aligned(draw: ImageDraw.Draw,
                      rect: tuple,  # (x, y, w, h)
                      text: str,
                      fill: tuple,
                      font: ImageFont.FreeTypeFont,
                      align: str = "center"):
    """在矩形内绘制文字，支持 left / center / right 水平对齐，垂直居中。

    rect: (x, y, width, height)
    align: "left" | "center" | "right"
    """
    x, y, w, h = rect
    tw, th = text_bbox(text, font)

    if align == "left":
        tx = x + 4
    elif align == "right":
        tx = x + w - tw - 4
    else:  # center
        tx = x + (w - tw) / 2

    ty = y + (h - th) / 2
    draw.text((tx, ty), text, fill=fill, font=font)
