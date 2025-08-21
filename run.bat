@echo off
chcp 65001 > nul
echo CS论文自动化分析系统 (uv版本)
echo ================================
echo.

REM 检查uv是否可用
where uv >nul 2>nul
if %errorlevel% neq 0 (
    echo 错误：未找到 uv 命令！
    echo.
    echo 请先安装 uv：
    echo   pip install uv
    echo.
    echo 或者使用Python启动脚本：
    echo   python start.py
    echo.
    pause
    exit /b 1
)

echo 正在使用uv管理项目...
echo.

REM 同步依赖
echo 同步依赖包...
uv sync
if %errorlevel% neq 0 (
    echo 依赖同步失败！
    pause
    exit /b 1
)

echo 依赖同步完成
echo.

REM 使用uv运行系统
echo 启动系统...
uv run automation_system.py interactive

echo.
echo 系统已退出
pause 