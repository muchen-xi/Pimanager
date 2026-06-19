"""
PillowCheckBox — 复选框组件
"""
import math
from PIL import Image, ImageDraw

from .canvas_renderer import BaseComponent
from .renderer import hex_to_rgba, hex_to_rgb, get_font, create_layer, create_text_layer


# 复选框常量
_BOX_SIZE = 16
_CHECK_COLOR = '#4CAF50'


class PillowCheckBox(BaseComponent):
    """复选框 — 小方块 + 勾号 + 标签文字。"""

    def __init__(self, text='', x=0, y=0, w=200, h=24,
                 variable=None, command=None):
        super().__init__(x, y, w, h)
        self.text = text
        self._variable = variable
        self.command = command

    def draw(self, cw, ch, font_scale=1.0):
        layer = create_layer(cw, ch)
        draw = ImageDraw.Draw(layer)
        x1, y1, x2, y2 = self.rect

        box_y = y1 + (y2 - y1 - _BOX_SIZE) // 2

        checked = self._variable.get() if self._variable else False

        # 复选框背景
        if checked:
            fill = hex_to_rgba(_CHECK_COLOR)
        else:
            fill = hex_to_rgba('#1A1A1A')
        draw.rounded_rectangle(
            [(x1, box_y), (x1 + _BOX_SIZE, box_y + _BOX_SIZE)],
            radius=3, fill=fill,
            outline=hex_to_rgba('#555555'), width=1
        )

        # 勾号（用两条短线组合）
        if checked:
            cx = x1 + _BOX_SIZE // 2
            cy = box_y + _BOX_SIZE // 2
            lx = cx - 5
            ly = cy
            mx = cx - 1
            my = cy + 4
            rx = cx + 6
            ry = cy - 4
            pts = [(lx, ly), (mx, my), (rx, ry)]
            for i in range(len(pts) - 1):
                draw.line([pts[i], pts[i + 1]],
                          fill=hex_to_rgba('#FFFFFF'), width=2)

        # 标签文字
        if self.text:
            # 获取页面背景色
            page_bg = '#0D1117'
            if self._parent and hasattr(self._parent, '_bg_color'):
                page_bg = self._parent._bg_color

            font = get_font('msyh', int(12 * font_scale))
            bbox = draw.textbbox((0, 0), self.text, font=font)
            text_h = bbox[3] - bbox[1]
            # 用实测高度计算垂直居中 + 补偿字形偏移
            text_x = x1 + _BOX_SIZE + 8
            text_y = y1 + (y2 - y1 - text_h) // 2 - bbox[1]

            # 在页面背景色上绘制标签文字
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            text_layer = create_text_layer(tw + 4, th + 4, page_bg)
            text_draw = ImageDraw.Draw(text_layer)
            text_draw.text((2 - bbox[0], 2 - bbox[1]), self.text,
                          fill=hex_to_rgb('#C9D1D9'), font=font)
            layer.paste(text_layer, (int(text_x - 2), int(text_y - 2)), text_layer)

        return layer

    def apply_theme(self, theme_colors):
        """
        从 ThemeColors 更新复选框颜色
        :param theme_colors: ThemeColors 类
        """
        global _CHECK_COLOR
        _CHECK_COLOR = theme_colors.get('accent')

    def hit_test(self, mx, my):
        x1, y1, x2, _ = self.rect
        return x1 <= mx <= x2 and y1 <= my <= y1 + 22

    def on_click(self, event):
        if self._variable:
            self._variable.set(not self._variable.get())
        if self._parent:
            self._parent.mark_dirty()
        if self.command:
            self.command()

    def on_release(self, event):
        pass
