"""
测试 config.py — 配置加载/保存/合并/验证逻辑
"""
import unittest
import sys
import os
import json
import copy
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (
    _deep_merge, DEFAULT_CONFIG, CONFIG_VERSION,
    validate_config, load_config, save_config, backup_config,
    restore_config, reset_to_defaults,
)


class TestDeepMerge(unittest.TestCase):
    """测试深度合并函数"""

    def test_simple_merge(self):
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        _deep_merge(base, override)
        self.assertEqual(base["a"], 1)
        self.assertEqual(base["b"], 3)
        self.assertEqual(base["c"], 4)

    def test_nested_merge(self):
        base = {"outer": {"inner_a": 1, "inner_b": 2}}
        override = {"outer": {"inner_b": 5}}
        _deep_merge(base, override)
        self.assertEqual(base["outer"]["inner_a"], 1)
        self.assertEqual(base["outer"]["inner_b"], 5)

    def test_new_keys_added(self):
        base = {"existing": 1}
        override = {"new_key": {"nested": "value"}}
        _deep_merge(base, override)
        self.assertIn("new_key", base)
        self.assertEqual(base["new_key"]["nested"], "value")

    def test_override_to_none(self):
        base = {"key": "old"}
        override = {"key": None}
        _deep_merge(base, override)
        self.assertIsNone(base["key"])


class TestDefaultConfig(unittest.TestCase):
    """测试默认配置"""

    def test_default_config_has_version(self):
        self.assertEqual(DEFAULT_CONFIG["version"], CONFIG_VERSION)

    def test_default_config_has_required_sections(self):
        self.assertIn("connections", DEFAULT_CONFIG)
        self.assertIn("appearance", DEFAULT_CONFIG)
        self.assertIn("behavior", DEFAULT_CONFIG)

    def test_default_connection_valid(self):
        conn = DEFAULT_CONFIG["connections"][0]
        self.assertIn("host", conn)
        self.assertIn("port", conn)
        self.assertIn("username", conn)


class TestValidateConfig(unittest.TestCase):
    """测试配置验证"""

    def test_valid_config(self):
        config = copy.deepcopy(DEFAULT_CONFIG)
        errors = validate_config(config)
        self.assertEqual(errors, [])

    def test_invalid_port(self):
        config = copy.deepcopy(DEFAULT_CONFIG)
        config["connections"] = [{"host": "test", "port": 99999}]
        errors = validate_config(config)
        self.assertTrue(any("端口" in e for e in errors))

    def test_invalid_opacity(self):
        config = copy.deepcopy(DEFAULT_CONFIG)
        config["appearance"]["background_opacity"] = 5.0
        errors = validate_config(config)
        self.assertTrue(any("透明度" in e for e in errors))

    def test_invalid_refresh_interval(self):
        config = copy.deepcopy(DEFAULT_CONFIG)
        config["behavior"]["refresh_interval"] = 100
        errors = validate_config(config)
        self.assertTrue(any("刷新间隔" in e for e in errors))

    def test_empty_host(self):
        config = copy.deepcopy(DEFAULT_CONFIG)
        config["connections"] = [{"host": "", "port": 22}]
        errors = validate_config(config)
        self.assertTrue(any("主机地址" in e for e in errors))


class TestConfigBackup(unittest.TestCase):
    """测试配置备份和恢复"""

    def setUp(self):
        import config as cfg_module
        self._orig_file = cfg_module.CONFIG_FILE
        self._orig_backup = cfg_module.CONFIG_BACKUP_DIR
        # 使用临时目录
        self._tmp = tempfile.TemporaryDirectory()
        cfg_module.CONFIG_FILE = Path(self._tmp.name) / "test_config.json"
        cfg_module.CONFIG_BACKUP_DIR = Path(self._tmp.name) / "backups"

    def tearDown(self):
        import config as cfg_module
        cfg_module.CONFIG_FILE = self._orig_file
        cfg_module.CONFIG_BACKUP_DIR = self._orig_backup
        self._tmp.cleanup()

    def test_save_and_load(self):
        config = copy.deepcopy(DEFAULT_CONFIG)
        config["connections"][0]["host"] = "test.local"
        save_config(config)
        loaded = load_config()
        self.assertEqual(loaded["connections"][0]["host"], "test.local")

    def test_backup_created_on_save(self):
        config = copy.deepcopy(DEFAULT_CONFIG)
        save_config(config)
        # 再保存一次触发备份
        save_config(config)
        backups = list(Path(self._tmp.name).glob("backups/pimanager_*.json"))
        self.assertGreater(len(backups), 0)

    def test_defaults_restored_with_no_file(self):
        # 文件不存在时应返回默认配置
        loaded = load_config()  # 第一次加载已创建文件
        self.assertIn("version", loaded)
        self.assertEqual(loaded["version"], CONFIG_VERSION)


if __name__ == "__main__":
    unittest.main()
