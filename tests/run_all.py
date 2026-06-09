#!/usr/bin/env python3
"""
运行所有测试
用法: python -m tests.run_all  或  python tests/run_all.py
"""
import unittest
import sys
import os

# 确保项目根目录在路径中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.discover(
        os.path.dirname(os.path.abspath(__file__)),
        pattern="test_*.py"
    )
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # 返回退出码
    sys.exit(0 if result.wasSuccessful() else 1)
