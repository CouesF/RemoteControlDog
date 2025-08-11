@echo off
chcp 65001 >nul

echo === 机器狗实验远程控制服务器 ===
echo.

REM 检查Python是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到Python，请先安装Python
    pause
    exit /b 1
)

REM 检查是否在正确的目录
if not exist "app.py" (
    echo 错误: 未找到app.py，请确保在remote_control_server目录中运行此脚本
    pause
    exit /b 1
)

REM 检查依赖是否已安装
echo 检查依赖...
python -c "import flask, flask_socketio" >nul 2>&1
if errorlevel 1 (
    echo 正在安装依赖...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo 错误: 依赖安装失败
        pause
        exit /b 1
    )
)

echo 依赖检查完成
echo.

REM 云服务器地址
set CLOUD_SERVER_IP=121.43.134.209

echo 服务器启动信息:
echo - 云服务器地址: http://%CLOUD_SERVER_IP%:5000
echo - 手机访问地址: http://%CLOUD_SERVER_IP%:5000/?token=remote_control_2024
echo - 访问Token: remote_control_2024
echo.
echo 请确保:
echo 1. 云服务器5000端口已开放
echo 2. Electron应用已启动并能访问云服务器
echo 3. 手机能访问云服务器（移动网络或WiFi均可）
echo.
echo 按Ctrl+C停止服务器
echo.

REM 启动服务器
python app.py
pause