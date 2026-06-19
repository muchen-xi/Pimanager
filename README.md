# PiManager — 轻量级树莓派桌面管理器

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)

一个基于 Python + tkinter + Pillow 的本地桌面 SSH 管理工具，专为树莓派 Zero W 设计。自建 [pillui](pillui/) 组件库实现纯 Pillow Canvas 渲染，v2.2.2 含 IP 漂移自动修复、流式终端、双栏文件管理等完整功能。

## 截图

> 截图待补充

## 功能

- **SSH 密钥连接** — 基于 ed25519/RSA 密钥的安全连接，支持密码回退
- **IP 漂移自动修复** — 树莓派 DHCP 更换 IP 时自动重新解析主机名并重连
- **实时状态监控** — CPU、温度、内存、磁盘、运行时间、负载，侧边栏 + 详情双视图
- **双栏文件管理器** — 远程/本地双栏，上传、下载（含进度条）、删除、重命名、新建文件夹
- **远程执行** — 右键运行 Python/Shell 脚本，结果实时返回或推送到终端
- **流式命令终端** — 多标签独立会话，流式/阻塞双模式，Ctrl+C 中断，命令历史
- **快捷命令** — 10 个常用命令一键发送
- **可自定义背景** — 支持任意图片作为背景，cover/contain/fill/tile 四种适配模式，可调透明度
- **主题切换** — 深色/浅色模式，绿色/蓝色/深蓝三色强调
- **轻量高效** — 原生桌面应用，pillui 自建组件库，Canvas 直接渲染，内存占用低

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 SSH 密钥

确保你的 SSH 密钥已配置：

```bash
# Windows 默认位置
C:\Users\<用户名>\.ssh\id_ed25519
```

如果还没有密钥，生成一个：

```bash
ssh-keygen -t ed25519 -C "pimanager"
ssh-copy-id pi@raspberrypi.local
```

### 3. 启动

**Windows 双击：**

```
启动.bat
```

**命令行：**

```bash
python -m pimanager.main
```

## 项目结构

```
pimanager/
├── main.py              # 入口文件
├── app.py               # 主应用窗口（侧边栏、导航、背景管理）
├── ssh_client.py        # SSH 客户端（paramiko 封装）
├── status_panel.py      # 系统状态监控面板
├── file_browser.py      # 远程文件管理器（双栏模式 + 远程执行）
├── terminal_page.py     # 多标签流式命令终端
├── settings_page.py     # 应用设置页（卡片式布局）
├── config.py            # 配置管理（版本迁移、验证、备份恢复）
├── theme.py             # 主题色彩系统
├── pillui/              # 自建 Pillow Canvas UI 组件库
│   ├── __init__.py
│   ├── button.py
│   ├── label.py
│   ├── card.py
│   ├── checkbox.py
│   ├── slider.py
│   ├── progress_bar.py
│   ├── option_menu.py
│   ├── scroll_frame.py
│   ├── canvas_renderer.py
│   ├── image_utils.py
│   └── _draw_utils.py
├── tests/               # 测试套件
├── docs/                # 文档
│   ├── USER_GUIDE.md
│   ├── ARCHITECTURE.md
│   ├── API.md
│   └── COMPLIANCE_REPORT.md
├── requirements.txt     # Python 依赖
├── 启动.bat             # Windows 启动脚本
└── assets/              # 资源文件
```

## 使用说明

### 连接树莓派

1. 点击左侧 **连接** 按钮
2. 首次使用点击 **连接设置** 配置主机、密钥路径
3. 勾选「自动修复IP漂移」可应对 DHCP 换 IP
4. 连接成功后状态指示灯变绿

### 系统状态

- 查看 CPU、温度、内存、磁盘实时数据
- 自动每 3 秒刷新（可在设置中调整）

### 文件管理

- 支持双栏模式（远程 / 本地）
- 上传 / 下载（含进度条）/ 运行远程脚本
- 新建文件夹 / 删除 / 重命名
- 双击目录进入，双击文件下载
- **运行**：执行 Python/Shell 脚本，结果推送到终端或弹窗

### 命令终端

- 多标签独立会话（＋ 新建终端）
- 流式 / 阻塞双模式切换
- 10 个快捷命令按钮
- 上下键浏览命令历史
- Ctrl+C 中断远程进程
- 清屏 / 复制全部

### 设置

- 主题模式（深色 / 浅色）
- 颜色主题（绿色 / 蓝色 / 深蓝）
- 自定义背景图片 + 适配模式 + 透明度调节
- 字体缩放、自动连接、刷新间隔
- IP 漂移自动检测

## 技术栈

- **Python 3.9+**
- **pillui** — 自建纯 Pillow Canvas 渲染组件库
- **tkinter** — 窗口框架
- **Paramiko** — SSH/SFTP 协议
- **Pillow** — 图层合成 + 字体渲染

## 许可证

本项目使用 [MIT License](LICENSE)。

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
