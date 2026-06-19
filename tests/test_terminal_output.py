"""
测试 CanvasTerminalOutput — 文本缓冲和滚动逻辑
纯逻辑测试，不需要 GUI 环境
"""
import unittest
import sys
import os

# 添加项目根目录
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestTerminalLineBuffer(unittest.TestCase):
    """测试终端行缓冲区的逻辑（不涉及 Tkinter）"""

    def setUp(self):
        """模拟 CanvasTerminalOutput 核心逻辑。"""
        self._lines = []
        self._visible_start = 0
        self._line_height = 18
        self._pad_y = 8
        self._auto_scroll = True

    def _insert(self, text, tag=None):
        color = '#FF6B6B' if tag == 'stderr' else '#C9D1D9'
        for line in text.split('\n'):
            self._lines.append((line, color))

    def _delete(self):
        self._lines.clear()
        self._visible_start = 0
        self._auto_scroll = True

    def _scroll(self, delta, ch=400):
        max_visible = max(1, (ch - self._pad_y * 2) // self._line_height)
        total = len(self._lines)
        max_start = max(0, total - max_visible)
        self._visible_start = max(0, min(max_start, self._visible_start + delta))
        if delta < 0 and self._visible_start < max_start:
            self._auto_scroll = False
        if self._visible_start >= max_start:
            self._auto_scroll = True

    def test_insert_lines(self):
        """插入文本应该正确存储到缓冲区。"""
        self._insert('hello world')
        self.assertEqual(len(self._lines), 1)
        self.assertEqual(self._lines[0][0], 'hello world')
        self.assertEqual(self._lines[0][1], '#C9D1D9')

    def test_insert_multiline(self):
        """多行插入应该分割为多个条目。"""
        self._insert('line1\nline2\nline3')
        self.assertEqual(len(self._lines), 3)
        self.assertEqual(self._lines[0][0], 'line1')
        self.assertEqual(self._lines[1][0], 'line2')
        self.assertEqual(self._lines[2][0], 'line3')

    def test_insert_stderr(self):
        """stderr 文本应该用红色标记。"""
        self._insert('error message', tag='stderr')
        self.assertEqual(self._lines[0][1], '#FF6B6B')

    def test_delete_clears_buffer(self):
        """删除应该清空缓冲区并重置状态。"""
        self._insert('some text')
        self._delete()
        self.assertEqual(len(self._lines), 0)
        self.assertEqual(self._visible_start, 0)
        self.assertTrue(self._auto_scroll)

    def test_scroll_down(self):
        """向下滚动时 visible_start 应增加。"""
        for i in range(100):
            self._insert(f'line {i}')
        old_start = self._visible_start
        self._scroll(5)
        self.assertGreater(self._visible_start, old_start)

    def test_scroll_up(self):
        """向上滚动时 visible_start 应减少且 auto_scroll 应为 False。"""
        for i in range(100):
            self._insert(f'line {i}')
        # 先滚到底部
        self._scroll(9999)
        self.assertTrue(self._auto_scroll)
        # 向上滚
        self._scroll(-5)
        self.assertFalse(self._auto_scroll)

    def test_scroll_boundary_top(self):
        """滚动不能超过顶部。"""
        for i in range(50):
            self._insert(f'line {i}')
        self._scroll(-9999)
        self.assertEqual(self._visible_start, 0)

    def test_scroll_boundary_bottom(self):
        """滚动不能超过底部。"""
        for i in range(50):
            self._insert(f'line {i}')
        self._scroll(9999)
        ch = 400
        max_visible = max(1, (ch - self._pad_y * 2) // self._line_height)
        total = len(self._lines)
        expected = max(0, total - max_visible)
        self.assertEqual(self._visible_start, expected)

    def test_auto_scroll_resume(self):
        """滚到底部后 auto_scroll 应该恢复为 True。"""
        for i in range(100):
            self._insert(f'line {i}')
        self._scroll(-10)
        self.assertFalse(self._auto_scroll)
        # 滚到底部
        self._scroll(9999)
        self.assertTrue(self._auto_scroll)

    def test_empty_buffer_visible_start(self):
        """空缓冲区 visible_start 应为 0。"""
        self._delete()
        self.assertEqual(self._visible_start, 0)

    def test_single_line_visible(self):
        """单行文本时 visible_start 应为 0。"""
        self._insert('only line')
        ch = 400
        max_visible = max(1, (ch - self._pad_y * 2) // self._line_height)
        total = len(self._lines)
        self.assertEqual(total, 1)
        # 只有 1 行，max_start = max(0, 1 - max_visible) = 0
        max_start = max(0, total - max_visible)
        self.assertEqual(max_start, 0)


class TestScrollEdgeCases(unittest.TestCase):
    """滚动边界条件测试"""

    def setUp(self):
        self._lines = []
        self._visible_start = 0
        self._line_height = 18
        self._pad_y = 8
        self._auto_scroll = True

    def _insert(self, text):
        for line in text.split('\n'):
            self._lines.append((line, '#C9D1D9'))

    def _scroll(self, delta, ch=200):
        max_visible = max(1, (ch - self._pad_y * 2) // self._line_height)
        total = len(self._lines)
        max_start = max(0, total - max_visible)
        self._visible_start = max(0, min(max_start, self._visible_start + delta))
        if delta < 0 and self._visible_start < max_start:
            self._auto_scroll = False
        if self._visible_start >= max_start:
            self._auto_scroll = True

    def test_scroll_when_fewer_lines_than_visible(self):
        """文本行数少于可见区域时，visible_start 始终为 0。"""
        for i in range(5):  # 只有 5 行
            self._insert(f'line {i}')
        self._scroll(10)
        self.assertEqual(self._visible_start, 0)
        self._scroll(-10)
        self.assertEqual(self._visible_start, 0)

    def test_very_long_lines_dont_break(self):
        """超长文本行不应该导致逻辑错误。"""
        long_line = 'x' * 10000
        self._insert(long_line)
        self._scroll(1)
        self.assertEqual(self._visible_start, 0)

    def test_many_lines(self):
        """大量行（>1000）的边界计算。"""
        for i in range(2000):
            self._insert(f'line {i}')
        # 滚到中间
        self._scroll(500)
        self.assertGreater(self._visible_start, 0)
        # 滚到底部
        self._scroll(2000)
        ch = 200
        max_visible = max(1, (ch - self._pad_y * 2) // self._line_height)
        total = len(self._lines)
        self.assertEqual(self._visible_start, max(0, total - max_visible))


if __name__ == '__main__':
    unittest.main()
