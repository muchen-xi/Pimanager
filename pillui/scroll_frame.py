"""
PillowScrollFrame — 可滚动内容区域
"""
import tkinter as tk

from .canvas_renderer import PageCanvas


class PillowScrollFrame(PageCanvas):
    """可滚动页面 — 存放内容组件的 Canvas，带 tk.Scrollbar。"""

    def __init__(self, master, width=400, height=300,
                 content_height=600, **kwargs):
        super().__init__(master, width=width, height=height, **kwargs)
        self._content_height = content_height
        self._scroll_y = 0

        # 滚动条
        self._scrollbar = tk.Scrollbar(master, orient='vertical',
                                       command=self._on_scrollbar)
        self._scrollbar.grid(row=0, column=1, sticky='ns')

        # 重绑定滚轮事件到自己的处理器
        self.unbind('<MouseWheel>')
        self.bind('<MouseWheel>', self._on_mousewheel)

    def _on_mousewheel(self, event):
        """滚轮滚动 — 更新 scroll_y 并重绘。"""
        delta = -1 if event.delta > 0 else 1
        visible_h = self.winfo_height()
        self._scroll_y = max(0, min(
            self._content_height - visible_h,
            self._scroll_y + delta * 30
        ))
        # 同步滚动条位置
        if self._content_height > visible_h:
            thumb_ratio = visible_h / self._content_height
            pos = self._scroll_y / (self._content_height - visible_h)
            self._scrollbar.set(pos, pos + thumb_ratio)
        self.render()

    def _on_scrollbar(self, *args):
        """滚动条拖动 — 更新 scroll_y 并重绘。"""
        if args[0] == 'moveto':
            ratio = float(args[1])
            visible_h = self.winfo_height()
            self._scroll_y = int(
                ratio * (self._content_height - visible_h))
            self.render()

    def render(self):
        """重写 render，按 _scroll_y 偏移所有组件坐标后绘制。"""
        # 保存原始坐标
        offsets = {}
        for cid, comp in self._components.items():
            offsets[cid] = (comp.x, comp.y)
            comp.set_pos(comp.x, comp.y - self._scroll_y)

        try:
            super().render()
        finally:
            # 恢复原始坐标
            for cid, (ox, oy) in offsets.items():
                comp = self._components.get(cid)
                if comp:
                    comp.set_pos(ox, oy)

    def set_content_height(self, h):
        """
        设置内容总高度
        :param h: 内容高度（像素）
        """
        self._content_height = h
        self.render()
