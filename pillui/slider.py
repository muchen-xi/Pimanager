"""
PillowSlider — 水平滑块组件（支持拖拽）
"""
from PIL import Image, ImageDraw

from .canvas_renderer import BaseComponent
from .renderer import hex_to_rgba, create_layer


# 滑块绘制常量
_THUMB_RADIUS = 7
_TRACK_INSET = 8

# 滑块颜色 — 初始使用深色默认值，apply_theme() 时更新
_TRACK_COLOR = '#333333'
_FILL_COLOR = '#4CAF50'
_THUMB_COLOR = '#4CAF50'
_THUMB_DRAG_COLOR = '#3A7A3A'


class PillowSlider(BaseComponent):
    """水平滑块 — Pillow 轨道 + 椭圆滑块 + 拖拽交互。"""

    def __init__(self, x=0, y=0, w=200, h=24,
                 from_val=0.0, to_val=1.0, steps=10,
                 variable=None, command=None):
        super().__init__(x, y, w, h)
        self.from_val = from_val
        self.to_val = to_val
        self.steps = steps
        self._variable = variable
        self.command = command
        self._dragging = False

    def draw(self, cw, ch, font_scale=1.0):
        layer = create_layer(cw, ch)
        draw = ImageDraw.Draw(layer)
        x1, y1, x2, y2 = self.rect

        val = self._variable.get() if self._variable else 0
        ratio = (val - self.from_val) / (self.to_val - self.from_val)
        ratio = max(0.0, min(1.0, ratio))

        track_y = y1 + (y2 - y1) // 2
        track_l = x1 + _TRACK_INSET
        track_r = x2 - _TRACK_INSET

        # 轨道底线
        draw.line([(track_l, track_y), (track_r, track_y)],
                  fill=hex_to_rgba(_TRACK_COLOR), width=4)

        # 已填充段
        fill_x = track_l + int((track_r - track_l) * ratio)
        if fill_x > track_l + 2:
            draw.line([(track_l, track_y), (fill_x, track_y)],
                      fill=hex_to_rgba(_FILL_COLOR), width=4)

        # 滑块椭圆
        thumb_color = hex_to_rgba(_THUMB_DRAG_COLOR) if self._dragging else hex_to_rgba(_THUMB_COLOR)
        draw.ellipse(
            [(fill_x - _THUMB_RADIUS, track_y - _THUMB_RADIUS),
             (fill_x + _THUMB_RADIUS, track_y + _THUMB_RADIUS)],
            fill=thumb_color
        )

        return layer

    def apply_theme(self, theme_colors):
        """
        从 ThemeColors 更新滑块颜色
        :param theme_colors: ThemeColors 类
        """
        global _TRACK_COLOR, _FILL_COLOR, _THUMB_COLOR, _THUMB_DRAG_COLOR
        _TRACK_COLOR = theme_colors.get('bg_card')
        _FILL_COLOR = theme_colors.get('accent')
        _THUMB_COLOR = theme_colors.get('accent')
        _THUMB_DRAG_COLOR = theme_colors.get('accent_hover')

    def hit_test(self, mx, my):
        x1, y1, x2, y2 = self.rect
        return x1 <= mx <= x2 and (y1 - 8) <= my <= (y2 + 8)

    def on_click(self, event):
        self._dragging = True
        self._update_from_mouse(event.x)
        if self._parent:
            self._parent.mark_dirty()

    def on_drag(self, event):
        """拖拽中持续更新滑块位置。"""
        if self._dragging:
            self._update_from_mouse(event.x)
            if self._parent:
                self._parent.mark_dirty()

    def on_release(self, event):
        self._dragging = False
        self._update_from_mouse(event.x)
        if self.command:
            self.command(self._variable.get() if self._variable else 0)
        if self._parent:
            self._parent.mark_dirty()

    def on_enter(self):
        pass

    def on_leave(self):
        pass

    def _update_from_mouse(self, mx):
        """
        根据鼠标 x 坐标更新滑块值
        :param mx: 鼠标 x 坐标
        """
        if not self._variable:
            return
        x1, _, x2, _ = self.rect
        track_l = x1 + _TRACK_INSET
        track_r = x2 - _TRACK_INSET
        ratio = max(0.0, min(1.0, (mx - track_l) / (track_r - track_l)))
        val = self.from_val + ratio * (self.to_val - self.from_val)

        if self.steps > 0:
            step_size = (self.to_val - self.from_val) / self.steps
            val = round(val / step_size) * step_size

        val = max(self.from_val, min(self.to_val, val))
        self._variable.set(val)
