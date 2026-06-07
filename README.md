# 🥧 PiManager - 树莓派 Zero W 轻量管理器

一个基于 Python + CustomTkinter 的本地桌面 SSH 管理工具，专为树莓派 Zero W 设计。

## ✨ 功能

- 🔌 **SSH 密钥连接** — 基于 ed25519/RSA 密钥的安全连接
- 📊 **实时状态监控** — CPU、温度、内存、磁盘、运行时间、负载
- 📁 **文件管理器** — 浏览、上传、下载、删除、重命名、新建文件夹
- ▶️ **远程执行** — 运行 Python/Shell 脚本，结果实时返回
- 💻 **多 Agent 终端** — 多标签独立会话，命令历史，快捷命令
- 🎨 **可自定义背景** — 支持任意图片作为背景，可调透明度
- 🌓 **主题切换** — 深色/浅色模式，多色主题（绿色/蓝色/深蓝）
- ⚡ **轻量高效** — 原生桌面应用，内存占用低

## 🚀 快速开始

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
ssh-copy-id chenxi@muchenxi-20081128.local
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

## 📁 项目结构

```
pimanager/
├── main.py            # 入口文件
├── app.py             # 主应用窗口（侧边栏、导航、背景管理）
├── ssh_client.py      # SSH 客户端（paramiko 封装）
├── status_panel.py    # 系统状态监控面板
├── file_browser.py    # 远程文件管理器（含远程执行）
├── terminal_page.py   # 多标签命令终端
├── settings_page.py   # 应用设置页（卡片式布局）
├── config.py          # 配置管理
├── pimanager.json     # 用户配置文件（自动生成）
├── requirements.txt   # Python 依赖
├── 启动.bat           # Windows 启动脚本
└── assets/            # 资源文件
```

## 🎯 使用说明

### 连接树莓派
1. 点击左侧 **🔌 连接** 按钮
2. 首次使用点击 **⚙️ 连接设置** 配置主机、密钥路径
3. 连接成功后状态指示灯变绿

### 系统状态
- 查看 CPU、温度、内存、磁盘实时数据
- 自动每 3 秒刷新（可在设置中调整）

### 文件管理
- 📤 上传 / 📥 下载 / ▶ 运行远程脚本
- 📁 新建文件夹 / 🗑 删除 / ✏️ 重命名
- 双击目录进入，双击文件下载
- **▶ 运行**：执行 Python/Shell 脚本，弹出结果窗口

### 命令终端
- 多标签独立会话（＋ 新建终端）
- 快捷命令按钮（10 个常用命令）
- ↑↓ 浏览命令历史
- 清屏 / 复制全部

### 设置
- 主题模式（深色/浅色）
- 颜色主题（绿色/蓝色/深蓝）
- 自定义背景图片 + 透明度调节
- 字体缩放、自动连接、刷新间隔

## 🖥️ 技术栈

- **Python 3.9+**
- **CustomTkinter** — 现代化桌面 UI
- **Paramiko** — SSH/SFTP 协议
- **Pillow** — 图片处理

## 🔧 树莓派 Zero W 配置

```bash
# 树莓派配置
Host: muchenxi-20081128.local
Port: 22
User: chenxi
Auth: ed25519 key
OS: Raspberry Pi OS (bookworm)
Kernel: 6.12.75+rpt-rpi-v6 (armv6l)
RAM: 427 MB
Disk: 29 GB
```
