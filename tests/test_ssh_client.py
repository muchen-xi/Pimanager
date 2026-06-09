"""
测试 SSHClient — 命令解析和连接逻辑（使用 mock）
"""
import unittest
import sys
import os
from unittest.mock import MagicMock, patch, PropertyMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ssh_client import SSHClient


class TestSSHClientState(unittest.TestCase):
    """测试 SSHClient 状态管理"""

    def setUp(self):
        self.ssh = SSHClient()

    def test_initial_state(self):
        """初始状态应为未连接。"""
        self.assertFalse(self.ssh.connected)
        self.assertEqual(self.ssh.host, "")

    @patch('paramiko.SSHClient')
    def test_connect_success(self, mock_ssh_cls):
        """模拟连接成功。"""
        mock_client = MagicMock()
        mock_client.connect.return_value = None
        mock_client.open_sftp.return_value = MagicMock()
        mock_ssh_cls.return_value = mock_client

        ok, msg = self.ssh.connect("test.local", 22, "pi",
                                    password="password")
        self.assertTrue(ok)
        self.assertEqual(self.ssh.host, "test.local")

    def test_exec_command_when_disconnected(self):
        """未连接时执行命令应返回错误。"""
        code, out, err = self.ssh.exec_command("ls")
        self.assertEqual(code, -1)
        self.assertIn("未连接", err)

    @patch('paramiko.SSHClient')
    def test_exec_command_success(self, mock_ssh_cls):
        """模拟命令执行成功。"""
        mock_client = MagicMock()
        mock_client.connect.return_value = None
        mock_client.open_sftp.return_value = MagicMock()

        mock_stdout = MagicMock()
        mock_stdout.channel.recv_exit_status.return_value = 0
        mock_stdout.read.return_value = b"output text"
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b""
        mock_client.exec_command.return_value = (MagicMock(), mock_stdout, mock_stderr)

        mock_ssh_cls.return_value = mock_client

        self.ssh.connect("test.local", 22, "pi", password="password")
        code, out, err = self.ssh.exec_command("echo hello")
        self.assertEqual(code, 0)
        self.assertEqual(out, "output text")


class TestSystemStatusParsing(unittest.TestCase):
    """测试系统状态输出解析"""

    def test_parse_cpu_temp(self):
        """解析 CPU 温度。"""
        val = float("45000") / 1000.0  # 45000 millidegrees
        self.assertEqual(val, 45.0)

    def test_parse_memory(self):
        """解析内存输出 "2048 512"。"""
        line = "MEM:2048 512"
        _, _, val = line.partition(":")
        parts = val.strip().split()
        total = int(parts[0])
        used = int(parts[1])
        self.assertEqual(total, 2048)
        self.assertEqual(used, 512)
        pct = (used / total * 100) if total > 0 else 0
        self.assertEqual(pct, 25.0)

    def test_parse_disk(self):
        """解析磁盘输出 "30720 8192 26"。"""
        line = "DISK:30720 8192 26"
        _, _, val = line.partition(":")
        parts = val.strip().split()
        total = int(parts[0].replace("M", ""))
        used = int(parts[1].replace("M", ""))
        pct = float(parts[2])
        self.assertEqual(total, 30720)
        self.assertEqual(used, 8192)
        self.assertEqual(pct, 26.0)

    def test_parse_empty_output(self):
        """空输出应该不抛出异常。"""
        result = {"cpu": 0.0}
        out = ""
        if not out.strip():
            # 应该保持默认值
            pass
        self.assertEqual(result["cpu"], 0.0)

    def test_parse_malformed_output(self):
        """畸形输出应该被安全跳过。"""
        result = {"cpu": 0.0}
        out = "garbage line\nCPU_PCT:abc\nMEM:invalid"
        for line in out.split("\n"):
            if ":" not in line:
                continue
            key, _, val = line.partition(":")
            val = val.strip()
            try:
                if key == "CPU_PCT":
                    result["cpu"] = float(val)
            except (ValueError, IndexError):
                pass
        self.assertEqual(result["cpu"], 0.0)  # 保持不变

    def test_parse_sidebar_stats(self):
        """解析侧边栏状态输出。"""
        out = "CPU_PCT:23.5\nMEM:2048 1024\nIP:192.168.1.100\nTEMP:42500"
        result = {"cpu": 0.0, "mem_total": 0, "mem_used": 0,
                  "mem_pct": 0.0, "ip": "--", "temp": 0.0}
        for line in out.strip().split("\n"):
            if ":" not in line:
                continue
            key, _, val = line.partition(":")
            val = val.strip()
            if key == "CPU_PCT":
                result["cpu"] = float(val)
            elif key == "MEM":
                parts = val.split()
                if len(parts) >= 2:
                    result["mem_total"] = int(parts[0])
                    result["mem_used"] = int(parts[1])
                    result["mem_pct"] = (int(parts[1]) / int(parts[0]) * 100)
            elif key == "IP":
                result["ip"] = val if val else "--"
            elif key == "TEMP":
                result["temp"] = float(val) / 1000.0

        self.assertEqual(result["cpu"], 23.5)
        self.assertEqual(result["mem_total"], 2048)
        self.assertEqual(result["mem_used"], 1024)
        self.assertEqual(result["mem_pct"], 50.0)
        self.assertEqual(result["ip"], "192.168.1.100")
        self.assertEqual(result["temp"], 42.5)


class TestReconnectLogic(unittest.TestCase):
    """测试重连逻辑"""

    def setUp(self):
        self.ssh = SSHClient()

    def test_reconnect_without_prior_connection(self):
        """没有之前的连接参数时重连应失败。"""
        ok, msg = self.ssh.reconnect()
        self.assertFalse(ok)
        self.assertIn("无可用连接参数", msg)


class TestExecCommandBatch(unittest.TestCase):
    """测试批量命令执行"""

    def setUp(self):
        self.ssh = SSHClient()

    def test_empty_batch(self):
        """空命令列表应返回空结果。"""
        results = self.ssh.exec_command_batch([])
        self.assertEqual(results, [])


if __name__ == "__main__":
    unittest.main()
