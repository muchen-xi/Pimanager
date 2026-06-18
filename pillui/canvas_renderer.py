"""
PageCanvas — 全页面 Canvas + 组件管理 + 事件分发

每个页面（状态/设置/文件/终端/侧边栏）包含一个 PageCanvas。
所有 Pillow 组件注册到 PageCanvas，由它统一渲染和事件分发。
"""
import tkinter as tk
from PIL import Image, ImageTk

from .renderer import hex_to_rgba, create_layer, composite_layer, get_font
from ._draw_utils import draw_rounded_rect, draw_text_aligned, text_bbox


# ============================================================
#  BaseComponent — 所有 Pillow 组件的抽象基类
# ============================================================

class BaseComponent:
    """所有 Pillow UI 组件的基类。"""

    def __init__(self, x: int = 0, y: int = 0, w: int = 0, h: int = 0):
        self.rect = (x, y, x + w, y + h)  # (x1, y1, x2, y2)
        self.visible = True
        self._parent: 'PageCanvas' = None

    # ---- 子类必须实现 ----

    def draw(self, cw: int, ch: int) -> Image.Image:
        """在透明图层上绘制组件，返回 PIL Image。

        cw, ch = 整个 PageCanvas 的尺寸。组件的 rect 是绝对坐标。
        """
        raise NotImplementedError

    def hit_test(self, mx: int, my: int) -> bool:
        """判断鼠标坐标 (mx, my) 是否在组件范围内。"""
        x1, y1, x2, y2 = self.rect
        return x1 <= mx <= x2 and y1 <= my <= y2

    # ---- 可选覆盖 ----

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

    def on_mousewheel(self, event):
        """鼠标滚轮。"""
        pass

    # ---- 属性 ----

    @property
    def x(self): return self.rect[0]

    @property
    def y(self): return self.rect[1]

    @property
    def w(self): return self.rect[2] - self.rect[0]

    @property
    def h(self): return self.rect[3] - self.rect[1]

    def set_pos(self, x: int, y: int):
        """更新位置。"""
        w, h = self.w, self.h
        self.rect = (x, y, x + w, y + h)

    def set_size(self, w: int, h: int):
        """更新尺寸。"""
        x, y = self.x, self.y
        self.rect = (x, y, x + w, y + h)


# ============================================================
#  PageCanvas — 主 Canvas：合成 + 事件 + 组件管理
# ============================================================

class PageCanvas(tk.Canvas):
    """一个全页面 Canvas，管理 Pillow 组件的渲染和交互。

    使用方式:
      canvas = PageCanvas(master, width=800, height=600)
      canvas.set_bg_color("#0D1117")
      btn = PillowButton("Click", x=10, y=10, w=100, h=36, command=my_func)
      canvas.add("my_btn", btn)
      canvas.grid(row=0, column=0, sticky="nsew")

    组件按 add 顺序叠加（后加的在上层），hit-test 从上层开始。
    """

    def __init__(self, master, width: int = 400, height: int = 300, **kwargs):
        super().__init__(master, width=width, height=height,
                         highlightthickness=0, bd=0, **kwargs)

        self._components: dict[str, BaseComponent] = {}
        self._bg_color: str = "#0D1117"
        self._bg_image: Image.Image = None
        self._dirty: bool = False
        self._tk_image_ref = None  # 保持 PhotoImage 引用不回收
        self._hovered: str = None  # 当前悬停组件 ID

        # 字体缩放
        self._font_scale: float = 1.0

        # 绑定事件
        self.bind("<Button-1>", self._on_click)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Motion>", self._on_motion)
        self.bind("<MouseWheel>", self._on_mousewheel)
        self.bind("<Configure>", self._on_resize)

    # ========== 组件管理 ==========

    def add(self, comp_id: str, comp: BaseComponent):
        """注册一个组件。comp_id 必须唯一。"""
        comp._parent = self
        self._components[comp_id] = comp
        self.mark_dirty()

    def remove(self, comp_id: str):
        """移除一个组件。"""
        if comp_id in self._components:
            del self._components[comp_id]
            if self._hovered == comp_id:
                self._hovered = None
            self.mark_dirty()

    def get(self, comp_id: str) -> BaseComponent:
        """获取组件。"""
        return self._components.get(comp_id)

    def clear(self):
        """清空所有组件。"""
        self._components.clear()
        self._hovered = None
        self.mark_dirty()

    # ========== 背景 ==========

    def set_bg_color(self, color: str):
        """设置背景颜色（hex）。"""
        self._bg_color = color
        self._bg_image = None
        self.mark_dirty()

    def set_bg_image(self, pil_image: Image.Image):
        """设置背景图片（PIL Image）。"""
        self._bg_image = pil_image
        self.mark_dirty()

    def get_bg_image(self) -> Image.Image:
        """获取当前背景图。"""
        return self._bg_image

    # ========== 渲染 ==========

    def mark_dirty(self):
        """标记需要重绘。在下一个 idle 周期执行。"""
        if not self._dirty:
            self._dirty = True
            self.after_idle(self.render)

    def render(self):
        """合成所有组件 → 显示到 Canvas。"""
        self._dirty = False

        cw = self.winfo_width()
        ch = self.winfo_height()
        if cw < 20 or ch < 20:
            return

        # Layer 0: 背景
        if self._bg_image:
            bg = self._bg_image.resize((cw, ch), Image.LANCZOS)
            base = bg.convert("RGBA") if bg.mode != "RGBA" else bg
        else:
            base = Image.new("RGBA", (cw, ch),
                             hex_to_rgba(self._bg_color))

        # Layer 1..N: 组件
        for comp in self._components.values():
            if comp.visible:
                try:
                    layer = comp.draw(cw, ch)
                    if layer and layer.mode == "RGBA":
                        base = Image.alpha_composite(base, layer)
                except Exception as e:
                    print(f"[PageCanvas] {type(comp).__name__} draw error: {e}")

        # 显示
        self._tk_image_ref = ImageTk.PhotoImage(base)
        self.delete("all")
        self.create_image(0, 0, anchor="nw", image=self._tk_image_ref)

    # ========== 事件分发 ==========

    def _on_click(self, event):
        """左键按下 — 从上到下 hit-test。"""
        for comp_id in reversed(list(self._components.keys())):
            comp = self._components[comp_id]
            if comp.visible and comp.hit_test(event.x, event.y):
                comp.on_click(event)
                return

    def _on_release(self, event):
        """左键释放 — 交给当前 hover 的组件。"""
        if self._hovered:
            comp = self._components.get(self._hovered)
            if comp:
                comp.on_release(event)

    def _on_motion(self, event):
        """鼠标移动 — 跟踪 hover 状态。"""
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
        """窗口大小改变 → 延迟重绘。"""
        self.after(80, self.mark_dirty)

    # ========== 工具 ==========

    def set_font_scale(self, scale: float):
        """设置字体缩放因子。"""
        self._font_scale = float(scale)

    @property
    def font_scale(self) -> float:
        return self._font_scale
