"""
PillowCard — 圆角卡片容器组件
"""
from PIL import Image, ImageDraw

from .canvas_renderer import BaseComponent
from .renderer import hex_to_rgba, hex_to_rgb, get_font, create_layer


class PillowCard(BaseComponent):
    """圆角矩形卡片容器，带可选的标题栏。"""

    def __init__(self, x=0, y=0, w=200, h=100,
                 title='', fill='#161B22',
                 border='#4D4D4D', radius=10, title_size=13):
        super().__init__(x, y, w, h)
        self.title = title
        self.fill_color = fill
        self.border_color = border
        self.radius = radius
        self.title_size = title_size

    def draw(self, cw, ch, font_scale=1.0):
        # 透明图层：仅卡片的 rect 区域不透明，不再覆盖整幅画布
        layer = create_layer(cw, ch)
        draw = ImageDraw.Draw(layer)
        x1, y1, x2, y2 = self.rect

        # 背景 + 边框
        fill = hex_to_rgba(self.fill_color)
        outline = hex_to_rgba(self.border_color)
        draw.rounded_rectangle(
            [(x1, y1), (x2, y2)],
            radius=self.radius, fill=fill, outline=outline, width=1
        )

        # 标题文字 (应用字体缩放)
        if self.title:
            title_fs = int(self.title_size * font_scale)
            font = get_font('msyhbd', title_fs)
            rgb = hex_to_rgb('#C9D1D9')
            draw.text(
                (x1 + 12, y1 + 10),
                self.title, fill=rgb, font=font
            )

        return layer

    def apply_theme(self, theme_colors):
        """
        从 ThemeColors 更新卡片填充色和边框色
        :param theme_colors: ThemeColors 类
        """
        self.fill_color = theme_colors.get('bg_card')
        border_val = theme_colors.get('card_border')
        if isinstance(border_val, tuple):
            self.border_color = border_val[0]
        else:
            self.border_color = border_val
