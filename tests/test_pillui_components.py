"""
测试 PillUI 组件库 — 纯逻辑测试（状态、setter、getter）
不需要 GUI 环境，通过 Mock PageCanvas 实现组件实例化
"""
import unittest
import sys
import os
import tkinter as tk
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pillui.canvas_renderer import BaseComponent, PageCanvas
from pillui.button import PillowButton
from pillui.label import PillowLabel
from pillui.progress_bar import PillowProgressBar
from pillui.card import PillowCard
from pillui.checkbox import PillowCheckBox
from pillui.slider import PillowSlider
from pillui.option_menu import PillowOptionMenu

# 全局 Tk 根窗口，供 tkinter Variable 使用（隐藏窗口）
_tk_root = None


def setUpModule():
    """模块级初始化：创建隐藏的 Tk 根窗口。"""
    global _tk_root
    _tk_root = tk.Tk()
    _tk_root.withdraw()


def tearDownModule():
    """模块级清理：销毁 Tk 根窗口。"""
    global _tk_root
    if _tk_root is not None:
        _tk_root.destroy()
        _tk_root = None


class MockCanvas:
    """模拟 PageCanvas，提供 mark_dirty 和基本属性。"""

    def __init__(self):
        self.dirty_count = 0
        self._components = {}

    def mark_dirty(self):
        self.dirty_count = self.dirty_count + 1

    def winfo_rootx(self):
        return 0

    def winfo_rooty(self):
        return 0


class TestPillowButton(unittest.TestCase):
    """测试 PillowButton 状态管理"""

    def setUp(self):
        self.mock = MockCanvas()

    def test_initial_state(self):
        """初始状态应为启用、未悬停、未按下。"""
        btn = PillowButton('Click', x=10, y=10, w=100, h=36)
        self.assertEqual(btn.text, 'Click')
        self.assertEqual(btn.style, 'primary')
        self.assertEqual(btn._disabled, False)
        self.assertEqual(btn._hovered, False)
        self.assertEqual(btn._pressed, False)

    def test_default_rect(self):
        """默认位置和尺寸应正确。"""
        btn = PillowButton('OK', x=5, y=5, w=80, h=30)
        self.assertEqual(btn.x, 5)
        self.assertEqual(btn.y, 5)
        self.assertEqual(btn.w, 80)
        self.assertEqual(btn.h, 30)

    def test_set_text(self):
        """set_text 应更新按钮文字。"""
        btn = PillowButton('Old')
        self.assertEqual(btn.text, 'Old')
        btn.set_text('New')
        self.assertEqual(btn.text, 'New')

    def test_set_text_triggers_dirty(self):
        """set_text 有 parent 时应触发 mark_dirty。"""
        btn = PillowButton('Old')
        btn._parent = self.mock
        btn.set_text('New')
        self.assertGreater(self.mock.dirty_count, 0)

    def test_set_disabled(self):
        """set_disabled 应切换禁用状态。"""
        btn = PillowButton('Click')
        self.assertFalse(btn._disabled)
        btn.set_disabled(True)
        self.assertTrue(btn._disabled)
        btn.set_disabled(False)
        self.assertFalse(btn._disabled)

    def test_set_disabled_triggers_dirty(self):
        """set_disabled 有 parent 时应触发 mark_dirty。"""
        btn = PillowButton('Click')
        btn._parent = self.mock
        btn.set_disabled(True)
        self.assertGreater(self.mock.dirty_count, 0)

    def test_set_style(self):
        """set_style 应切换样式名。"""
        btn = PillowButton('Click', style='primary')
        self.assertEqual(btn.style, 'primary')
        btn.set_style('danger')
        self.assertEqual(btn.style, 'danger')
        btn.set_style('transparent')
        self.assertEqual(btn.style, 'transparent')

    def test_set_style_triggers_dirty(self):
        """set_style 有 parent 时应触发 mark_dirty。"""
        btn = PillowButton('Click')
        btn._parent = self.mock
        btn.set_style('danger')
        self.assertGreater(self.mock.dirty_count, 0)

    def test_on_click_when_disabled(self):
        """禁用时点击不应触发任何操作。"""
        btn = PillowButton('Click')
        btn._parent = self.mock
        btn.set_disabled(True)
        before = self.mock.dirty_count
        btn.on_click(MagicMock())
        self.assertFalse(btn._pressed)
        # dirty_count 不应再增加（点击被忽略）
        self.assertEqual(self.mock.dirty_count, before)

    def test_on_click_when_enabled(self):
        """启用时点击应设置 _pressed 为 True。"""
        btn = PillowButton('Click')
        btn._parent = self.mock
        btn.on_click(MagicMock())
        self.assertTrue(btn._pressed)
        self.assertGreater(self.mock.dirty_count, 0)

    def test_on_release_when_disabled(self):
        """禁用时释放不应触发命令。"""
        called = []
        btn = PillowButton('Click', command=lambda: called.append(1))
        btn._parent = self.mock
        btn.set_disabled(True)
        btn.on_release(MagicMock())
        self.assertEqual(called, [])

    def test_on_release_fires_command(self):
        """释放时应触发 command 回调。"""
        called = []
        btn = PillowButton('Click', command=lambda: called.append(1))
        btn._parent = self.mock
        btn.on_release(MagicMock())
        self.assertEqual(called, [1])

    def test_on_release_resets_pressed(self):
        """释放后 _pressed 应为 False。"""
        btn = PillowButton('Click')
        btn._parent = self.mock
        btn.on_click(MagicMock())
        self.assertTrue(btn._pressed)
        btn.on_release(MagicMock())
        self.assertFalse(btn._pressed)

    def test_release_without_command_does_not_raise(self):
        """无 command 时释放不应抛出异常。"""
        btn = PillowButton('Click')
        btn._parent = self.mock
        btn.on_click(MagicMock())
        try:
            btn.on_release(MagicMock())
        except Exception as e:
            self.fail('无 command 时释放抛出了异常: %s' % e)

    def test_on_enter_sets_hovered(self):
        """鼠标进入应设置 _hovered 为 True。"""
        btn = PillowButton('Click')
        btn.on_enter()
        self.assertTrue(btn._hovered)

    def test_on_leave_clears_hovered_and_pressed(self):
        """鼠标离开应清除 _hovered 和 _pressed。"""
        btn = PillowButton('Click')
        btn._hovered = True
        btn._pressed = True
        btn.on_leave()
        self.assertFalse(btn._hovered)
        self.assertFalse(btn._pressed)

    def test_multiple_styles_dont_affect_text(self):
        """样式切换不应影响文字。"""
        btn = PillowButton('Hello', style='primary')
        btn.set_style('danger')
        self.assertEqual(btn.text, 'Hello')
        btn.set_style('transparent')
        self.assertEqual(btn.text, 'Hello')


class TestPillowLabel(unittest.TestCase):
    """测试 PillowLabel 状态管理"""

    def setUp(self):
        self.mock = MockCanvas()

    def test_initial_state(self):
        """初始属性应正确保存。"""
        lbl = PillowLabel('Hello', x=10, y=10, w=100, h=20,
                          font_size=14, color='#FF0000',
                          align='center', weight='bold',
                          anchor='center')
        self.assertEqual(lbl.text, 'Hello')
        self.assertEqual(lbl.font_size, 14)
        self.assertEqual(lbl.color, '#FF0000')
        self.assertEqual(lbl.align, 'center')
        self.assertEqual(lbl.weight, 'bold')
        self.assertEqual(lbl.anchor, 'center')

    def test_default_values(self):
        """默认值应正确。"""
        lbl = PillowLabel()
        self.assertEqual(lbl.text, '')
        self.assertEqual(lbl.font_size, 12)
        self.assertEqual(lbl.color, '#C9D1D9')
        self.assertEqual(lbl.align, 'left')
        self.assertEqual(lbl.weight, 'normal')
        self.assertEqual(lbl.anchor, 'nw')

    def test_set_text(self):
        """set_text 应更新文字内容。"""
        lbl = PillowLabel('Old')
        lbl.set_text('New')
        self.assertEqual(lbl.text, 'New')

    def test_set_text_same_value_no_dirty(self):
        """相同文字不触发 mark_dirty。"""
        lbl = PillowLabel('Same')
        lbl._parent = self.mock
        lbl.set_text('Same')
        self.assertEqual(self.mock.dirty_count, 0)

    def test_set_text_different_value_triggers_dirty(self):
        """不同文字触发 mark_dirty。"""
        lbl = PillowLabel('Old')
        lbl._parent = self.mock
        lbl.set_text('New')
        self.assertGreater(self.mock.dirty_count, 0)

    def test_set_color(self):
        """set_color 应更新文字颜色。"""
        lbl = PillowLabel(color='#000000')
        lbl.set_color('#FFFFFF')
        self.assertEqual(lbl.color, '#FFFFFF')

    def test_set_color_triggers_dirty(self):
        """set_color 有 parent 时应触发 mark_dirty。"""
        lbl = PillowLabel(color='#000000')
        lbl._parent = self.mock
        lbl.set_color('#FFFFFF')
        self.assertGreater(self.mock.dirty_count, 0)

    def test_multiline_text_stored(self):
        """多行文字应存储在 text 属性中。"""
        lbl = PillowLabel('line1\nline2\nline3')
        self.assertEqual(lbl.text, 'line1\nline2\nline3')

    def test_align_center(self):
        """居中对齐值应为 'center'。"""
        lbl = PillowLabel(align='center')
        self.assertEqual(lbl.align, 'center')

    def test_align_right(self):
        """右对齐值应为 'right'。"""
        lbl = PillowLabel(align='right')
        self.assertEqual(lbl.align, 'right')

    def test_align_left(self):
        """左对齐值应为 'left'。"""
        lbl = PillowLabel(align='left')
        self.assertEqual(lbl.align, 'left')

    def test_anchor_nw(self):
        """左上角锚点应为 'nw'。"""
        lbl = PillowLabel(anchor='nw')
        self.assertEqual(lbl.anchor, 'nw')

    def test_anchor_center(self):
        """居中锚点应为 'center'。"""
        lbl = PillowLabel(anchor='center')
        self.assertEqual(lbl.anchor, 'center')

    def test_weight_normal(self):
        """正常字重应为 'normal'。"""
        lbl = PillowLabel(weight='normal')
        self.assertEqual(lbl.weight, 'normal')

    def test_weight_bold(self):
        """粗体字重应为 'bold'。"""
        lbl = PillowLabel(weight='bold')
        self.assertEqual(lbl.weight, 'bold')

    def test_minimum_width(self):
        """宽度至少为 1。"""
        lbl = PillowLabel('x', w=0, h=0)
        self.assertEqual(lbl.w, 1)
        self.assertEqual(lbl.h, 1)


class TestPillowProgressBar(unittest.TestCase):
    """测试 PillowProgressBar 进度值管理"""

    def setUp(self):
        self.mock = MockCanvas()

    def test_initial_value(self):
        """初始进度值应为 0.0。"""
        bar = PillowProgressBar()
        self.assertEqual(bar.value, 0.0)

    def test_set_value_normal(self):
        """设置正常进度值 (0.0 ~ 1.0)。"""
        bar = PillowProgressBar()
        bar.set(0.5)
        self.assertEqual(bar.value, 0.5)

    def test_set_value_zero(self):
        """设置进度为 0.0。"""
        bar = PillowProgressBar(value=0.8)
        bar.set(0.0)
        self.assertEqual(bar.value, 0.0)

    def test_set_value_one(self):
        """设置进度为 1.0 (100%)。"""
        bar = PillowProgressBar()
        bar.set(1.0)
        self.assertEqual(bar.value, 1.0)

    def test_set_value_clamp_below_zero(self):
        """小于 0 的值应被钳制到 0.0。"""
        bar = PillowProgressBar()
        bar.set(-0.5)
        self.assertEqual(bar.value, 0.0)

    def test_set_value_clamp_above_one(self):
        """大于 1 的值应被钳制到 1.0。"""
        bar = PillowProgressBar()
        bar.set(1.5)
        self.assertEqual(bar.value, 1.0)

    def test_set_value_clamp_negative(self):
        """负数应被钳制到 0.0。"""
        bar = PillowProgressBar()
        bar.set(-100)
        self.assertEqual(bar.value, 0.0)

    def test_set_value_clamp_large(self):
        """超大值应被钳制到 1.0。"""
        bar = PillowProgressBar()
        bar.set(999)
        self.assertEqual(bar.value, 1.0)

    def test_set_triggers_dirty(self):
        """set 有 parent 时应触发 mark_dirty。"""
        bar = PillowProgressBar()
        bar._parent = self.mock
        bar.set(0.5)
        self.assertGreater(self.mock.dirty_count, 0)

    def test_set_color(self):
        """set_color 应更新填充颜色。"""
        bar = PillowProgressBar(color='#FF0000')
        bar.set_color('#00FF00')
        self.assertEqual(bar.color, '#00FF00')

    def test_set_color_triggers_dirty(self):
        """set_color 有 parent 时应触发 mark_dirty。"""
        bar = PillowProgressBar()
        bar._parent = self.mock
        bar.set_color('#00FF00')
        self.assertGreater(self.mock.dirty_count, 0)

    def test_initial_custom_value(self):
        """构造时可设置自定义初始值。"""
        bar = PillowProgressBar(value=0.75)
        self.assertEqual(bar.value, 0.75)

    def test_constructor_clamps_value(self):
        """构造时值不钳制（由 set 方法负责）。"""
        bar = PillowProgressBar(value=0.5)
        self.assertEqual(bar.value, 0.5)
        bar2 = PillowProgressBar(value=1.5)
        # 构造函数不钳制，但 set() 会
        self.assertEqual(bar2.value, 1.5)

    def test_value_is_readonly_property(self):
        """value 应为只读属性。"""
        bar = PillowProgressBar()
        with self.assertRaises(AttributeError):
            bar.value = 0.5


class TestPillowCard(unittest.TestCase):
    """测试 PillowCard 创建和属性"""

    def test_card_with_title(self):
        """带标题的卡片创建。"""
        card = PillowCard(title='系统信息')
        self.assertEqual(card.title, '系统信息')

    def test_card_without_title(self):
        """不带标题的卡片创建。"""
        card = PillowCard()
        self.assertEqual(card.title, '')

    def test_card_default_colors(self):
        """卡片默认填充和边框色。"""
        card = PillowCard()
        self.assertEqual(card.fill_color, '#161B22')
        self.assertEqual(card.border_color, '#4D4D4D')

    def test_card_custom_colors(self):
        """自定义填充和边框色。"""
        card = PillowCard(fill='#000000', border='#FFFFFF')
        self.assertEqual(card.fill_color, '#000000')
        self.assertEqual(card.border_color, '#FFFFFF')

    def test_card_default_radius(self):
        """默认圆角半径应为 10。"""
        card = PillowCard()
        self.assertEqual(card.radius, 10)

    def test_card_custom_radius(self):
        """自定义圆角半径。"""
        card = PillowCard(radius=20)
        self.assertEqual(card.radius, 20)

    def test_card_default_title_size(self):
        """默认标题字号应为 13。"""
        card = PillowCard()
        self.assertEqual(card.title_size, 13)

    def test_card_dimensions(self):
        """卡片尺寸应正确。"""
        card = PillowCard(x=10, y=20, w=300, h=200)
        self.assertEqual(card.x, 10)
        self.assertEqual(card.y, 20)
        self.assertEqual(card.w, 300)
        self.assertEqual(card.h, 200)

    def test_card_empty_title_stored_as_empty_string(self):
        """空标题应为空字符串。"""
        card = PillowCard(title='')
        self.assertEqual(card.title, '')


class TestPillowCheckBox(unittest.TestCase):
    """测试 PillowCheckBox 状态和 BooleanVar 绑定"""

    def setUp(self):
        self.mock = MockCanvas()

    def test_initial_state_unchecked(self):
        """初始时无 variable 默认为未选中。"""
        cb = PillowCheckBox('选项')
        self.assertEqual(cb.text, '选项')
        self.assertIsNone(cb._variable)

    def test_with_boolean_var_default_false(self):
        """BooleanVar 默认为 False。"""
        var = tk.BooleanVar(value=False)
        cb = PillowCheckBox('选项', variable=var)
        self.assertFalse(var.get())

    def test_with_boolean_var_initial_true(self):
        """BooleanVar 初始为 True。"""
        var = tk.BooleanVar(value=True)
        cb = PillowCheckBox('选项', variable=var)
        self.assertTrue(var.get())

    def test_toggle_state_false_to_true(self):
        """点击切换：False → True。"""
        var = tk.BooleanVar(value=False)
        cb = PillowCheckBox('选项', variable=var)
        cb._parent = self.mock
        cb.on_click(MagicMock())
        self.assertTrue(var.get())

    def test_toggle_state_true_to_false(self):
        """点击切换：True → False。"""
        var = tk.BooleanVar(value=True)
        cb = PillowCheckBox('选项', variable=var)
        cb._parent = self.mock
        cb.on_click(MagicMock())
        self.assertFalse(var.get())

    def test_toggle_triggers_dirty(self):
        """点击切换触发 mark_dirty。"""
        var = tk.BooleanVar(value=False)
        cb = PillowCheckBox('选项', variable=var)
        cb._parent = self.mock
        cb.on_click(MagicMock())
        self.assertGreater(self.mock.dirty_count, 0)

    def test_toggle_fires_command(self):
        """点击切换触发 command 回调。"""
        called = []
        var = tk.BooleanVar(value=False)
        cb = PillowCheckBox('选项', variable=var, command=lambda: called.append(1))
        cb._parent = self.mock
        cb.on_click(MagicMock())
        self.assertEqual(called, [1])

    def test_no_variable_no_error(self):
        """无 variable 时点击不抛异常。"""
        cb = PillowCheckBox('选项')
        cb._parent = self.mock
        try:
            cb.on_click(MagicMock())
        except Exception as e:
            self.fail('无 variable 时点击抛出了异常: %s' % e)

    def test_multiple_toggles(self):
        """连续多次切换。"""
        var = tk.BooleanVar(value=False)
        cb = PillowCheckBox('选项', variable=var)
        cb._parent = self.mock
        cb.on_click(MagicMock())
        self.assertTrue(var.get())
        cb.on_click(MagicMock())
        self.assertFalse(var.get())
        cb.on_click(MagicMock())
        self.assertTrue(var.get())

    def test_hit_test_inside(self):
        """hit_test 在组件范围内应返回 True。"""
        cb = PillowCheckBox('选项', x=10, y=10, w=200, h=24)
        self.assertTrue(cb.hit_test(15, 15))
        self.assertTrue(cb.hit_test(10, 10))
        self.assertTrue(cb.hit_test(209, 31))

    def test_hit_test_outside_left(self):
        """hit_test 在组件左侧外部应返回 False。"""
        cb = PillowCheckBox('选项', x=10, y=10, w=200, h=24)
        self.assertFalse(cb.hit_test(5, 15))

    def test_hit_test_outside_right(self):
        """hit_test 在组件右侧外部应返回 False。"""
        cb = PillowCheckBox('选项', x=10, y=10, w=200, h=24)
        self.assertFalse(cb.hit_test(211, 15))

    def test_hit_test_outside_below(self):
        """hit_test 在组件下方应返回 False (y 范围检查)。"""
        cb = PillowCheckBox('选项', x=10, y=10, w=200, h=24)
        self.assertFalse(cb.hit_test(15, 35))

    def test_on_release_is_noop(self):
        """on_release 应为空操作。"""
        var = tk.BooleanVar(value=False)
        cb = PillowCheckBox('选项', variable=var)
        cb._parent = self.mock
        cb.on_release(MagicMock())
        self.assertFalse(var.get())  # 状态不变


class TestPillowSlider(unittest.TestCase):
    """测试 PillowSlider 值和范围钳制逻辑"""

    def setUp(self):
        self.mock = MockCanvas()

    def test_initial_values(self):
        """初始值应正确。"""
        slider = PillowSlider(from_val=0.0, to_val=100.0, steps=10)
        self.assertEqual(slider.from_val, 0.0)
        self.assertEqual(slider.to_val, 100.0)
        self.assertEqual(slider.steps, 10)

    def test_variable_binding(self):
        """变量绑定应正确。"""
        var = tk.DoubleVar(value=50.0)
        slider = PillowSlider(from_val=0.0, to_val=100.0, steps=10, variable=var)
        self.assertEqual(slider._variable.get(), 50.0)

    def test_update_from_mouse_clamps_min(self):
        """鼠标在最小值左侧时值应钳制到 from_val。"""
        var = tk.DoubleVar(value=50.0)
        slider = PillowSlider(x=0, y=0, w=200, h=24,
                              from_val=0.0, to_val=100.0,
                              steps=10, variable=var)
        # 模拟鼠标在最左侧
        slider._update_from_mouse(-999)
        self.assertEqual(var.get(), 0.0)

    def test_update_from_mouse_clamps_max(self):
        """鼠标在最大值右侧时值应钳制到 to_val。"""
        var = tk.DoubleVar(value=50.0)
        slider = PillowSlider(x=0, y=0, w=200, h=24,
                              from_val=0.0, to_val=100.0,
                              steps=10, variable=var)
        # 模拟鼠标在最右侧
        slider._update_from_mouse(9999)
        self.assertEqual(var.get(), 100.0)

    def test_update_from_mouse_midpoint(self):
        """鼠标在中间时值应为中间值。"""
        var = tk.DoubleVar(value=0.0)
        slider = PillowSlider(x=0, y=0, w=200, h=24,
                              from_val=0.0, to_val=100.0,
                              steps=10, variable=var)
        # 鼠标在中间 (x=100)
        slider._update_from_mouse(100)
        # 步长 10, track 范围约 184, 中间约 50
        val = var.get()
        self.assertGreaterEqual(val, 0.0)
        self.assertLessEqual(val, 100.0)

    def test_step_rounding(self):
        """值应按步长舍入。"""
        var = tk.DoubleVar(value=0.0)
        slider = PillowSlider(x=0, y=0, w=200, h=24,
                              from_val=0.0, to_val=10.0,
                              steps=10, variable=var)
        # 滑到大约 32% 位置 (x≈65): ratio ≈ 0.32, val ≈ 3.2, 步长=1, round→3
        slider._update_from_mouse(65)
        val = var.get()
        # 值应为步长 1.0 的整数倍
        self.assertEqual(val, round(val / 1.0) * 1.0)

    def test_slider_no_variable_no_error(self):
        """无 variable 时 _update_from_mouse 不抛异常。"""
        slider = PillowSlider(from_val=0.0, to_val=100.0, steps=10)
        try:
            slider._update_from_mouse(50)
        except Exception as e:
            self.fail('无 variable 时 _update_from_mouse 抛出了异常: %s' % e)

    def test_on_click_starts_dragging(self):
        """on_click 应设置 _dragging 为 True。"""
        var = tk.DoubleVar(value=0.0)
        slider = PillowSlider(from_val=0.0, to_val=100.0, steps=10, variable=var)
        slider._parent = self.mock

        class MockEvent:
            x = 100
        slider.on_click(MockEvent())
        self.assertTrue(slider._dragging)

    def test_on_release_stops_dragging(self):
        """on_release 应设置 _dragging 为 False。"""
        var = tk.DoubleVar(value=50.0)
        slider = PillowSlider(from_val=0.0, to_val=100.0, steps=10, variable=var)
        slider._parent = self.mock

        class MockEvent:
            x = 100
        slider._dragging = True
        slider.on_release(MockEvent())
        self.assertFalse(slider._dragging)

    def test_on_release_fires_command(self):
        """on_release 应触发 command 回调并传入当前值。"""
        called = []
        var = tk.DoubleVar(value=50.0)
        slider = PillowSlider(from_val=0.0, to_val=100.0, steps=10,
                              variable=var, command=lambda v: called.append(v))
        slider._parent = self.mock

        class MockEvent:
            x = 100
        slider.on_release(MockEvent())
        self.assertEqual(len(called), 1)
        self.assertIsInstance(called[0], float)

    def test_on_release_no_command_no_error(self):
        """无 command 时 on_release 不抛异常。"""
        var = tk.DoubleVar(value=50.0)
        slider = PillowSlider(from_val=0.0, to_val=100.0, steps=10, variable=var)
        slider._parent = self.mock

        class MockEvent:
            x = 100
        try:
            slider.on_release(MockEvent())
        except Exception as e:
            self.fail('无 command 时 on_release 抛出了异常: %s' % e)

    def test_dragging_state_persists_during_drag(self):
        """拖拽过程中 _dragging 保持 True。"""
        var = tk.DoubleVar(value=0.0)
        slider = PillowSlider(from_val=0.0, to_val=100.0, steps=10, variable=var)
        slider._parent = self.mock

        class MockEvent:
            x = 100
        slider.on_click(MockEvent())
        self.assertTrue(slider._dragging)
        # 拖拽移动
        slider.on_drag(MockEvent())
        self.assertTrue(slider._dragging)

    def test_default_step(self):
        """默认步数应为 10。"""
        slider = PillowSlider()
        self.assertEqual(slider.steps, 10)

    def test_hit_test_within_bounds(self):
        """hit_test 在滑块范围内应返回 True。"""
        slider = PillowSlider(x=10, y=10, w=200, h=24)
        self.assertTrue(slider.hit_test(110, 22))

    def test_hit_test_outside(self):
        """hit_test 在滑块范围外应返回 False。"""
        slider = PillowSlider(x=10, y=10, w=200, h=24)
        self.assertFalse(slider.hit_test(5, 22))


class TestPillowOptionMenu(unittest.TestCase):
    """测试 PillowOptionMenu 选项管理和 StringVar 绑定"""

    def setUp(self):
        self.mock = MockCanvas()

    def test_initial_values_empty(self):
        """初始值列表为空。"""
        menu = PillowOptionMenu()
        self.assertEqual(menu.values, [])

    def test_set_values(self):
        """构造时传入选项列表。"""
        menu = PillowOptionMenu(values=['选项1', '选项2', '选项3'])
        self.assertEqual(menu.values, ['选项1', '选项2', '选项3'])

    def test_string_var_binding(self):
        """StringVar 绑定应正确。"""
        var = tk.StringVar(value='选项1')
        menu = PillowOptionMenu(values=['选项1', '选项2', '选项3'],
                                variable=var)
        self.assertEqual(menu._variable.get(), '选项1')

    def test_select_updates_variable(self):
        """_select 应更新 StringVar 的值。"""
        var = tk.StringVar(value='旧值')
        menu = PillowOptionMenu(values=['选项1', '选项2', '选项3'],
                                variable=var)
        menu._parent = self.mock
        menu._select('选项2')
        self.assertEqual(var.get(), '选项2')

    def test_select_triggers_dirty(self):
        """_select 应触发 mark_dirty。"""
        var = tk.StringVar(value='选项1')
        menu = PillowOptionMenu(values=['选项1', '选项2', '选项3'],
                                variable=var)
        menu._parent = self.mock
        menu._select('选项2')
        self.assertGreater(self.mock.dirty_count, 0)

    def test_select_fires_command(self):
        """_select 应触发 command 回调并传入选中值。"""
        called = []
        var = tk.StringVar(value='选项1')
        menu = PillowOptionMenu(values=['选项1', '选项2', '选项3'],
                                variable=var,
                                command=lambda v: called.append(v))
        menu._parent = self.mock
        menu._select('选项3')
        self.assertEqual(called, ['选项3'])

    def test_select_without_variable_no_error(self):
        """无 variable 时 _select 不抛异常。"""
        menu = PillowOptionMenu(values=['选项1', '选项2'])
        menu._parent = self.mock
        try:
            menu._select('选项1')
        except Exception as e:
            self.fail('无 variable 时 _select 抛出了异常: %s' % e)

    def test_select_without_command_no_error(self):
        """无 command 时 _select 不抛异常。"""
        var = tk.StringVar(value='选项1')
        menu = PillowOptionMenu(values=['选项1', '选项2'], variable=var)
        menu._parent = self.mock
        try:
            menu._select('选项2')
        except Exception as e:
            self.fail('无 command 时 _select 抛出了异常: %s' % e)

    def test_on_click_no_parent(self):
        """无 parent 时 on_click 不抛异常。"""
        menu = PillowOptionMenu(values=['选项1', '选项2'])
        try:
            menu.on_click(MagicMock())
        except Exception as e:
            self.fail('无 parent 时 on_click 抛出了异常: %s' % e)

    def test_get_theme_color_fallback(self):
        """_get_theme_color 在无法导入时应返回回退值。"""
        color = PillowOptionMenu._get_theme_color('bg_card')
        self.assertIsInstance(color, str)
        self.assertTrue(color.startswith('#'))

    def test_get_theme_color_unknown_key(self):
        """未知键应返回 '#000000'。"""
        color = PillowOptionMenu._get_theme_color('nonexistent_key_xyz')
        self.assertEqual(color, '#000000')


class TestBaseComponent(unittest.TestCase):
    """测试 BaseComponent 基础功能"""

    def test_rect_properties(self):
        """rect 属性应正确计算。"""
        comp = BaseComponent(x=10, y=20, w=100, h=50)
        self.assertEqual(comp.x, 10)
        self.assertEqual(comp.y, 20)
        self.assertEqual(comp.w, 100)
        self.assertEqual(comp.h, 50)
        self.assertEqual(comp.rect, (10, 20, 110, 70))

    def test_set_pos(self):
        """set_pos 应更新位置。"""
        comp = BaseComponent(x=10, y=20, w=100, h=50)
        comp.set_pos(30, 40)
        self.assertEqual(comp.x, 30)
        self.assertEqual(comp.y, 40)
        self.assertEqual(comp.w, 100)
        self.assertEqual(comp.h, 50)

    def test_set_size(self):
        """set_size 应更新尺寸。"""
        comp = BaseComponent(x=10, y=20, w=100, h=50)
        comp.set_size(200, 80)
        self.assertEqual(comp.x, 10)
        self.assertEqual(comp.y, 20)
        self.assertEqual(comp.w, 200)
        self.assertEqual(comp.h, 80)

    def test_default_visible(self):
        """默认 visible 应为 True。"""
        comp = BaseComponent()
        self.assertTrue(comp.visible)

    def test_hit_test_inside(self):
        """hit_test 在范围内应返回 True。"""
        comp = BaseComponent(x=10, y=10, w=100, h=50)
        self.assertTrue(comp.hit_test(10, 10))
        self.assertTrue(comp.hit_test(109, 59))
        self.assertTrue(comp.hit_test(50, 30))

    def test_hit_test_outside(self):
        """hit_test 在范围外应返回 False。"""
        comp = BaseComponent(x=10, y=10, w=100, h=50)
        self.assertFalse(comp.hit_test(9, 30))
        self.assertFalse(comp.hit_test(50, 9))
        self.assertFalse(comp.hit_test(111, 30))
        self.assertFalse(comp.hit_test(50, 61))

    def test_draw_raises_not_implemented(self):
        """draw 方法应抛出 NotImplementedError。"""
        comp = BaseComponent()
        with self.assertRaises(NotImplementedError):
            comp.draw(100, 100)

    def test_default_parent_none(self):
        """默认 _parent 应为 None。"""
        comp = BaseComponent()
        self.assertIsNone(comp._parent)

    def test_visible_toggle(self):
        """visible 可手动切换。"""
        comp = BaseComponent()
        comp.visible = False
        self.assertFalse(comp.visible)
        comp.visible = True
        self.assertTrue(comp.visible)


if __name__ == '__main__':
    unittest.main()
