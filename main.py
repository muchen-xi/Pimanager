"""
PiManager - 轻量级树莓派 Zero W 桌面管理器 (v3: NiceGUI + tkinter + Pillow)
入口文件
"""
from nicegui import ui
from pimanager.app import AppState, create_main_page


def main():
    # 加载配置（AppState 构造时自动完成）
    AppState.get()

    # 注册主页面
    create_main_page()

    # 启动 NiceGUI（native=True 用 pywebview 开原生桌面窗口）
    ui.run(
        title='PiManager - 树莓派管理器',
        host='127.0.0.1',
        port=8080,
        native=True,
        reload=False,
        show=True,
        window_size=(1100, 700),
        favicon='🚀',
    )


if __name__ == '__main__':
    main()
