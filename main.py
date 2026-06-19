"""
PiManager - 轻量级树莓派 Zero W 桌面管理器 (v2: tkinter + Pillow)
入口文件
"""
from pimanager.theme import ThemeColors
from pimanager.app import PiManagerApp
from pimanager.config import load_config


def main():
    # 统一通过 config 模块读取配置（支持 frozen/开发两种模式）
    config = load_config()
    appearance = config.get('appearance', {})
    saved_theme = appearance.get('theme', 'dark')
    saved_color = appearance.get('color_theme', 'green')
    saved_scale = appearance.get('font_scale', 1.0)

    # 初始化主题
    ThemeColors.set_mode(saved_theme)
    ThemeColors.set_color_theme(saved_color)
    ThemeColors.set_font_scale(saved_scale)

    # 启动应用
    app = PiManagerApp()
    app.mainloop()


if __name__ == '__main__':
    main()
