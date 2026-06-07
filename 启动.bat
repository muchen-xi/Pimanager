@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 🥧 启动 PiManager...
python -m pimanager.main
pause
