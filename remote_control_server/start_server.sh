#!/bin/bash

# 机器狗实验远程控制服务器启动脚本

echo "=== 机器狗实验远程控制服务器 ==="
echo ""

# 检查Python是否安装
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到Python3，请先安装Python3"
    exit 1
fi

# 检查是否在正确的目录
if [ ! -f "app.py" ]; then
    echo "错误: 未找到app.py，请确保在remote_control_server目录中运行此脚本"
    exit 1
fi

# 检查依赖是否已安装
echo "检查依赖..."
python3 -c "import flask, flask_socketio" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "正在安装依赖..."
    pip3 install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "错误: 依赖安装失败"
        exit 1
    fi
fi

# 云服务器地址
CLOUD_SERVER_IP="121.43.134.209"

echo "依赖检查完成"
echo ""
echo "服务器启动信息:"
echo "- 云服务器地址: http://$CLOUD_SERVER_IP:5000"
echo "- 手机访问地址: http://$CLOUD_SERVER_IP:5000/?token=remote_control_2024"
echo "- 访问Token: remote_control_2024"
echo ""
echo "请确保:"
echo "1. 云服务器5000端口已开放"
echo "2. Electron应用已启动并能访问云服务器"
echo "3. 手机能访问云服务器（移动网络或WiFi均可）"
echo ""
echo "按Ctrl+C停止服务器"
echo ""

# 启动服务器
python3 app.py