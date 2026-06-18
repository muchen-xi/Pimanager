"""
pillui — Pillow UI 组件库 for PiManager v2

纯 Pillow 绘制 + tk.Canvas 显示的轻量 UI 组件。
完全替代 CustomTkinter，支持深色/浅色主题切换。
"""

from .renderer import hex_to_rgba, hex_to_rgb, get_font, create_layer, composite_layer, center_text
from ._draw_utils import draw_rounded_rect, draw_text_aligned, text_bbox
from .canvas_renderer import PageCanvas, BaseComponent
from .label import PillowLabel
from .button import PillowButton
from .progress_bar import PillowProgressBar
from .card import PillowCard
