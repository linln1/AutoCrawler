@echo off
echo CS论文自动化分析系统
echo ========================
echo.
echo 正在启动系统...
echo.

REM 检查配置文件是否存在
if not exist "config.yaml" (
    echo 错误：配置文件 config.yaml 不存在！
    echo.
    echo 请先复制配置模板：
    echo   copy config_template.yaml config.yaml
    echo.
    echo 然后编辑 config.yaml，填入你的实际配置信息
    echo.
    pause
    exit /b 1
)

echo 配置文件检查通过
echo.
echo 启动交互式菜单...
echo.

REM 使用uv运行系统
uv run automation_system.py interactive

echo.
echo 系统已退出
pause 