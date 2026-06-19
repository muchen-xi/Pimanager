"""
PiManager 主题颜色系统 — 深色/浅色自动切换 (v2: 去 CTk 依赖)
所有组件通过 ThemeColors.get(key) 获取颜色
"""


# 统一颜色令牌 — 深色/浅色自动切换
class ThemeColors:
    # 类级别状态：_mode 和 _font_scale 跨所有调用共享
    _mode = 'Dark'
    _color_theme = 'green'

    _color_accents = {
        'green': {
            'dark': {'accent': '#4CAF50', 'accent_hover': '#3A7A3A', 'accent_dim': '#2B5B2B', 'btn_primary': '#2B5B2B', 'btn_primary_hover': '#3A7A3A'},
            'light': {'accent': '#2DA44E', 'accent_hover': '#2C974B', 'accent_dim': '#DCF5E4', 'btn_primary': '#2DA44E', 'btn_primary_hover': '#2C974B'}
        },
        'blue': {
            'dark': {'accent': '#58A6FF', 'accent_hover': '#1F6FEB', 'accent_dim': '#1A3A5C', 'btn_primary': '#1A3A5C', 'btn_primary_hover': '#1F6FEB'},
            'light': {'accent': '#0969DA', 'accent_hover': '#0550AE', 'accent_dim': '#DDF4FF', 'btn_primary': '#0969DA', 'btn_primary_hover': '#0550AE'}
        },
        'dark-blue': {
            'dark': {'accent': '#79C0FF', 'accent_hover': '#1F6FEB', 'accent_dim': '#0D2B4A', 'btn_primary': '#0D2B4A', 'btn_primary_hover': '#1A3A5C'},
            'light': {'accent': '#0550AE', 'accent_hover': '#033D8B', 'accent_dim': '#DDF4FF', 'btn_primary': '#0550AE', 'btn_primary_hover': '#033D8B'}
        },
    }

    _dark = {
        'bg': '#0D1117',
        'bg_card': '#161B22',
        'text': '#C9D1D9',
        'text_secondary': '#8B949E',
        'accent': '#4CAF50',
        'accent_hover': '#3A7A3A',
        'accent_dim': '#2B5B2B',
        'danger': '#8B0000',
        'danger_hover': '#A00000',
        'warning': '#FFB347',
        'warning_strong': '#FF4444',
        'card_border': ('#D0D7DE', '#8B949E'),
        'btn_primary': '#2B5B2B',
        'btn_primary_hover': '#3A7A3A',
        'btn_transparent_hover': '#333333',
        'separator': ('#E0E0E0', '#D0D0D0'),
        'input_placeholder': '#555555',
        'scrollbar': '#555555',
        'scrollbar_track': '#1A1A1A',
        'nav_active': ('#C9D1D9', '#21262D'),
        'dual_btn': '#1E3A5A',
        'dual_btn_hover': '#2A4A6A',
        'terminal_prompt': '#4CAF50',
        'status_ok': '#4CAF50',
        'local_file_name': '#8BCCFF',
        # Canvas 渲染专用
        'canvas_bg': '#0D1117',
        'canvas_text': '#C9D1D9',
        'canvas_text_dim': '#8B949E',
        'canvas_selection': '#2A5A2A',
        'canvas_err': '#FF6B6B',
        'canvas_quick_btn': '#1E3A1E',
        'canvas_quick_btn_hover': '#2A4A2A',
    }

    _light = {
        'bg': '#FFFFFF',
        'bg_card': '#F6F8FA',
        'text': '#24292F',
        'text_secondary': '#656D76',
        'accent': '#2DA44E',
        'accent_hover': '#2C974B',
        'accent_dim': '#DCF5E4',
        'danger': '#CF222E',
        'danger_hover': '#A40E26',
        'warning': '#D4A72C',
        'warning_strong': '#CF222E',
        'card_border': ('#D0D7DE', '#8B949E'),
        'btn_primary': '#2DA44E',
        'btn_primary_hover': '#2C974B',
        'btn_transparent_hover': '#E8E8E8',
        'separator': ('#E0E0E0', '#D0D0D0'),
        'input_placeholder': '#999999',
        'scrollbar': '#CCCCCC',
        'scrollbar_track': '#E8E8E8',
        'nav_active': ('#24292F', '#D0D7DE'),
        'dual_btn': '#DDF4FF',
        'dual_btn_hover': '#C6ECFF',
        'terminal_prompt': '#2DA44E',
        'status_ok': '#2DA44E',
        'local_file_name': '#0969DA',
        # Canvas 渲染专用
        'canvas_bg': '#FFFFFF',
        'canvas_text': '#24292F',
        'canvas_text_dim': '#656D76',
        'canvas_selection': '#DCF5E4',
        'canvas_err': '#CF222E',
        'canvas_quick_btn': '#DCF5E4',
        'canvas_quick_btn_hover': '#C6ECFF',
    }

    @classmethod
    def _current(cls):
        """获取当前主题的颜色映射。"""
        return cls._dark if cls._mode == 'Dark' else cls._light

    @classmethod
    def set_mode(cls, mode):
        """设置主题模式: 'dark' 或 'light'。"""
        cls._mode = 'Dark' if mode.lower() == 'dark' else 'Light'

    @classmethod
    def get_mode(cls):
        """获取当前主题模式。"""
        return cls._mode

    @classmethod
    def toggle_mode(cls):
        """切换主题。"""
        cls.set_mode('light' if cls._mode == 'Dark' else 'dark')

    # 字体缩放因子（由 SettingsPage / app 设置）
    _font_scale = 1.0

    @classmethod
    def set_color_theme(cls, name):
        """
        设置颜色主题
        :param name: 'green' | 'blue' | 'dark-blue'
        """
        if name in cls._color_accents:
            cls._color_theme = name

    @classmethod
    def get_color_theme(cls):
        """获取当前颜色主题名称。"""
        return cls._color_theme

    @classmethod
    def get(cls, key):
        """
        获取颜色值，优先使用当前颜色主题的覆盖值
        :param key: 颜色键名
        :return: hex 颜色字符串或元组
        """
        # 检查当前颜色主题的模式覆盖
        theme_accents = cls._color_accents.get(cls._color_theme, {})
        mode_key = 'dark' if cls._mode == 'Dark' else 'light'
        mode_accents = theme_accents.get(mode_key, {})
        if key in mode_accents:
            return mode_accents[key]
        return cls._current().get(key, '#000000')

    @classmethod
    def fg_hover(cls, key):
        """获取 fg_color 和 hover_color 对。"""
        colors = cls._current()
        return (colors.get(key, '#000000'),
                colors.get(key + '_hover', '#222222'))

    @classmethod
    def set_font_scale(cls, scale):
        """设置字体缩放因子（1.0 = 默认）。"""
        cls._font_scale = float(scale)

    @classmethod
    def get_font_scale(cls):
        """获取字体缩放因子。"""
        return cls._font_scale

    @classmethod
    def scaled_font(cls, family, size):
        """返回缩放后的字体元组 (family, size)。"""
        return (family, int(size * cls._font_scale))
