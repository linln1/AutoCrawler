#!/bin/bash

echo "CS论文自动化分析系统 (uv版本)"
echo "================================"
echo ""

# 检查uv是否可用
if ! command -v uv &> /dev/null; then
    echo "错误：未找到 uv 命令！"
    echo ""
    echo "请先安装 uv："
    echo "  pip install uv"
    echo ""
    echo "或者使用Python启动脚本："
    echo "  python start.py"
    echo ""
    read -p "按回车键退出..."
    exit 1
fi

echo "正在使用uv管理项目..."
echo ""

# 同步依赖
echo "同步依赖包..."
if ! uv sync; then
    echo "依赖同步失败！"
    read -p "按回车键退出..."
    exit 1
fi

echo "依赖同步完成"
echo ""

# 使用uv运行系统
echo "启动系统..."
uv run automation_system.py interactive

echo ""
echo "系统已退出"
read -p "按回车键退出..." 