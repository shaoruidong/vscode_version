@echo off
chcp 65001 >nul
echo 启动 VSCode 版本切换工具...
call conda activate vs
python main.py
pause
