"""
测试 theme.py — 主题颜色系统深色/浅色切换逻辑
"""
import unittest
import sys
import os

from pimanager.theme import ThemeColors


class TestThemeModeToggle(unittest.TestCase):
    """测试主题模式切换"""

    def setUp(self):
        """每个测试前重置为深色模式。"""
        ThemeColors.set_mode('dark')
        ThemeColors.set_font_scale(1.0)

    def test_default_mode_is_dark(self):
        """默认模式应为深色。"""
        self.assertEqual(ThemeColors.get_mode(), 'Dark')

    def test_set_mode_dark(self):
        """设置为深色模式后 get_mode 返回 'Dark'。"""
        ThemeColors.set_mode('dark')
        self.assertEqual(ThemeColors.get_mode(), 'Dark')

    def test_set_mode_light(self):
        """设置为浅色模式后 get_mode 返回 'Light'。"""
        ThemeColors.set_mode('light')
        self.assertEqual(ThemeColors.get_mode(), 'Light')

    def test_set_mode_case_insensitive(self):
        """set_mode 应不区分大小写。"""
        ThemeColors.set_mode('DARK')
        self.assertEqual(ThemeColors.get_mode(), 'Dark')
        ThemeColors.set_mode('LIGHT')
        self.assertEqual(ThemeColors.get_mode(), 'Light')
        ThemeColors.set_mode('DaRk')
        self.assertEqual(ThemeColors.get_mode(), 'Dark')

    def test_toggle_mode(self):
        """toggle_mode — 在深色/浅色之间切换。"""
        self.assertEqual(ThemeColors.get_mode(), 'Dark')
        ThemeColors.toggle_mode()
        self.assertEqual(ThemeColors.get_mode(), 'Light')
        ThemeColors.toggle_mode()
        self.assertEqual(ThemeColors.get_mode(), 'Dark')

    def test_invalid_mode_falls_back_to_light(self):
        """无效的模式名应回退到浅色模式。"""
        ThemeColors.set_mode('invalid')
        self.assertEqual(ThemeColors.get_mode(), 'Light')
        ThemeColors.set_mode('')
        self.assertEqual(ThemeColors.get_mode(), 'Light')
        ThemeColors.set_mode('blue')
        self.assertEqual(ThemeColors.get_mode(), 'Light')


class TestThemeColorsGet(unittest.TestCase):
    """测试颜色令牌获取"""

    def setUp(self):
        ThemeColors.set_mode('dark')
        ThemeColors.set_font_scale(1.0)

    def test_dark_bg_color(self):
        """深色模式背景色应为 '#0D1117'。"""
        self.assertEqual(ThemeColors.get('bg'), '#0D1117')

    def test_dark_text_color(self):
        """深色模式文字色应为 '#C9D1D9'。"""
        self.assertEqual(ThemeColors.get('text'), '#C9D1D9')

    def test_dark_accent_color(self):
        """深色模式强调色应为 '#4CAF50'。"""
        self.assertEqual(ThemeColors.get('accent'), '#4CAF50')

    def test_dark_card_bg(self):
        """深色模式卡片背景应为 '#161B22'。"""
        self.assertEqual(ThemeColors.get('bg_card'), '#161B22')

    def test_dark_danger_color(self):
        """深色模式危险色应为 '#8B0000'。"""
        self.assertEqual(ThemeColors.get('danger'), '#8B0000')

    def test_dark_success_color(self):
        """深色模式成功色应为 '#4CAF50'。"""
        self.assertEqual(ThemeColors.get('status_ok'), '#4CAF50')

    def test_dark_warning_color(self):
        """深色模式警告色应为 '#FFB347'。"""
        self.assertEqual(ThemeColors.get('warning'), '#FFB347')

    def test_light_bg_color(self):
        """浅色模式背景色应为 '#FFFFFF'。"""
        ThemeColors.set_mode('light')
        self.assertEqual(ThemeColors.get('bg'), '#FFFFFF')

    def test_light_text_color(self):
        """浅色模式文字色应为 '#24292F'。"""
        ThemeColors.set_mode('light')
        self.assertEqual(ThemeColors.get('text'), '#24292F')

    def test_light_accent_color(self):
        """浅色模式强调色应为 '#2DA44E'。"""
        ThemeColors.set_mode('light')
        self.assertEqual(ThemeColors.get('accent'), '#2DA44E')

    def test_light_card_bg(self):
        """浅色模式卡片背景应为 '#F6F8FA'。"""
        ThemeColors.set_mode('light')
        self.assertEqual(ThemeColors.get('bg_card'), '#F6F8FA')

    def test_light_danger_color(self):
        """浅色模式危险色应为 '#CF222E'。"""
        ThemeColors.set_mode('light')
        self.assertEqual(ThemeColors.get('danger'), '#CF222E')

    def test_light_success_color(self):
        """浅色模式成功色应为 '#2DA44E'。"""
        ThemeColors.set_mode('light')
        self.assertEqual(ThemeColors.get('status_ok'), '#2DA44E')

    def test_light_warning_color(self):
        """浅色模式警告色应为 '#D4A72C'。"""
        ThemeColors.set_mode('light')
        self.assertEqual(ThemeColors.get('warning'), '#D4A72C')

    def test_unknown_key_fallback(self):
        """未知颜色键应返回 '#000000' 作为回退。"""
        self.assertEqual(ThemeColors.get('nonexistent_key'), '#000000')

    def test_mode_switch_changes_colors(self):
        """切换模式后颜色值应随之变化。"""
        dark_bg = ThemeColors.get('bg')
        ThemeColors.set_mode('light')
        light_bg = ThemeColors.get('bg')
        self.assertNotEqual(dark_bg, light_bg)
        self.assertEqual(dark_bg, '#0D1117')
        self.assertEqual(light_bg, '#FFFFFF')

    def test_canvas_specific_colors_dark(self):
        """深色模式 Canvas 专用颜色。"""
        self.assertEqual(ThemeColors.get('canvas_bg'), '#0D1117')
        self.assertEqual(ThemeColors.get('canvas_text'), '#C9D1D9')
        self.assertEqual(ThemeColors.get('canvas_err'), '#FF6B6B')

    def test_canvas_specific_colors_light(self):
        """浅色模式 Canvas 专用颜色。"""
        ThemeColors.set_mode('light')
        self.assertEqual(ThemeColors.get('canvas_bg'), '#FFFFFF')
        self.assertEqual(ThemeColors.get('canvas_text'), '#24292F')
        self.assertEqual(ThemeColors.get('canvas_err'), '#CF222E')

    def test_border_color_is_tuple(self):
        """边框颜色应为元组类型。"""
        border = ThemeColors.get('card_border')
        self.assertIsInstance(border, tuple)
        self.assertEqual(len(border), 2)

    def test_separator_color_is_tuple(self):
        """分隔线颜色应为元组类型。"""
        sep = ThemeColors.get('separator')
        self.assertIsInstance(sep, tuple)
        self.assertEqual(len(sep), 2)

    def test_nav_active_color_is_tuple(self):
        """导航激活色应为元组类型。"""
        nav = ThemeColors.get('nav_active')
        self.assertIsInstance(nav, tuple)
        self.assertEqual(len(nav), 2)

    def test_all_dark_color_tokens_accessible(self):
        """深色模式所有颜色令牌均可正常获取。"""
        dark_keys = [
            'bg', 'bg_card', 'text', 'text_secondary',
            'accent', 'accent_hover', 'accent_dim',
            'danger', 'danger_hover', 'warning', 'warning_strong',
            'card_border', 'btn_primary', 'btn_primary_hover',
            'btn_transparent_hover', 'separator', 'input_placeholder',
            'scrollbar', 'scrollbar_track', 'nav_active',
            'dual_btn', 'dual_btn_hover', 'terminal_prompt',
            'status_ok', 'local_file_name',
            'canvas_bg', 'canvas_text', 'canvas_text_dim',
            'canvas_selection', 'canvas_err',
            'canvas_quick_btn', 'canvas_quick_btn_hover',
        ]
        for key in dark_keys:
            color = ThemeColors.get(key)
            self.assertIsNotNone(color, '键 "%s" 返回了 None' % key)
            self.assertIsInstance(color, (str, tuple),
                                  '键 "%s" 类型异常: %s' % (key, type(color)))

    def test_all_light_color_tokens_accessible(self):
        """浅色模式所有颜色令牌均可正常获取。"""
        ThemeColors.set_mode('light')
        light_keys = [
            'bg', 'bg_card', 'text', 'text_secondary',
            'accent', 'accent_hover', 'accent_dim',
            'danger', 'danger_hover', 'warning', 'warning_strong',
            'card_border', 'btn_primary', 'btn_primary_hover',
            'btn_transparent_hover', 'separator', 'input_placeholder',
            'scrollbar', 'scrollbar_track', 'nav_active',
            'dual_btn', 'dual_btn_hover', 'terminal_prompt',
            'status_ok', 'local_file_name',
            'canvas_bg', 'canvas_text', 'canvas_text_dim',
            'canvas_selection', 'canvas_err',
            'canvas_quick_btn', 'canvas_quick_btn_hover',
        ]
        for key in light_keys:
            color = ThemeColors.get(key)
            self.assertIsNotNone(color, '键 "%s" 返回了 None' % key)
            self.assertIsInstance(color, (str, tuple),
                                  '键 "%s" 类型异常: %s' % (key, type(color)))


class TestThemeFgHover(unittest.TestCase):
    """测试 fg_hover 方法"""

    def setUp(self):
        ThemeColors.set_mode('dark')
        ThemeColors.set_font_scale(1.0)

    def test_fg_hover_returns_pair(self):
        """fg_hover 应返回 (fg, hover) 元组。"""
        result = ThemeColors.fg_hover('btn_primary')
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)

    def test_fg_hover_btn_primary_dark(self):
        """深色模式主按钮 fg_hover。"""
        fg, hover = ThemeColors.fg_hover('btn_primary')
        self.assertEqual(fg, '#2B5B2B')
        self.assertEqual(hover, '#3A7A3A')

    def test_fg_hover_danger_dark(self):
        """深色模式危险按钮 fg_hover（无 _hover 后缀）。"""
        fg, hover = ThemeColors.fg_hover('danger')
        self.assertEqual(fg, '#8B0000')
        self.assertEqual(hover, '#A00000')

    def test_fg_hover_accent_dark(self):
        """深色模式强调色 fg_hover。"""
        fg, hover = ThemeColors.fg_hover('accent')
        self.assertEqual(fg, '#4CAF50')
        self.assertEqual(hover, '#3A7A3A')

    def test_fg_hover_nonexistent_key(self):
        """不存在的键应返回回退值。"""
        fg, hover = ThemeColors.fg_hover('no_such_key')
        self.assertEqual(fg, '#000000')
        self.assertEqual(hover, '#222222')

    def test_fg_hover_light_mode(self):
        """浅色模式 fg_hover。"""
        ThemeColors.set_mode('light')
        fg, hover = ThemeColors.fg_hover('btn_primary')
        self.assertEqual(fg, '#2DA44E')
        self.assertEqual(hover, '#2C974B')


class TestFontScale(unittest.TestCase):
    """测试字体缩放"""

    def setUp(self):
        ThemeColors.set_mode('dark')
        ThemeColors.set_font_scale(1.0)

    def test_default_font_scale(self):
        """默认字体缩放因子应为 1.0。"""
        self.assertEqual(ThemeColors.get_font_scale(), 1.0)

    def test_set_font_scale_normal(self):
        """设置正常缩放因子。"""
        ThemeColors.set_font_scale(1.5)
        self.assertEqual(ThemeColors.get_font_scale(), 1.5)

    def test_set_font_scale_small(self):
        """设置小于 1 的缩放因子。"""
        ThemeColors.set_font_scale(0.75)
        self.assertEqual(ThemeColors.get_font_scale(), 0.75)

    def test_set_font_scale_large(self):
        """设置大于 1 的缩放因子。"""
        ThemeColors.set_font_scale(2.0)
        self.assertEqual(ThemeColors.get_font_scale(), 2.0)

    def test_set_font_scale_int_converts_to_float(self):
        """整数输入应转换为浮点数。"""
        ThemeColors.set_font_scale(2)
        self.assertEqual(ThemeColors.get_font_scale(), 2.0)
        self.assertIsInstance(ThemeColors.get_font_scale(), float)

    def test_scaled_font_default(self):
        """默认缩放 (1.0) 下字体尺寸不变。"""
        family, size = ThemeColors.scaled_font('msyh', 12)
        self.assertEqual(family, 'msyh')
        self.assertEqual(size, 12)

    def test_scaled_font_enlarged(self):
        """放大后字体尺寸应增大。"""
        ThemeColors.set_font_scale(1.5)
        family, size = ThemeColors.scaled_font('msyh', 12)
        self.assertEqual(family, 'msyh')
        self.assertEqual(size, 18)

    def test_scaled_font_reduced(self):
        """缩小后字体尺寸应减小。"""
        ThemeColors.set_font_scale(0.5)
        family, size = ThemeColors.scaled_font('msyh', 14)
        self.assertEqual(family, 'msyh')
        self.assertEqual(size, 7)

    def test_scaled_font_rounds_to_int(self):
        """缩放后尺寸应为整数。"""
        ThemeColors.set_font_scale(1.3)
        family, size = ThemeColors.scaled_font('msyh', 10)
        self.assertEqual(size, 13)
        self.assertIsInstance(size, int)

    def test_font_scale_class_level_shared(self):
        """字体缩放因子是类级别共享的。"""
        ThemeColors.set_font_scale(2.0)
        # 直接读取类属性确认
        self.assertEqual(ThemeColors._font_scale, 2.0)


if __name__ == '__main__':
    unittest.main()
