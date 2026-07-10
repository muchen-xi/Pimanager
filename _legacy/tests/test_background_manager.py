"""
测试 BackgroundManager — 全局背景管理逻辑
"""
import unittest
import sys
import os
import tempfile
from unittest.mock import MagicMock, patch, Mock

from pimanager.app import BackgroundManager


class MockCanvas:
    """模拟 tk.Canvas / PageCanvas。"""

    def __init__(self, width=200, height=150):
        self._width = width
        self._height = height
        self._bg_image = None
        self._bg_color = None
        self._fit_mode = 'cover'
        self._classes = set()
        self._objects = {}
        self._called = []

    def winfo_width(self):
        return self._width

    def winfo_height(self):
        return self._height

    def delete(self, tag):
        self._called.append(('delete', tag))

    def create_image(self, x, y, **kw):
        self._objects['bg_image'] = kw
        self._called.append(('create_image', x, y))

    def tag_lower(self, tag):
        self._called.append(('tag_lower', tag))

    def set_bg_image(self, pil_image, fit_mode='cover'):
        self._bg_image = pil_image
        self._fit_mode = fit_mode
        self._called.append(('set_bg_image', pil_image is not None))

    def set_bg_color(self, color):
        self._bg_color = color
        self._called.append(('set_bg_color', color))

    def render(self):
        self._called.append('render')


class TestBackgroundManagerSingleton(unittest.TestCase):
    """测试 BackgroundManager 类级别状态（单例行为）"""

    def setUp(self):
        """每个测试前重置类级别状态。"""
        BackgroundManager._blended = None
        BackgroundManager._opacity = 0.15
        BackgroundManager._path = ''
        BackgroundManager._canvases = []
        BackgroundManager._tk_images = {}
        BackgroundManager._size_cache = {}
        BackgroundManager._fit_mode = 'cover'

    def test_initial_state(self):
        """初始状态应为空。"""
        self.assertIsNone(BackgroundManager._blended)
        self.assertEqual(BackgroundManager._opacity, 0.15)
        self.assertEqual(BackgroundManager._fit_mode, 'cover')
        self.assertEqual(BackgroundManager._path, '')
        self.assertEqual(BackgroundManager._canvases, [])
        self.assertEqual(BackgroundManager._tk_images, {})

    def test_state_is_class_level_shared(self):
        """类级别状态在所有调用间共享。"""
        BackgroundManager._opacity = 0.5
        self.assertEqual(BackgroundManager._opacity, 0.5)
        # 通过类直接访问确认
        BackgroundManager._opacity = 0.3
        self.assertEqual(BackgroundManager._opacity, 0.3)


class TestBackgroundManagerCanvas(unittest.TestCase):
    """测试 Canvas 注册和注销"""

    def setUp(self):
        BackgroundManager._blended = None
        BackgroundManager._opacity = 0.15
        BackgroundManager._path = ''
        BackgroundManager._canvases = []
        BackgroundManager._tk_images = {}
        BackgroundManager._size_cache = {}
        BackgroundManager._fit_mode = 'cover'

    def test_register_canvas(self):
        """注册一个 Canvas 应添加到列表。"""
        canvas = MockCanvas()
        BackgroundManager.register(canvas)
        self.assertIn(canvas, BackgroundManager._canvases)
        self.assertEqual(len(BackgroundManager._canvases), 1)

    def test_register_duplicate(self):
        """重复注册同一个 Canvas 不应重复添加。"""
        canvas = MockCanvas()
        BackgroundManager.register(canvas)
        BackgroundManager.register(canvas)
        self.assertEqual(len(BackgroundManager._canvases), 1)

    def test_register_multiple_canvases(self):
        """注册多个不同的 Canvas。"""
        c1 = MockCanvas()
        c2 = MockCanvas()
        c3 = MockCanvas()
        BackgroundManager.register(c1)
        BackgroundManager.register(c2)
        BackgroundManager.register(c3)
        self.assertEqual(len(BackgroundManager._canvases), 3)

    def test_unregister_canvas(self):
        """注销一个 Canvas 应从列表移除。"""
        canvas = MockCanvas()
        BackgroundManager.register(canvas)
        self.assertIn(canvas, BackgroundManager._canvases)
        BackgroundManager.unregister(canvas)
        self.assertNotIn(canvas, BackgroundManager._canvases)

    def test_unregister_nonexistent_canvas(self):
        """注销不存在的 Canvas 不应抛异常。"""
        canvas = MockCanvas()
        try:
            BackgroundManager.unregister(canvas)
        except Exception as e:
            self.fail('注销不存在的 Canvas 抛出了异常: %s' % e)

    def test_unregister_clears_tk_image(self):
        """注销时应清除对应的 tk_image。"""
        canvas = MockCanvas()
        BackgroundManager.register(canvas)
        BackgroundManager._tk_images[id(canvas)] = 'dummy_image'
        BackgroundManager.unregister(canvas)
        self.assertNotIn(id(canvas), BackgroundManager._tk_images)

    def test_register_preserves_other_state(self):
        """注册 Canvas 不应影响其他状态。"""
        canvas = MockCanvas()
        old_opacity = BackgroundManager._opacity
        BackgroundManager.register(canvas)
        self.assertEqual(BackgroundManager._opacity, old_opacity)


class TestBackgroundManagerSetBackground(unittest.TestCase):
    """测试 set_background 方法"""

    def setUp(self):
        BackgroundManager._blended = None
        BackgroundManager._opacity = 0.15
        BackgroundManager._path = ''
        BackgroundManager._canvases = []
        BackgroundManager._tk_images = {}
        BackgroundManager._size_cache = {}
        BackgroundManager._fit_mode = 'cover'

    def test_set_background_with_empty_path(self):
        """空路径应清空背景。"""
        BackgroundManager.set_background('', 0.15)
        self.assertIsNone(BackgroundManager._blended)
        self.assertEqual(BackgroundManager._path, '')

    def test_set_background_with_nonexistent_path(self):
        """不存在的文件路径应清空背景。"""
        BackgroundManager.set_background('/nonexistent/path/bg.jpg', 0.2)
        self.assertIsNone(BackgroundManager._blended)
        self.assertEqual(BackgroundManager._path, '/nonexistent/path/bg.jpg')

    @patch('PIL.Image.blend')
    @patch('PIL.Image.new')
    @patch('os.path.exists', return_value=True)
    @patch('PIL.Image.open')
    def test_set_background_with_valid_path(self, mock_open, mock_exists,
                                             mock_new, mock_blend):
        """有效路径应尝试加载背景。"""
        mock_img = MagicMock()
        mock_img.size = (640, 480)
        mock_img.mode = 'RGBA'
        mock_img.convert.return_value = mock_img
        mock_open.return_value = mock_img
        mock_new.return_value = mock_img
        mock_blend.return_value = mock_img

        BackgroundManager.set_background('/valid/path/bg.jpg', 0.2)
        self.assertEqual(BackgroundManager._path, '/valid/path/bg.jpg')
        self.assertEqual(BackgroundManager._opacity, 0.2)

    @patch('PIL.Image.blend')
    @patch('PIL.Image.new')
    @patch('os.path.exists', return_value=True)
    @patch('PIL.Image.open')
    def test_set_background_sets_opacity(self, mock_open, mock_exists,
                                          mock_new, mock_blend):
        """set_background 应更新透明度值。"""
        mock_img = MagicMock()
        mock_img.size = (640, 480)
        mock_img.mode = 'RGBA'
        mock_img.convert.return_value = mock_img
        mock_open.return_value = mock_img
        mock_new.return_value = mock_img
        mock_blend.return_value = mock_img

        BackgroundManager.set_background('/path/bg.jpg', 0.35)
        self.assertEqual(BackgroundManager._opacity, 0.35)

    @patch('PIL.Image.blend')
    @patch('PIL.Image.new')
    @patch('os.path.exists', return_value=True)
    @patch('PIL.Image.open')
    def test_set_background_calls_refresh(self, mock_open, mock_exists,
                                           mock_new, mock_blend):
        """set_background 应调用 _refresh（通过检查 tk_images 清空）。"""
        mock_img = MagicMock()
        mock_img.size = (640, 480)
        mock_img.mode = 'RGBA'
        mock_img.convert.return_value = mock_img
        mock_open.return_value = mock_img
        mock_new.return_value = mock_img
        mock_blend.return_value = mock_img

        # 预先填充一些 tk_images
        BackgroundManager._tk_images[123] = 'dummy'
        BackgroundManager.set_background('/path/bg.jpg', 0.2)
        # _refresh 前会清空 tk_images
        self.assertEqual(BackgroundManager._tk_images, {})

    def test_set_background_casts_opacity_to_float(self):
        """opacity 参数应转换为 float。"""
        BackgroundManager.set_background('', '0.25')
        self.assertEqual(BackgroundManager._opacity, 0.25)
        self.assertIsInstance(BackgroundManager._opacity, float)


class TestBackgroundManagerGetBlended(unittest.TestCase):
    """测试 get_blended 方法"""

    def setUp(self):
        BackgroundManager._blended = None
        BackgroundManager._opacity = 0.15
        BackgroundManager._path = ''
        BackgroundManager._canvases = []
        BackgroundManager._tk_images = {}
        BackgroundManager._size_cache = {}
        BackgroundManager._fit_mode = 'cover'

    def test_get_blended_none_when_empty(self):
        """无背景图时返回 None。"""
        result = BackgroundManager.get_blended()
        self.assertIsNone(result)

    def test_get_blended_returns_image(self):
        """有背景图时返回 PIL Image。"""
        mock_img = MagicMock()
        BackgroundManager._blended = mock_img
        result = BackgroundManager.get_blended()
        self.assertEqual(result, mock_img)

    @patch('pimanager.app.fit_image')
    def test_get_blended_with_size(self, mock_fit_image):
        """指定尺寸时调用 fit_image 进行适配。"""
        mock_img = MagicMock()
        mock_fit_image.return_value = mock_img
        BackgroundManager._blended = mock_img
        BackgroundManager._fit_mode = 'cover'

        result = BackgroundManager.get_blended(size=(800, 600))
        mock_fit_image.assert_called_once_with(mock_img, 800, 600, 'cover')
        self.assertEqual(result, mock_img)

    def test_get_blended_without_size(self):
        """不指定尺寸时返回原始图片。"""
        mock_img = MagicMock()
        BackgroundManager._blended = mock_img

        result = BackgroundManager.get_blended()
        self.assertEqual(result, mock_img)
        mock_img.resize.assert_not_called()


class TestBackgroundManagerClear(unittest.TestCase):
    """测试 clear 方法"""

    def setUp(self):
        BackgroundManager._blended = None
        BackgroundManager._opacity = 0.15
        BackgroundManager._path = ''
        BackgroundManager._canvases = []
        BackgroundManager._tk_images = {}
        BackgroundManager._size_cache = {}
        BackgroundManager._fit_mode = 'cover'

    def test_clear_resets_state(self):
        """clear 应重置所有背景状态。"""
        mock_img = MagicMock()
        BackgroundManager._blended = mock_img
        BackgroundManager._path = '/some/path.jpg'
        BackgroundManager._tk_images[1] = 'dummy'

        BackgroundManager.clear()
        self.assertIsNone(BackgroundManager._blended)
        self.assertEqual(BackgroundManager._path, '')
        self.assertEqual(BackgroundManager._tk_images, {})

    def test_clear_with_canvases_calls_refresh(self):
        """clear 有 Canvas 时应触发 _refresh。"""
        canvas = MockCanvas()
        canvas.set_bg_color = MagicMock()
        canvas.render = MagicMock()
        BackgroundManager.register(canvas)

        BackgroundManager.clear()
        # _refresh 应被调用（通过 canvas 的方法验证）
        canvas.set_bg_color.assert_called()
        canvas.render.assert_called()


class TestBackgroundManagerOpacityRange(unittest.TestCase):
    """测试透明度范围验证"""

    def setUp(self):
        BackgroundManager._blended = None
        BackgroundManager._opacity = 0.15
        BackgroundManager._path = ''
        BackgroundManager._canvases = []
        BackgroundManager._tk_images = {}
        BackgroundManager._size_cache = {}
        BackgroundManager._fit_mode = 'cover'

    def test_opacity_zero(self):
        """透明度为 0.0 应有效。"""
        BackgroundManager.set_background('', 0.0)
        self.assertEqual(BackgroundManager._opacity, 0.0)

    def test_opacity_one(self):
        """透明度为 1.0 应有效。"""
        BackgroundManager.set_background('', 1.0)
        self.assertEqual(BackgroundManager._opacity, 1.0)

    def test_opacity_half(self):
        """透明度为 0.5 应有效。"""
        BackgroundManager.set_background('', 0.5)
        self.assertEqual(BackgroundManager._opacity, 0.5)

    @patch('PIL.Image.blend')
    @patch('PIL.Image.new')
    @patch('os.path.exists', return_value=True)
    @patch('PIL.Image.open')
    def test_opacity_negative_with_image(self, mock_open, mock_exists,
                                          mock_new, mock_blend):
        """负透明度值存储但不影响 set_background 调用。"""
        mock_img = MagicMock()
        mock_img.size = (640, 480)
        mock_img.mode = 'RGBA'
        mock_img.convert.return_value = mock_img
        mock_open.return_value = mock_img
        mock_new.return_value = mock_img
        mock_blend.return_value = mock_img

        BackgroundManager.set_background('/path/bg.jpg', -0.5)
        self.assertEqual(BackgroundManager._opacity, -0.5)


class TestBackgroundManagerRefresh(unittest.TestCase):
    """测试 _refresh 方法"""

    def setUp(self):
        BackgroundManager._blended = None
        BackgroundManager._opacity = 0.15
        BackgroundManager._path = ''
        BackgroundManager._canvases = []
        BackgroundManager._tk_images = {}
        BackgroundManager._size_cache = {}
        BackgroundManager._fit_mode = 'cover'

    def test_refresh_empty_canvases_no_error(self):
        """无 Canvas 时 _refresh 不抛异常。"""
        try:
            BackgroundManager._refresh()
        except Exception as e:
            self.fail('空 Canvas 列表 _refresh 抛出了异常: %s' % e)

    def test_refresh_pagecanvas_with_bg_image(self):
        """有背景图时 PageCanvas 应收到 set_bg_image 调用（含 fit_mode）。"""
        mock_img = MagicMock()
        BackgroundManager._blended = mock_img
        BackgroundManager._fit_mode = 'cover'

        canvas = MockCanvas()
        canvas.set_bg_image = MagicMock()
        canvas.render = MagicMock()
        BackgroundManager.register(canvas)

        BackgroundManager._refresh()
        canvas.set_bg_image.assert_called_once_with(mock_img, 'cover')
        canvas.render.assert_called_once()

    def test_refresh_pagecanvas_without_bg_image(self):
        """无背景图时 PageCanvas 应收到 set_bg_color 调用。"""
        canvas = MockCanvas()
        canvas.set_bg_color = MagicMock()
        canvas.render = MagicMock()
        BackgroundManager.register(canvas)

        BackgroundManager._refresh()
        canvas.set_bg_color.assert_called()
        canvas.render.assert_called_once()

    def test_refresh_tk_canvas_no_image(self):
        """原始 tk.Canvas 无背景图时应仅删除旧图。"""
        # 构造一个无 set_bg_image 的 Canvas 模拟原始 tk.Canvas
        canvas = MagicMock()
        canvas.winfo_width.return_value = 200
        canvas.winfo_height.return_value = 150
        # 不设置 set_bg_image，模拟原始 tk.Canvas 无此方法
        del canvas.set_bg_image
        BackgroundManager.register(canvas)

        BackgroundManager._refresh()
        canvas.delete.assert_called_with('bg_image')

    def test_refresh_handles_exception_per_canvas(self):
        """单个 Canvas 异常不应影响其他 Canvas。"""
        bad = MockCanvas()
        bad.set_bg_image = MagicMock(side_effect=Exception('模拟故障'))
        bad.render = MagicMock()

        good = MockCanvas()
        good.set_bg_color = MagicMock()
        good.render = MagicMock()

        mock_img = MagicMock()
        BackgroundManager._blended = mock_img
        BackgroundManager.register(bad)
        BackgroundManager.register(good)

        # 不应抛出异常
        try:
            BackgroundManager._refresh()
        except Exception as e:
            self.fail('_refresh 在单个 Canvas 异常时抛出了异常: %s' % e)

        # good canvas 应该正常刷新
        good.render.assert_called()


if __name__ == '__main__':
    unittest.main()
