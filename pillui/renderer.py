"""
pillui 核心渲染工具 — 颜色转换 / 字体 / 图层管理
"""
from PIL import Image, ImageFont, ImageDraw
import os

# ============================================================
#  颜色转换
# ============================================================

def hex_to_rgba(hex_color: str, alpha: int = 255) -> tuple:
    """#1A2B3C → (26, 43, 60, 255)"""
    h = hex_color.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), alpha)


def hex_to_rgb(hex_color: str) -> tuple:
    """#1A2B3C → (26, 43, 60)"""
    h = hex_color.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


# ============================================================
#  字体加载
# ============================================================

# 字体缓存
_font_cache: dict = {}


def get_font(family: str = "msyh", size: int = 12) -> ImageFont.FreeTypeFont:
    """加载字体，带缓存和多平台路径回退。

    优先加载指定的 family，找不到时回退到系统默认。
    """
    cache_key = (family, size)
    if cache_key in _font_cache:
        return _font_cache[cache_key]

    # 中文字体搜索路径
    search_paths = [
        f"C:/Windows/Fonts/{family}.ttc",
        f"C:/Windows/Fonts/{family}.ttf",
        f"/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        f"/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]

    for path in search_paths:
        if os.path.exists(path):
            font = ImageFont.truetype(path, size)
            _font_cache[cache_key] = font
            return font

    # 最终回退
    font = ImageFont.load_default()
    _font_cache[cache_key] = font
    return font


# ============================================================
#  图层管理
# ============================================================

def create_layer(w: int, h: int) -> Image.Image:
    """创建透明 RGBA 图层。"""
    return Image.new("RGBA", (w, h), (0, 0, 0, 0))


def composite_layer(base: Image.Image, layer: Image.Image,
                    x: int = 0, y: int = 0) -> Image.Image:
    """将 layer 叠加到 base 上（base 会被修改并返回）。

    如果 layer 位置有偏移，先将其粘贴到等大透明层上再合成。
    """
    if x == 0 and y == 0 and layer.size == base.size:
        return Image.alpha_composite(base, layer)

    # 偏移合成：先创建等大透明层，粘贴 layer，再合成
    full = create_layer(*base.size)
    full.paste(layer, (x, y))
    return Image.alpha_composite(base, full)


def center_text(draw: ImageDraw.Draw, rect: tuple, text: str,
                fill: tuple, font: ImageFont.FreeTypeFont) -> None:
    """在矩形区域内居中绘制文字。

    rect: (x, y, width, height)
    """
    x, y, w, h = rect
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text((x + (w - tw) / 2, y + (h - th) / 2),
              text, fill=fill, font=font)
