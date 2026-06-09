"""
PiManager 主题颜色系统 — 深色/浅色自动切换
所有 Canvas 渲染组件通过 ThemeColors.get(key) 获取颜色
"""
import customtkinter as ctk


class ThemeColors:
    """统一颜色令牌 — 深色/浅色自动切换。"""

    _dark = {
        "bg": "#0D1117",
        "bg_card": "#161B22",
        "text": "#C9D1D9",
        "text_secondary": "#8B949E",
        "accent": "#4CAF50",
        "accent_hover": "#3A7A3A",
        "accent_dim": "#2B5B2B",
        "danger": "#8B0000",
        "danger_hover": "#A00000",
        "warning": "#FFB347",
        "warning_strong": "#FF4444",
        "card_border": ("gray55", "gray35"),
        "btn_primary": "#2B5B2B",
        "btn_primary_hover": "#3A7A3A",
        "btn_transparent_hover": "#333333",
        "separator": ("gray70", "gray30"),
        "input_placeholder": "#555555",
        "scrollbar": "#555555",
        "scrollbar_track": "#1A1A1A",
        "nav_active": ("gray80", "gray28"),
        "dual_btn": "#1E3A5A",
        "dual_btn_hover": "#2A4A6A",
        "terminal_prompt": "#4CAF50",
        "status_ok": "#4CAF50",
        "local_file_name": "#8BCCFF",
        # Canvas 渲染专用
        "canvas_bg": "#0D1117",
        "canvas_text": "#C9D1D9",
        "canvas_text_dim": "#8B949E",
        "canvas_selection": "#2A5A2A",
        "canvas_err": "#FF6B6B",
        "canvas_quick_btn": "#1E3A1E",
        "canvas_quick_btn_hover": "#2A4A2A",
    }

    _light = {
        "bg": "#FFFFFF",
        "bg_card": "#F6F8FA",
        "text": "#24292F",
        "text_secondary": "#656D76",
        "accent": "#2DA44E",
        "accent_hover": "#2C974B",
        "accent_dim": "#DCF5E4",
        "danger": "#CF222E",
        "danger_hover": "#A40E26",
        "warning": "#D4A72C",
        "warning_strong": "#CF222E",
        "card_border": ("gray55", "gray35"),
        "btn_primary": "#2DA44E",
        "btn_primary_hover": "#2C974B",
        "btn_transparent_hover": "#E8E8E8",
        "separator": ("gray70", "gray30"),
        "input_placeholder": "#999999",
        "scrollbar": "#CCCCCC",
        "scrollbar_track": "#E8E8E8",
        "nav_active": ("gray75", "gray28"),
        "dual_btn": "#DDF4FF",
        "dual_btn_hover": "#C6ECFF",
        "terminal_prompt": "#2DA44E",
        "status_ok": "#2DA44E",
        "local_file_name": "#0969DA",
        # Canvas 渲染专用
        "canvas_bg": "#FFFFFF",
        "canvas_text": "#24292F",
        "canvas_text_dim": "#656D76",
        "canvas_selection": "#DCF5E4",
        "canvas_err": "#CF222E",
        "canvas_quick_btn": "#DCF5E4",
        "canvas_quick_btn_hover": "#C6ECFF",
    }

    @classmethod
    def _current(cls) -> dict:
        """获取当前主题的颜色映射。"""
        try:
            mode = ctk.get_appearance_mode()
        except Exception:
            mode = "Dark"
        return cls._dark if mode == "Dark" else cls._light

    # 字体缩放因子（由 SettingsPage / app 设置）
    _font_scale: float = 1.0

    @classmethod
    def get(cls, key: str):
        """获取颜色值。"""
        return cls._current().get(key, "#000000")

    @classmethod
    def fg_hover(cls, key: str) -> tuple:
        """获取 fg_color 和 hover_color 对。"""
        colors = cls._current()
        return (colors.get(key, "#000000"),
                colors.get(f"{key}_hover", "#222222"))

    @classmethod
    def set_font_scale(cls, scale: float):
        """设置字体缩放因子（1.0 = 默认）。"""
        cls._font_scale = float(scale)

    @classmethod
    def get_font_scale(cls) -> float:
        """获取字体缩放因子。"""
        return cls._font_scale

    @classmethod
    def scaled_font(cls, family: str, size: int) -> tuple:
        """返回缩放后的字体元组 (family, size)。"""
        return (family, int(size * cls._font_scale))
