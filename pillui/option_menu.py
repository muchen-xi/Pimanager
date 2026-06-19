"""
PillowOptionMenu — 下拉选择框组件
"""
import tkinter as tk
from PIL import Image, ImageDraw

from .canvas_renderer import BaseComponent
from .renderer import hex_to_rgba, hex_to_rgb, get_font, create_layer, create_text_layer


# 选项菜单颜色 — 模块级，apply_theme() 时更新
_OPTION_BG = '#1A1A1A'
_OPTION_BORDER = '#555555'
_OPTION_FG = '#C9D1D9'
_OPTION_ARROW = '#8B949E'


class PillowOptionMenu(BaseComponent):
    """下拉选择框 — Pillow 绘制外观，tk.Menu 做弹窗。"""

    def __init__(self, x=0, y=0, w=120, h=30,
                 values=None, variable=None, command=None):
        super().__init__(x, y, w, h)
        self.values = values or []
        self._variable = variable
        self.command = command

    def draw(self, cw, ch, font_scale=1.0):
        # 使用 bg 颜色作为图层背景，使文字抗锯齿正确
        layer = create_text_layer(cw, ch, _OPTION_BG)
        draw = ImageDraw.Draw(layer)
        x1, y1, x2, y2 = self.rect

        # 背景 + 边框
        draw.rounded_rectangle(
            [(x1, y1), (x2, y2)], radius=6,
            fill=hex_to_rgba(_OPTION_BG),
            outline=hex_to_rgba(_OPTION_BORDER), width=1
        )

        # 当前选中值
        current = self._variable.get() if self._variable else ''
        font = get_font('msyh', int(12 * font_scale))
        bbox = draw.textbbox((0, 0), current, font=font)
        text_h = bbox[3] - bbox[1]
        draw.text(
            (x1 + 10, y1 + (y2 - y1 - text_h) // 2 - bbox[1]),
            current, fill=hex_to_rgb(_OPTION_FG), font=font
        )

        # 下拉箭头
        arrow = '▼'
        ab = draw.textbbox((0, 0), arrow, font=font)
        aw = ab[2] - ab[0]
        ah = ab[3] - ab[1]
        draw.text(
            (x2 - aw - 10, y1 + (y2 - y1 - ah) // 2 - ab[1]),
            arrow, fill=hex_to_rgb(_OPTION_ARROW), font=font
        )

        return layer

    def apply_theme(self, theme_colors):
        """
        从 ThemeColors 更新选项菜单颜色
        :param theme_colors: ThemeColors 类
        """
        global _OPTION_BG, _OPTION_BORDER, _OPTION_FG, _OPTION_ARROW
        _OPTION_BG = theme_colors.get('bg_card')
        _OPTION_BORDER = theme_colors.get('input_placeholder')
        _OPTION_FG = theme_colors.get('text')
        _OPTION_ARROW = theme_colors.get('text_secondary')

    def on_click(self, event):
        """弹出 tk.Menu 让用户选择。"""
        if not self._parent:
            return
        bg = self._get_theme_color('bg_card')
        fg = self._get_theme_color('text')
        menu = tk.Menu(self._parent, tearoff=0, bg=bg, fg=fg)
        for v in self.values:
            menu.add_command(
                label=v, command=lambda val=v: self._select(val))
        x = self._parent.winfo_rootx() + self.x
        y = self._parent.winfo_rooty() + self.y + self.h
        menu.post(x, y)

    def _select(self, value):
        """
        选中菜单项后的回调
        :param value: 选中的值
        """
        if self._variable:
            self._variable.set(value)
        if self._parent:
            self._parent.mark_dirty()
        if self.command:
            self.command(value)

    @staticmethod
    def _get_theme_color(key):
        """
        获取主题颜色，供 tk.Menu 使用，带 fallback
        :param key: 颜色键名
        :return: hex 颜色字符串
        """
        try:
            from pimanager.theme import ThemeColors
            return ThemeColors.get(key)
        except ImportError as e:
            print('[PillowOptionMenu] 无法导入 ThemeColors: %s' % e)
        except Exception as e:
            print('[PillowOptionMenu] ThemeColors.get 异常: %s' % e)

        # 回退：硬编码默认颜色
        defaults = {
            'bg_card': '#161B22', 'text': '#C9D1D9',
            'bg': '#0D1117', 'accent': '#4CAF50'
        }
        return defaults.get(key, '#000000')
