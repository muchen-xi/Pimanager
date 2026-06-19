"""
测试 TerminalSession — 命令历史导航模型
"""
import unittest
import sys
import os

# 项目根目录的父目录
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from pimanager.terminal_page import TerminalSession


class TestTerminalSessionCreation(unittest.TestCase):
    """测试会话创建"""

    def test_creation_with_name_and_index(self):
        """创建时应正确设置 name 和 index。"""
        session = TerminalSession('会话A', 0)
        self.assertEqual(session.name, '会话A')
        self.assertEqual(session.index, 0)

    def test_creation_with_arbitrary_index(self):
        """任意索引值应正确存储。"""
        session = TerminalSession('会话B', 5)
        self.assertEqual(session.name, '会话B')
        self.assertEqual(session.index, 5)

    def test_initial_history_empty(self):
        """初始历史记录应为空。"""
        session = TerminalSession('测试', 0)
        self.assertEqual(len(session.history), 0)

    def test_initial_history_index(self):
        """初始 history_index 应为 -1。"""
        session = TerminalSession('测试', 0)
        self.assertEqual(session.history_index, -1)

    def test_history_maxlen(self):
        """历史记录最大长度应为 500。"""
        session = TerminalSession('测试', 0)
        self.assertEqual(session.history.maxlen, 500)


class TestTerminalSessionHistoryAppend(unittest.TestCase):
    """测试历史记录添加"""

    def setUp(self):
        self.session = TerminalSession('测试', 0)

    def test_append_single_command(self):
        """添加单条命令。"""
        self.session.add_history('ls -la')
        self.assertEqual(len(self.session.history), 1)
        self.assertEqual(self.session.history[0], 'ls -la')

    def test_append_multiple_commands(self):
        """添加多条命令。"""
        self.session.add_history('ls')
        self.session.add_history('pwd')
        self.session.add_history('whoami')
        self.assertEqual(len(self.session.history), 3)
        self.assertEqual(self.session.history[0], 'ls')
        self.assertEqual(self.session.history[1], 'pwd')
        self.assertEqual(self.session.history[2], 'whoami')

    def test_append_empty_string(self):
        """空字符串不应被加入历史。"""
        self.session.add_history('')
        self.assertEqual(len(self.session.history), 0)

    def test_append_whitespace_only(self):
        """仅包含空白字符的字符串不应被加入历史。"""
        self.session.add_history('   ')
        self.assertEqual(len(self.session.history), 0)
        self.session.add_history('\t')
        self.assertEqual(len(self.session.history), 0)
        self.session.add_history('\n')
        self.assertEqual(len(self.session.history), 0)

    def test_append_preserves_order(self):
        """命令应按添加顺序保存。"""
        for i in range(10):
            self.session.add_history('cmd_%d' % i)
        for i in range(10):
            self.assertEqual(self.session.history[i], 'cmd_%d' % i)

    def test_append_beyond_maxlen(self):
        """超过最大长度时应丢弃最旧的命令。"""
        for i in range(600):
            self.session.add_history('cmd_%d' % i)
        self.assertEqual(len(self.session.history), 500)
        # 最旧的 100 条被丢弃，第一条应是 cmd_100
        self.assertEqual(self.session.history[0], 'cmd_100')
        self.assertEqual(self.session.history[-1], 'cmd_599')


class TestTerminalSessionHistoryNavigation(unittest.TestCase):
    """测试历史记录上下导航"""

    def setUp(self):
        self.session = TerminalSession('测试', 0)

    def test_history_up_empty(self):
        """空历史时 history_up 应返回空字符串。"""
        result = self.session.history_up()
        self.assertEqual(result, '')

    def test_history_down_empty(self):
        """空历史时 history_down 应返回空字符串。"""
        result = self.session.history_down()
        self.assertEqual(result, '')

    def test_history_up_first_time(self):
        """第一次按上键应返回最后一条命令。"""
        self.session.add_history('cmd1')
        self.session.add_history('cmd2')
        self.session.add_history('cmd3')
        result = self.session.history_up()
        self.assertEqual(result, 'cmd3')

    def test_history_up_twice(self):
        """按两次上键应返回倒数第二条命令。"""
        self.session.add_history('cmd1')
        self.session.add_history('cmd2')
        self.session.add_history('cmd3')
        self.session.history_up()     # → cmd3
        result = self.session.history_up()  # → cmd2
        self.assertEqual(result, 'cmd2')

    def test_history_up_three_times(self):
        """按三次上键应返回倒数第三条（即第一条）命令。"""
        self.session.add_history('cmd1')
        self.session.add_history('cmd2')
        self.session.add_history('cmd3')
        self.session.history_up()  # → cmd3
        self.session.history_up()  # → cmd2
        result = self.session.history_up()  # → cmd1
        self.assertEqual(result, 'cmd1')

    def test_history_up_boundary(self):
        """按上键超过历史起点后应停留在第一条。"""
        self.session.add_history('cmd1')
        self.session.add_history('cmd2')
        self.session.history_up()  # → cmd2
        self.session.history_up()  # → cmd1
        result = self.session.history_up()  # 不应再前进
        self.assertEqual(result, 'cmd1')
        # 确认索引在 0
        self.assertEqual(self.session.history_index, 0)

    def test_history_down_after_up(self):
        """按上键后按下键应返回更新的命令。"""
        self.session.add_history('cmd1')
        self.session.add_history('cmd2')
        self.session.add_history('cmd3')
        self.session.history_up()  # → cmd3
        self.session.history_up()  # → cmd2
        result = self.session.history_down()  # → cmd3
        self.assertEqual(result, 'cmd3')

    def test_history_down_to_end(self):
        """按下键到末尾应返回空字符串并重置索引。"""
        self.session.add_history('cmd1')
        self.session.add_history('cmd2')
        self.session.history_up()  # → cmd2
        result = self.session.history_down()  # → 超出范围 → ''
        self.assertEqual(result, '')
        self.assertEqual(self.session.history_index, -1)

    def test_history_down_from_start(self):
        """从未按过上键时，按下键应返回空字符串。"""
        self.session.add_history('cmd1')
        result = self.session.history_down()
        self.assertEqual(result, '')

    def test_history_up_down_full_cycle(self):
        """完整的上下导航循环测试。"""
        self.session.add_history('cmd1')
        self.session.add_history('cmd2')
        self.session.add_history('cmd3')

        # 上三次
        self.assertEqual(self.session.history_up(), 'cmd3')
        self.assertEqual(self.session.history_up(), 'cmd2')
        self.assertEqual(self.session.history_up(), 'cmd1')
        # 不能再上
        self.assertEqual(self.session.history_up(), 'cmd1')

        # 下三次回到底部
        self.assertEqual(self.session.history_down(), 'cmd2')
        self.assertEqual(self.session.history_down(), 'cmd3')
        self.assertEqual(self.session.history_down(), '')
        self.assertEqual(self.session.history_index, -1)

    def test_history_up_after_new_command(self):
        """添加新命令后上键应能访问。"""
        self.session.add_history('cmd1')
        self.session.history_up()  # → cmd1
        self.assertEqual(self.session.history_up(), 'cmd1')  # 边界
        self.session.add_history('cmd2')
        self.session.reset_history()
        self.assertEqual(self.session.history_up(), 'cmd2')
        self.assertEqual(self.session.history_up(), 'cmd1')

    def test_single_command_navigation(self):
        """只有一条命令时上下导航。"""
        self.session.add_history('only')
        self.assertEqual(self.session.history_up(), 'only')
        self.assertEqual(self.session.history_up(), 'only')  # 边界停住
        self.assertEqual(self.session.history_down(), '')
        self.assertEqual(self.session.history_index, -1)


class TestTerminalSessionHistoryReset(unittest.TestCase):
    """测试历史索引重置"""

    def setUp(self):
        self.session = TerminalSession('测试', 0)

    def test_reset_after_navigation(self):
        """导航后 reset_history 应将索引重置为 -1。"""
        self.session.add_history('cmd1')
        self.session.add_history('cmd2')
        self.session.history_up()  # history_index 变为 1
        self.assertNotEqual(self.session.history_index, -1)
        self.session.reset_history()
        self.assertEqual(self.session.history_index, -1)

    def test_reset_when_idle(self):
        """未导航时 reset 仍将索引保持为 -1。"""
        self.session.add_history('cmd1')
        self.session.reset_history()
        self.assertEqual(self.session.history_index, -1)

    def test_reset_does_not_clear_history(self):
        """reset 不应清空历史记录。"""
        self.session.add_history('cmd1')
        self.session.add_history('cmd2')
        self.session.history_up()
        self.session.reset_history()
        self.assertEqual(len(self.session.history), 2)


class TestTerminalSessionEdgeCases(unittest.TestCase):
    """测试边界情况"""

    def setUp(self):
        self.session = TerminalSession('测试', 0)

    def test_long_command(self):
        """超长命令应正常保存。"""
        long_cmd = 'echo ' + 'x' * 5000
        self.session.add_history(long_cmd)
        self.assertEqual(len(self.session.history), 1)
        self.assertEqual(self.session.history[0], long_cmd)

    def test_special_characters(self):
        """特殊字符命令应正常保存。"""
        cmd = 'grep -E "pattern|$HOME" /etc/*.conf'
        self.session.add_history(cmd)
        self.assertEqual(self.session.history[0], cmd)

    def test_unicode_command(self):
        """Unicode 命令应正常保存。"""
        cmd = 'echo "你好世界 🌍"'
        self.session.add_history(cmd)
        self.assertEqual(self.session.history[0], cmd)

    def test_multiline_command_appended(self):
        """多行命令（不含换行）应作为一个条目。"""
        cmd = 'for i in 1 2 3; do echo $i; done'
        self.session.add_history(cmd)
        self.assertEqual(len(self.session.history), 1)

    def test_rapid_navigation(self):
        """快速切换上下导航。"""
        for i in range(10):
            self.session.add_history('cmd_%d' % i)
        # 快速上→下→上
        self.session.history_up()
        self.session.history_down()
        self.session.history_up()
        self.session.history_up()
        # 10 条命令，索引现在应在 7 (倒数第3条=cmd_7)
        current = self.session.history[self.session.history_index]
        self.assertEqual(current, 'cmd_8')  # 索引 7 → cmd_8 (0-indexed)

    def test_history_up_then_add_then_up(self):
        """导航中新增命令后重置索引再上键。"""
        self.session.add_history('old1')
        self.session.add_history('old2')
        self.session.history_up()  # → old2

        self.session.add_history('new1')
        self.assertEqual(len(self.session.history), 3)
        # 新命令添加后 history_index 仍然是之前的值
        # 但 reset_history 应由外部调用

    def test_empty_session_always_returns_empty(self):
        """空会话的上下键始终返回空字符串。"""
        for _ in range(10):
            self.assertEqual(self.session.history_up(), '')
        for _ in range(10):
            self.assertEqual(self.session.history_down(), '')


if __name__ == '__main__':
    unittest.main()
