"""
pillui 核心渲染工具 — 颜色转换 / 字体 / 图层管理
"""
import os
from PIL import Image, ImageFont, ImageDraw


# 字体缓存
_font_cache = {}


def hex_to_rgba(hex_color, alpha=255):
    """
    #1A2B3C 转 (26, 43, 60, 255) RGBA 元组
    :param hex_color: 十六进制颜色字符串
    :param alpha: alpha 通道值 0-255
    :return: (R, G, B, A) 元组
    """
    h = hex_color.lstrip('#')
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), alpha)


def hex_to_rgb(hex_color):
    """
    #1A2B3C 转 (26, 43, 60) RGB 元组
    :param hex_color: 十六进制颜色字符串
    :return: (R, G, B) 元组
    """
    h = hex_color.lstrip('#')
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def get_font(family='msyh', size=12):
    """
    加载字体，带缓存和多平台路径回退
    :param family: 字体名称（不含扩展名）
    :param size: 字号
    :return: PIL ImageFont 对象
    """
    cache_key = (family, size)
    if cache_key in _font_cache:
        return _font_cache[cache_key]

    # 中文字体搜索路径
    search_paths = [
        'C:/Windows/Fonts',
        'C:/Windows/Fonts',
        '/usr/share/fonts/truetype/noto',
        '/usr/share/fonts/truetype/dejavu',
    ]

    # 构建文件名列表：优先 TTC，然后 TTF
    filenames = ['%s.ttc' % family, '%s.ttf' % family]

    # BUG 9 fix: 粗体字体回退到基础 TTC 的 index=1
    if family.endswith('bd') or family.endswith('bold'):
        base_family = family.replace('bd', '').replace('bold', '')
        filenames = ['%s.ttc' % base_family, '%s.ttf' % base_family,
                     '%s.ttc' % family, '%s.ttf' % family]

    for search_dir in search_paths:
        for fname in filenames:
            path = os.path.join(search_dir, fname)
            if os.path.exists(path):
                try:
                    if family.endswith('bd') or family.endswith('bold'):
                        if fname.endswith('.ttc') and fname.startswith(family.replace('bd', '').replace('bold', '')):
                            font = ImageFont.truetype(path, size, index=1)
                        else:
                            font = ImageFont.truetype(path, size, index=0)
                    else:
                        font = ImageFont.truetype(path, size, index=0)
                except Exception:
                    font = ImageFont.truetype(path, size)
                _font_cache[cache_key] = font
                return font

    # Noto CJK 回退
    noto_path = '/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc'
    if os.path.exists(noto_path):
        try:
            font = ImageFont.truetype(noto_path, size, index=0)
            _font_cache[cache_key] = font
            return font
        except Exception:
            pass

    # DejaVu 回退
    dejavu_path = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    if os.path.exists(dejavu_path):
        try:
            font = ImageFont.truetype(dejavu_path, size)
            _font_cache[cache_key] = font
            return font
        except Exception:
            pass

    # 最终回退：默认字体
    font = ImageFont.load_default()
    _font_cache[cache_key] = font
    return font


def create_layer(w, h):
    """
    创建透明 RGBA 图层
    :param w: 宽度（像素）
    :param h: 高度（像素）
    :return: PIL RGBA Image
    """
    return Image.new('RGBA', (w, h), (0, 0, 0, 0))


def create_text_layer(w, h, bg_color):
    """
    创建带背景色的文本绘制层，避免 RGBA 抗锯齿暗晕 (BUG 8)
    :param w: 宽度（像素）
    :param h: 高度（像素）
    :param bg_color: hex 颜色字符串 或 'transparent' 或 RGBA 元组
    :return: PIL RGBA Image
    """
    if bg_color and bg_color != 'transparent':
        if isinstance(bg_color, str):
            return Image.new('RGBA', (w, h), hex_to_rgba(bg_color))
        else:
            return Image.new('RGBA', (w, h), bg_color)
    return Image.new('RGBA', (w, h), (0, 0, 0, 0))


def composite_layer(base, layer, x=0, y=0):
    """
    将 layer 叠加到 base 上，返回合成结果
    :param base: 底层 PIL Image
    :param layer: 要叠加的 PIL Image
    :param x: 水平偏移
    :param y: 垂直偏移
    :return: 合成后的 PIL Image
    """
    if x == 0 and y == 0 and layer.size == base.size:
        return Image.alpha_composite(base, layer)

    # 偏移合成：先创建等大透明层，粘贴 layer，再合成
    full = create_layer(*base.size)
    full.paste(layer, (x, y))
    return Image.alpha_composite(base, full)


def center_text(draw, rect, text, fill, font):
    """
    在矩形区域内居中绘制文字
    :param draw: PIL ImageDraw 对象
    :param rect: (x, y, width, height) 矩形区域
    :param text: 文字内容
    :param fill: 文字颜色 RGB 元组
    :param font: PIL ImageFont 对象
    """
    x, y, w, h = rect
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    # BUG 3 fix: 补偿字形方位偏移 (glyph bearing)
    draw_x = x + (w - tw) / 2 - bbox[0]
    draw_y = y + (h - th) / 2 - bbox[1]
    draw.text(
        (draw_x, draw_y),
        text, fill=fill, font=font
    )
