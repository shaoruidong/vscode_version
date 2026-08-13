@echo off
chcp 65001 >nul
echo ========================================
echo   打包 VSCode 版本切换工具 (PyInstaller)
echo ========================================
echo.

call conda activate vs

python -m PyInstaller build_config.spec --noconfirm --clean

echo.
if exist "dist\VSCode版本切换工具.exe" (
    echo 打包完成！产物: dist\VSCode版本切换工具.exe
) else (
    echo 打包失败，请查看上方错误信息。
)
echo.
pause
