"""
PillowSlider — 水平滑块组件（支持拖拽）
"""
from PIL import Image, ImageDraw

from .canvas_renderer import BaseComponent
from .renderer import hex_to_rgba, hex_to_rgb, get_font, create_layer


class PillowSlider(BaseComponent):
    """水平滑块 — Pillow 轨道 + 椭圆滑块 + 拖拽。"""

    def __init__(self, x: int = 0, y: int = 0,
                 w: int = 200, h: int = 24,
                 from_val: float = 0.0, to_val: float = 1.0,
                 steps: int = 10, variable=None, command=None):
        super().__init__(x, y, w, h)
        self.from_val = from_val
        self.to_val = to_val
        self.steps = steps
        self._variable = variable  # tk.DoubleVar or tk.IntVar
        self.command = command
        self._dragging = False

    def draw(self, cw: int, ch: int) -> Image.Image:
        layer = create_layer(cw, ch)
        draw = ImageDraw.Draw(layer)
        x1, y1, x2, y2 = self.rect

        val = self._variable.get() if self._variable else 0
        ratio = (val - self.from_val) / (self.to_val - self.from_val)
        ratio = max(0.0, min(1.0, ratio))

        track_y = y1 + (y2 - y1) // 2
        track_l = x1 + 8
        track_r = x2 - 8

        # 轨道
        draw.line([(track_l, track_y), (track_r, track_y)],
                  fill=hex_to_rgba("#333333"), width=4)

        # 已填充段
        fill_x = track_l + int((track_r - track_l) * ratio)
        if fill_x > track_l + 2:
            draw.line([(track_l, track_y), (fill_x, track_y)],
                      fill=hex_to_rgba("#4CAF50"), width=4)

        # 滑块（椭圆）
        thumb_r = 7
        draw.ellipse(
            [(fill_x - thumb_r, track_y - thumb_r),
             (fill_x + thumb_r, track_y + thumb_r)],
            fill=hex_to_rgba("#4CAF50") if not self._dragging
            else hex_to_rgba("#3A7A3A")
        )

        return layer

    def hit_test(self, mx: int, my: int) -> bool:
        x1, y1, x2, y2 = self.rect
        # 扩大点击区域（上下各 +8px）
        return x1 <= mx <= x2 and (y1 - 8) <= my <= (y2 + 8)

    def on_click(self, event):
        self._dragging = True
        self._update_from_mouse(event.x)
        self._parent.mark_dirty()

    def on_drag(self, event):
        """拖拽中持续更新。"""
        if self._dragging:
            self._update_from_mouse(event.x)
            self._parent.mark_dirty()

    def on_release(self, event):
        self._dragging = False
        self._update_from_mouse(event.x)
        if self.command:
            self.command(self._variable.get())
        if self._parent:
            self._parent.mark_dirty()

    def _update_from_mouse(self, mx: int):
        if not self._variable:
            return
        x1, _, x2, _ = self.rect
        track_l = x1 + 8
        track_r = x2 - 8
        ratio = max(0.0, min(1.0, (mx - track_l) / (track_r - track_l)))
        val = self.from_val + ratio * (self.to_val - self.from_val)

        if self.steps > 0:
            step_size = (self.to_val - self.from_val) / self.steps
            val = round(val / step_size) * step_size

        val = max(self.from_val, min(self.to_val, val))
        self._variable.set(val)

    # 拖拽中需要持续跟踪鼠标
    def on_enter(self):
        pass

    def on_leave(self):
        pass
