"""
背景图片适配工具 — contain/cover/fill/tile 四种模式
"""
from PIL import Image


def fit_image(image, target_w, target_h, mode="fill", bg_color=(0, 0, 0, 0)):
    """
    将图片适配到目标尺寸
    :param image: PIL Image
    :param target_w: 目标宽度
    :param target_h: 目标高度
    :param mode: "fill" 拉伸填充 / "contain" 完整显示留白 / "cover" 填满裁剪 / "tile" 平铺
    :param bg_color: contain/tile 模式下的背景色 RGBA
    :return: 适配后的 PIL Image (target_w × target_h)
    """
    if mode == "fill":
        return image.resize((target_w, target_h), Image.LANCZOS)

    iw, ih = image.size
    tw, th = target_w, target_h

    if mode == "contain":
        scale = min(tw / iw, th / ih)
        new_w = int(iw * scale)
        new_h = int(ih * scale)
        resized = image.resize((new_w, new_h), Image.LANCZOS)
        canvas = Image.new("RGBA", (tw, th), bg_color)
        offset_x = (tw - new_w) // 2
        offset_y = (th - new_h) // 2
        canvas.paste(resized, (offset_x, offset_y))
        return canvas

    if mode == "cover":
        scale = max(tw / iw, th / ih)
        new_w = int(iw * scale)
        new_h = int(ih * scale)
        resized = image.resize((new_w, new_h), Image.LANCZOS)
        left = (new_w - tw) // 2
        top = (new_h - th) // 2
        return resized.crop((left, top, left + tw, top + th))

    if mode == "tile":
        canvas = Image.new("RGBA", (tw, th), bg_color)
        for x in range(0, tw, iw):
            for y in range(0, th, ih):
                canvas.paste(image, (x, y))
        return canvas

    return image.resize((target_w, target_h), Image.LANCZOS)
