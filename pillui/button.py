"""
PillowButton — 带悬停/按下效果的按钮组件
"""
from PIL import Image, ImageDraw

from .canvas_renderer import BaseComponent
from .renderer import hex_to_rgb, hex_to_rgba, get_font, create_layer, create_text_layer


# 按钮预设样式 — 初始使用深色默认值，apply_theme() 时动态更新
_BUTTON_STYLES = {
    'primary': {
        'bg': '#2B5B2B', 'hover': '#3A7A3A',
        'text': '#FFFFFF', 'border': None
    },
    'danger': {
        'bg': '#8B0000', 'hover': '#A00000',
        'text': '#FFFFFF', 'border': None
    },
    'transparent': {
        'bg': 'transparent', 'hover': '#333333',
        'text': '#C9D1D9', 'border': ('#555555', '#444444')
    },
}


class PillowButton(BaseComponent):
    """纯 Pillow 绘制的按钮，支持 hover/pressed 状态。"""

    def __init__(self, text='', x=0, y=0, w=100, h=36,
                 command=None, style='primary', font_size=13,
                 disabled=False):
        super().__init__(x, y, w, h)
        self.text = text
        self.command = command
        self.style = style
        self.font_size = font_size
        self._disabled = disabled
        self._hovered = False
        self._pressed = False

    def draw(self, cw, ch, font_scale=1.0):
        layer = create_layer(cw, ch)
        draw = ImageDraw.Draw(layer)

        s = _BUTTON_STYLES.get(self.style, _BUTTON_STYLES['primary'])
        x1, y1, x2, y2 = self.rect

        # 填充色：禁用 > 按下 > 悬停 > 正常
        if self._disabled:
            fill = hex_to_rgba('#555555')
        elif self._pressed:
            fill = hex_to_rgba(s['hover'])
        elif self._hovered:
            fill = hex_to_rgba(s['hover'])
        elif s['bg'] == 'transparent':
            fill = (0, 0, 0, 0)
        else:
            fill = hex_to_rgba(s['bg'])

        # 圆角矩形背景
        if fill != (0, 0, 0, 0):
            draw.rounded_rectangle(
                [(x1, y1), (x2, y2)],
                radius=8, fill=fill
            )

        # 边框
        border_val = s.get('border')
        if border_val:
            if isinstance(border_val, tuple):
                border_color = border_val[0]
            else:
                border_color = border_val
            draw.rounded_rectangle(
                [(x1, y1), (x2, y2)],
                radius=8,
                outline=hex_to_rgba(border_color),
                width=1
            )

        # 文字居中 (BUG 3 fix: 补偿字形方位偏移)
        text_rgb = hex_to_rgb('#888888' if self._disabled else s['text'])
        fs = int(self.font_size * font_scale)
        font = get_font('msyh', fs)
        bbox = draw.textbbox((0, 0), self.text, font=font)
        draw_x = x1 + (x2 - x1 - (bbox[2] - bbox[0])) / 2 - bbox[0]
        draw_y = y1 + (y2 - y1 - (bbox[3] - bbox[1])) / 2 - bbox[1]

        # BUG 8 fix: 透明按钮文字在页面背景色上绘制，避免 RGBA 抗锯齿暗晕
        if fill == (0, 0, 0, 0):
            page_bg = '#0D1117'
            if self._parent and hasattr(self._parent, '_bg_color'):
                page_bg = self._parent._bg_color
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            text_layer = create_text_layer(tw + 4, th + 4, page_bg)
            text_draw = ImageDraw.Draw(text_layer)
            text_draw.text((2 - bbox[0], 2 - bbox[1]), self.text, fill=text_rgb, font=font)
            layer.paste(text_layer, (int(draw_x - 2), int(draw_y - 2)), text_layer)
        else:
            draw.text(
                (draw_x, draw_y),
                self.text, fill=text_rgb, font=font
            )

        return layer

    def apply_theme(self, theme_colors):
        """
        从 ThemeColors 更新 _BUTTON_STYLES 模块级颜色
        :param theme_colors: ThemeColors 类
        """
        _BUTTON_STYLES['primary'] = {
            'bg': theme_colors.get('btn_primary'),
            'hover': theme_colors.get('btn_primary_hover'),
            'text': '#FFFFFF', 'border': None
        }
        _BUTTON_STYLES['danger'] = {
            'bg': theme_colors.get('danger'),
            'hover': theme_colors.get('danger_hover'),
            'text': '#FFFFFF', 'border': None
        }
        border_val = theme_colors.get('card_border')
        if isinstance(border_val, tuple):
            border_hex = border_val[0]
        else:
            border_hex = border_val
        _BUTTON_STYLES['transparent'] = {
            'bg': 'transparent',
            'hover': theme_colors.get('btn_transparent_hover'),
            'text': theme_colors.get('text'),
            'border': (border_hex, border_hex)
        }

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

    def set_disabled(self, disabled):
        """
        设置禁用状态
        :param disabled: bool
        """
        self._disabled = disabled
        if self._parent:
            self._parent.mark_dirty()

    def set_text(self, text):
        """
        更新按钮文字
        :param text: 新文字
        """
        self.text = text
        if self._parent:
            self._parent.mark_dirty()

    def set_style(self, style):
        """
        切换按钮样式
        :param style: 样式名 ("primary" | "danger" | "transparent")
        """
        self.style = style
        if self._parent:
            self._parent.mark_dirty()
