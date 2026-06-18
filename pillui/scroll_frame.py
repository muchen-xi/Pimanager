"""
PillowScrollFrame — 可滚动内容区域
"""
import tkinter as tk
from PIL import Image, ImageDraw

from .canvas_renderer import PageCanvas
from .renderer import hex_to_rgba, create_layer


class PillowScrollFrame(PageCanvas):
    """可滚动页面 — 存放内容组件的 Canvas，带 tk.Scrollbar。"""

    def __init__(self, master, width: int = 400, height: int = 300,
                 content_height: int = 600, **kwargs):
        super().__init__(master, width=width, height=height, **kwargs)
        self._content_height = content_height
        self._scroll_y = 0

        # 滚动条
        self._scrollbar = tk.Scrollbar(master, orient="vertical",
                                       command=self._on_scrollbar)
        self._scrollbar.grid(row=0, column=1, sticky="ns")

        # 重绑定滚轮事件
        self.unbind("<MouseWheel>")
        self.bind("<MouseWheel>", self._on_mousewheel)

    def _on_mousewheel(self, event):
        """滚轮滚动。"""
        delta = -1 if event.delta > 0 else 1
        self._scroll_y = max(0, min(
            self._content_height - self.winfo_height(),
            self._scroll_y + delta * 30
        ))
        # 更新滚动条位置
        if self._content_height > self.winfo_height():
            thumb_h = self.winfo_height() / self._content_height * self.winfo_height()
            pos = self._scroll_y / (self._content_height - self.winfo_height())
            self._scrollbar.set(pos, pos + thumb_h / self.winfo_height())
        self.render()

    def _on_scrollbar(self, *args):
        """滚动条拖动。"""
        if args[0] == "moveto":
            ratio = float(args[1])
            self._scroll_y = int(
                ratio * (self._content_height - self.winfo_height()))
            self.render()

    def render(self):
        """重写 render，应用 y 偏移。"""
        from .canvas_renderer import canvas_renderer
        # 偏移所有组件的绘制坐标
        # 简化方案：所有子组件在 add() 时就已设置好 y 坐标，
        # render 时按 _scroll_y 偏移。
        # Pillow 图层已经包含绝对坐标，我们只需要在最终显示时裁剪。
        #
        # 实际上我们需要一种方式让组件知道它们被偏移了。
        # 这里用最简方案：将所有子组件 y 向上移动 _scroll_y
        original_render = super().render

        # 保存原始 y 坐标
        offsets = {}
        for cid, comp in self._components.items():
            offsets[cid] = (comp.x, comp.y)
            comp.set_pos(comp.x, comp.y - self._scroll_y)

        try:
            original_render()
        finally:
            # 恢复原始坐标
            for cid, (ox, oy) in offsets.items():
                self._components[cid].set_pos(ox, oy)

    def set_content_height(self, h: int):
        self._content_height = h
        self.render()
