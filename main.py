"""
PiManager - 轻量级树莓派 Zero W 桌面管理器 (v2: tkinter + Pillow)
入口文件
"""
import sys
import os

# 确保项目根目录在路径中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pimanager.theme import ThemeColors
from pimanager.app import PiManagerApp


def main():
    # 初始化主题
    ThemeColors.set_mode("dark")
    ThemeColors.set_font_scale(1.0)

    # 启动应用
    app = PiManagerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
