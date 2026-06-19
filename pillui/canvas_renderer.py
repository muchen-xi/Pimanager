"""
PageCanvas — 全页面 Canvas + 组件管理 + 事件分发
"""
import tkinter as tk
from PIL import Image, ImageTk

from .renderer import hex_to_rgba
from .image_utils import fit_image


# BaseComponent — 所有 Pillow 组件的抽象基类

class BaseComponent:
    """所有 Pillow UI 组件的基类。"""

    def __init__(self, x=0, y=0, w=0, h=0):
        self.rect = (x, y, x + w, y + h)
        self.visible = True
        self._parent = None

    def draw(self, cw, ch, font_scale=1.0):
        """
        在透明图层上绘制组件，返回 PIL Image
        :param cw: 整个 PageCanvas 的宽度
        :param ch: 整个 PageCanvas 的高度
        :param font_scale: 字体缩放因子
        :return: PIL RGBA Image 图层
        """
        raise NotImplementedError

    def hit_test(self, mx, my):
        """
        判断鼠标坐标是否在组件范围内
        :param mx: 鼠标 x 坐标
        :param my: 鼠标 y 坐标
        :return: bool
        """
        x1, y1, x2, y2 = self.rect
        return x1 <= mx <= x2 and y1 <= my <= y2

    def on_click(self, event):
        """左键按下。"""
        pass

    def on_release(self, event):
        """左键释放。"""
        pass

    def on_enter(self):
        """鼠标进入组件区域。"""
        pass

    def on_leave(self):
        """鼠标离开组件区域。"""
        pass

    def on_drag(self, event):
        """鼠标拖拽中。"""
        pass

    def on_mousewheel(self, event):
        """鼠标滚轮。"""
        pass

    def apply_theme(self, theme_colors):
        """
        应用主题颜色，子类重写以更新自身的颜色属性
        :param theme_colors: ThemeColors 类
        """
        pass

    @property
    def x(self):
        return self.rect[0]

    @property
    def y(self):
        return self.rect[1]

    @property
    def w(self):
        return self.rect[2] - self.rect[0]

    @property
    def h(self):
        return self.rect[3] - self.rect[1]

    def set_pos(self, x, y):
        """
        更新组件位置
        :param x: 新 x 坐标
        :param y: 新 y 坐标
        """
        w, h = self.w, self.h
        self.rect = (x, y, x + w, y + h)

    def set_size(self, w, h):
        """
        更新组件尺寸
        :param w: 新宽度
        :param h: 新高度
        """
        x, y = self.x, self.y
        self.rect = (x, y, x + w, y + h)


# PageCanvas — 主 Canvas：合成 + 事件 + 组件管理

class PageCanvas(tk.Canvas):
    """全页面 Canvas，管理 Pillow 组件的渲染和交互。

    使用方式:
      canvas = PageCanvas(master, width=800, height=600)
      canvas.set_bg_color("#0D1117")
      btn = PillowButton("Click", x=10, y=10, w=100, h=36, command=my_func)
      canvas.add("my_btn", btn)
      canvas.grid(row=0, column=0, sticky="nsew")

    组件按 add 顺序叠加，hit-test 从上层开始。
    """

    def __init__(self, master, width=400, height=300, **kwargs):
        super().__init__(master, width=width, height=height,
                         highlightthickness=0, bd=0, **kwargs)

        self._components = {}
        self._bg_color = '#0D1117'
        self._bg_image = None
        self._fit_mode = 'cover'
        self._dirty = False
        self._tk_image_ref = None
        self._hovered = None
        self._font_scale = 1.0
        self._idle_id = None

        # 绑定鼠标/窗口事件
        self.bind('<Button-1>', self._on_click)
        self.bind('<B1-Motion>', self._on_drag)
        self.bind('<ButtonRelease-1>', self._on_release)
        self.bind('<Motion>', self._on_motion)
        self.bind('<MouseWheel>', self._on_mousewheel)
        self.bind('<Configure>', self._on_resize)

    # 组件管理

    def add(self, comp_id, comp):
        """
        注册组件
        :param comp_id: 唯一组件 ID
        :param comp: BaseComponent 实例
        """
        comp._parent = self
        self._components[comp_id] = comp
        self.mark_dirty()

    def remove(self, comp_id):
        """
        移除组件
        :param comp_id: 组件 ID
        """
        if comp_id in self._components:
            del self._components[comp_id]
            if self._hovered == comp_id:
                self._hovered = None
            self.mark_dirty()

    def get(self, comp_id):
        """
        获取组件
        :param comp_id: 组件 ID
        :return: BaseComponent 或 None
        """
        return self._components.get(comp_id)

    def clear(self):
        """清空所有组件。"""
        self._components.clear()
        self._hovered = None
        self.mark_dirty()

    # 背景

    def set_bg_color(self, color):
        """
        设置背景颜色
        :param color: hex 颜色字符串
        """
        self._bg_color = color
        self._bg_image = None
        self.mark_dirty()

    def set_bg_image(self, pil_image, fit_mode='cover'):
        """
        设置背景图片
        :param pil_image: PIL Image 对象
        :param fit_mode: 适配模式 cover/contain/fill/tile
        """
        self._bg_image = pil_image
        self._fit_mode = fit_mode
        self.mark_dirty()

    def get_bg_image(self):
        """
        获取当前背景图
        :return: PIL Image 或 None
        """
        return self._bg_image

    def set_fit_mode(self, mode):
        """
        设置背景适配模式
        :param mode: cover/contain/fill/tile
        """
        self._fit_mode = mode
        if self._bg_image:
            self.mark_dirty()

    def get_fit_mode(self):
        """
        获取当前背景适配模式
        :return: 适配模式字符串
        """
        return self._fit_mode

    # 渲染

    def mark_dirty(self):
        """标记需要重绘。取消前一个待执行 idle，避免堆积。"""
        if self._idle_id is not None:
            self.after_cancel(self._idle_id)
            self._idle_id = None
        if not self._dirty:
            self._dirty = True
        self._idle_id = self.after(16, self._do_render)

    def _do_render(self):
        """执行实际渲染 (~60fps 节流)。"""
        self._idle_id = None
        self.render()

    def render(self):
        """合成所有组件 → 显示到 Canvas。"""
        self._dirty = False
        self._idle_id = None

        cw = self.winfo_width()
        ch = self.winfo_height()
        if cw < 20 or ch < 20:
            self._retry_count = getattr(self, '_retry_count', 0) + 1
            if self._retry_count > 30:
                return
            self._dirty = True
            self._idle_id = self.after(100, self.render)
            return
        self._retry_count = 0

        # Layer 0: 背景
        if self._bg_image:
            bg = fit_image(self._bg_image, cw, ch, self._fit_mode)
            base = bg.convert('RGBA') if bg.mode != 'RGBA' else bg
        else:
            base = Image.new('RGBA', (cw, ch),
                             hex_to_rgba(self._bg_color))

        # Layer 1..N: 组件逐层叠加
        for comp in self._components.values():
            if comp.visible:
                try:
                    layer = comp.draw(cw, ch, font_scale=self._font_scale)
                    if layer and layer.mode == 'RGBA':
                        base = Image.alpha_composite(base, layer)
                except Exception as e:
                    print('[PageCanvas] %s draw error: %s' % (type(comp).__name__, e))

        # 显示到 tk Canvas
        self._tk_image_ref = ImageTk.PhotoImage(base)
        self.delete('all')
        self.create_image(0, 0, anchor='nw', image=self._tk_image_ref)

    # 事件分发

    def _on_click(self, event):
        """左键按下 — 从上到下 hit-test。"""
        for comp_id in reversed(list(self._components.keys())):
            comp = self._components[comp_id]
            if comp.visible and comp.hit_test(event.x, event.y):
                comp.on_click(event)
                return

    def _on_drag(self, event):
        """鼠标拖拽 — 交给当前 hover 的组件。"""
        if self._hovered:
            comp = self._components.get(self._hovered)
            if comp:
                comp.on_drag(event)

    def _on_release(self, event):
        """左键释放 — 交给当前 hover 的组件。"""
        if self._hovered:
            comp = self._components.get(self._hovered)
            if comp:
                comp.on_release(event)

    def _on_motion(self, event):
        """鼠标移动 — 跟踪 hover 状态变化。"""
        new_hover = None
        for comp_id in reversed(list(self._components.keys())):
            comp = self._components[comp_id]
            if comp.visible and comp.hit_test(event.x, event.y):
                new_hover = comp_id
                break

        if new_hover != self._hovered:
            # 离开旧组件
            if self._hovered:
                old = self._components.get(self._hovered)
                if old:
                    old.on_leave()
            # 进入新组件
            if new_hover:
                new = self._components.get(new_hover)
                if new:
                    new.on_enter()
            self._hovered = new_hover
            self.mark_dirty()

    def _on_mousewheel(self, event):
        """滚轮 — 交给当前 hover 的组件。"""
        if self._hovered:
            comp = self._components.get(self._hovered)
            if comp:
                comp.on_mousewheel(event)

    def _on_resize(self, event):
        """窗口大小改变 → 立即安排重绘。"""
        self.mark_dirty()

    # 工具

    def apply_theme(self, theme_colors=None):
        """
        将主题颜色传播到所有组件并触发重绘
        :param theme_colors: ThemeColors 类，若未传则自动导入
        """
        if theme_colors is None:
            try:
                from pimanager.theme import ThemeColors as tc
                theme_colors = tc
            except ImportError:
                return
        for comp in self._components.values():
            if hasattr(comp, 'apply_theme'):
                comp.apply_theme(theme_colors)
        self.mark_dirty()

    def set_font_scale(self, scale):
        """
        设置字体缩放因子
        :param scale: 缩放比例
        """
        self._font_scale = float(scale)
        self.mark_dirty()

    @property
    def font_scale(self):
        return self._font_scale
