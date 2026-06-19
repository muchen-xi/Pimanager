"""
PiManager - 轻量级树莓派 Zero W 桌面管理器 (v2: tkinter + Pillow)
入口文件
"""
import os
import json

from pimanager.theme import ThemeColors
from pimanager.app import PiManagerApp


def main():
    # 从配置文件读取保存的主题
    config_path = os.path.join(os.path.dirname(__file__), 'pimanager.json')
    saved_theme = 'dark'
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                saved_theme = data.get('appearance', {}).get('theme', 'dark')
                saved_color = data.get('appearance', {}).get('color_theme', 'green')
                saved_scale = data.get('appearance', {}).get('font_scale', 1.0)
        except Exception:
            pass

    # 初始化主题
    ThemeColors.set_mode(saved_theme)
    ThemeColors.set_color_theme(saved_color)
    ThemeColors.set_font_scale(saved_scale)

    # 启动应用
    app = PiManagerApp()
    app.mainloop()


if __name__ == '__main__':
    main()
