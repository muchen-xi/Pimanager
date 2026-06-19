# -*- mode: python ; coding: utf-8 -*-
"""
PiManager PyInstaller 打包配置
构建命令: pyinstaller --clean pimanager.spec
输出: dist/PiManager/
"""
import sys
from pathlib import Path

block_cipher = None

# --- 项目根目录 ---
project_root = Path(SPECPATH)  # SPECPATH = .spec 文件所在目录

# --- Hidden imports ---
# PyInstaller 自动检测容易遗漏以下模块，显式列出

tk_hidden = [
    'tkinter', 'tkinter.ttk', 'tkinter.filedialog',
    'tkinter.messagebox', 'tkinter.scrolledtext', 'tkinter.font',
    '_tkinter',
]

ssh_hidden = [
    'paramiko', 'paramiko.transport', 'paramiko.client',
    'paramiko.agent', 'paramiko.dsskey', 'paramiko.ecdsakey',
    'paramiko.ed25519key', 'paramiko.rsakey', 'paramiko.hostkeys',
    'paramiko.message', 'paramiko.packet', 'paramiko.sftp',
    'paramiko.sftp_client', 'paramiko.sftp_handle', 'paramiko.sftp_file',
    'paramiko.sftp_attr', 'paramiko.sftp_server',
    'paramiko.buffered_pipe', 'paramiko.util',
    'nacl', 'nacl.bindings', 'nacl.bindings.crypto_sign',
    'bcrypt', 'cryptography',
    'cryptography.hazmat.primitives.ciphers',
    'cryptography.hazmat.primitives.asymmetric',
    'cryptography.hazmat.backends',
]

pil_hidden = [
    'PIL', 'PIL.Image', 'PIL.ImageTk', 'PIL.ImageDraw',
    'PIL.ImageFont', 'PIL.ImageFilter',
]

pimanager_hidden = [
    'pimanager', 'pimanager.config', 'pimanager.theme',
    'pimanager.ssh_client', 'pimanager.status_panel',
    'pimanager.file_browser', 'pimanager.terminal_page',
    'pimanager.settings_page',
    'pimanager.pillui',
    'pimanager.pillui.renderer', 'pimanager.pillui._draw_utils',
    'pimanager.pillui.button', 'pimanager.pillui.label',
    'pimanager.pillui.card', 'pimanager.pillui.checkbox',
    'pimanager.pillui.slider', 'pimanager.pillui.progress_bar',
    'pimanager.pillui.option_menu', 'pimanager.pillui.canvas_renderer',
    'pimanager.pillui.image_utils', 'pimanager.pillui.scroll_frame',
]

all_hidden = tk_hidden + ssh_hidden + pil_hidden + pimanager_hidden

# --- Data files (bundled into _MEIPASS) ---
datas = [
    (
        str(project_root / 'pimanager' / 'assets' / 'icon.ico'),
        'pimanager/assets',
    ),
]

# --- Exclusions ---
excludes = [
    'tkinter.test',
    'matplotlib', 'numpy', 'scipy', 'pandas',
    'curses', 'readline',
    'test', 'unittest', 'pytest',
    'setuptools', 'distutils', 'pip',
]

a = Analysis(
    ['main.py'],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=all_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='PiManager',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,                      # GUI 应用，无命令行窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(project_root / 'pimanager' / 'assets' / 'icon.ico'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='PiManager',
)
