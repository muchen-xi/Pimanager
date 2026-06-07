"""
PiManager - 轻量级树莓派 Zero W 桌面管理器
入口文件
"""
import sys
import os

# 确保项目根目录在路径中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import customtkinter as ctk
from pimanager.app import PiManagerApp


def main():
    # 外观设置
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("green")
    ctk.set_widget_scaling(1.0)

    # 启动应用
    app = PiManagerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
