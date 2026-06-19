"""
PillowLabel — 纯文本标签组件
"""
from PIL import Image, ImageDraw

from .canvas_renderer import BaseComponent
from .renderer import hex_to_rgb, get_font, create_layer, create_text_layer


class PillowLabel(BaseComponent):
    """纯文本标签，支持左/中/右对齐和多行。"""

    def __init__(self, text='', x=0, y=0, w=100, h=20,
                 font_size=12, color='#C9D1D9',
                 align='left', weight='normal', anchor='nw'):
        """
        :param text: 文字内容
        :param x: 水平位置
        :param y: 垂直位置
        :param w: 宽度
        :param h: 高度
        :param font_size: 字号
        :param color: hex 颜色
        :param align: "left" | "center" | "right"
        :param weight: "normal" | "bold"
        :param anchor: "nw" (左上角) | "center"
        """
        w = max(w, 1)
        h = max(h, 1)
        super().__init__(x, y, w, h)
        self.text = text
        self.font_size = font_size
        self.color = color
        self.align = align
        self.weight = weight
        self.anchor = anchor

    def draw(self, cw, ch, font_scale=1.0):
        # 获取页面背景色用于文本抗锯齿
        page_bg = '#0D1117'
        if self._parent and hasattr(self._parent, '_bg_color'):
            page_bg = self._parent._bg_color

        layer = create_layer(cw, ch)
        rgb = hex_to_rgb(self.color)

        family = 'msyh'
        if self.weight == 'bold':
            family = 'msyhbd'

        # 应用字体缩放
        font_size = int(self.font_size * font_scale)
        font = get_font(family, font_size)

        # 多行处理
        lines = self.text.split('\n')
        line_height = font_size + 6

        x, y = self.x, self.y
        if self.anchor == 'center':
            total_h = len(lines) * line_height
            x = self.x - self.w // 2
            y = self.y - total_h // 2

        # 临时 draw 用于测量文字
        measure_img = Image.new('RGBA', (1, 1), (0, 0, 0, 0))
        measure_draw = ImageDraw.Draw(measure_img)

        for i, line in enumerate(lines):
            ly = y + i * line_height

            # 在页面背景色上绘制文字，避免 RGBA 抗锯齿暗晕
            # 测量文字包围盒
            tb = measure_draw.textbbox((0, 0), line, font=font)
            tw = tb[2] - tb[0]
            th = tb[3] - tb[1]

            # 在小尺寸不透光层上绘制文字（匹配页面背景色）
            text_layer = create_text_layer(tw + 8, th + 8, page_bg)
            text_draw = ImageDraw.Draw(text_layer)
            # 补偿字形方位偏移
            text_draw.text((4 - tb[0], 4 - tb[1]), line, fill=rgb, font=font)

            # 计算粘贴位置
            if self.align == 'center':
                paste_x = x + (self.w - tw) // 2 - 4
            elif self.align == 'right':
                paste_x = x + self.w - tw - 8
            else:
                paste_x = x

            layer.paste(text_layer, (int(paste_x), int(ly - 4)), text_layer)

        return layer

    def apply_theme(self, theme_colors):
        """
        更新主题颜色，仅对使用默认文字色的标签生效，保留语义颜色
        :param theme_colors: ThemeColors 类
        """
        # 默认文字色集合（深色/浅色模式的 text 和 text_secondary）
        default_text_colors = {'#C9D1D9', '#24292F', '#8B949E', '#656D76', 'gray'}
        if self.color in default_text_colors:
            if self.color in ('#C9D1D9', '#24292F', 'gray'):
                self.color = theme_colors.get('text')
            elif self.color in ('#8B949E', '#656D76'):
                self.color = theme_colors.get('text_secondary')

    def set_text(self, text):
        """
        更新文字内容
        :param text: 新文字
        """
        if self.text != text:
            self.text = text
            if self._parent:
                self._parent.mark_dirty()

    def set_color(self, color):
        """
        更新文字颜色
        :param color: hex 颜色字符串
        """
        self.color = color
        if self._parent:
            self._parent.mark_dirty()
