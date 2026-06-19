"""
共享绘图工具 — 圆角矩形 / 文字对齐 / 文字测量
"""
from PIL import Image, ImageDraw, ImageFont


def draw_rounded_rect(draw, x1, y1, x2, y2, radius, fill=None, outline=None, width=1):
    """
    在 ImageDraw 上绘制圆角矩形
    :param draw: PIL ImageDraw 对象
    :param x1: 左上角 x
    :param y1: 左上角 y
    :param x2: 右下角 x
    :param y2: 右下角 y
    :param radius: 圆角半径
    :param fill: 填充色 RGBA 元组
    :param outline: 边框色 RGBA 元组
    :param width: 边框宽度
    """
    draw.rounded_rectangle(
        [(x1, y1), (x2, y2)],
        radius=radius, fill=fill, outline=outline, width=width
    )


def text_bbox(text, font):
    """
    获取文字包围盒 (width, height)
    :param text: 文字内容
    :param font: PIL ImageFont 对象
    :return: (width, height) 元组
    """
    dummy = Image.new('RGBA', (1, 1), (0, 0, 0, 0))
    d = ImageDraw.Draw(dummy)
    bb = d.textbbox((0, 0), text, font=font)
    return (bb[2] - bb[0], bb[3] - bb[1])


def draw_text_aligned(draw, rect, text, fill, font, align='center'):
    """
    在矩形内绘制文字，支持左/中/右水平对齐，垂直居中
    :param draw: PIL ImageDraw 对象
    :param rect: (x, y, width, height) 矩形区域
    :param text: 文字内容
    :param fill: 文字颜色 RGB 元组
    :param font: PIL ImageFont 对象
    :param align: "left" | "center" | "right"
    """
    x, y, w, h = rect
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]

    if align == 'left':
        tx = x + 4
    elif align == 'right':
        tx = x + w - tw - 4
    else:
        tx = x + (w - tw) / 2

    # BUG 3 fix: 补偿字形方位偏移
    ty = y + (h - th) / 2 - bbox[1]
    tx = tx - bbox[0]
    draw.text((tx, ty), text, fill=fill, font=font)
