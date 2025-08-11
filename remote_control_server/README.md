# 机器狗实验远程控制系统

## 系统概述

这是一个简单的远程控制系统，允许通过手机浏览器远程控制Electron应用中的"JA成功"和"JA失败"按钮。

### 架构图
```
手机浏览器 <--> Flask WebSocket服务器 <--> Electron应用
```

### 组件说明
- **Flask WebSocket服务器**: 中继服务器，处理消息转发和简单的Token验证
- **网页控制界面**: 手机端控制界面，包含两个控制按钮
- **Electron WebSocket客户端**: 接收远程命令并模拟按钮点击

## 快速开始

### 1. 安装依赖

```bash
# 进入服务器目录
cd remote_control_server

# 安装Python依赖
pip install -r requirements.txt
```

### 2. 启动Flask服务器

```bash
python app.py
```

服务器将在 `http://0.0.0.0:5000` 启动

### 3. 启动Electron应用

```bash
# 进入Electron目录
cd ../control_end_electron

# 安装依赖（首次运行）
npm install

# 启动应用
npm start
```

### 4. 手机访问控制界面

在手机浏览器中访问：
```
http://121.43.134.209:5000/?token=remote_control_2024
```

云服务器地址已配置为：`121.43.134.209`

## 使用步骤

### 1. 验证连接状态
- 打开手机控制界面，确认显示"🟢 已连接"
- 查看Electron应用右上角的远程控制状态指示器

### 2. 进入JA指示模式
- 在Electron应用中选择一个JA目标
- 点击"开始Target指示"进入JA指示模式

### 3. 远程控制
- 在手机上点击"JA成功"或"JA失败"按钮
- 观察Electron应用的反应和状态变化

## 配置说明

### 访问Token
默认Token: `remote_control_2024`

如需修改，请同时更改：
- `remote_control_server/app.py` 中的 `VALID_TOKEN`
- `control_end_electron/src/main/remote_control_handler.js` 中的 `token`

### 服务器地址
默认: `localhost:5000`

当前配置为云服务器 `121.43.134.209:5000`

如需修改，请同时更改：
- `remote_control_server/app.py` 中的端口设置
- `control_end_electron/src/main/remote_control_handler.js` 中的服务器地址

## 故障排除

### 1. 手机无法访问控制界面
- 确认云服务器已启动
- 确认云服务器5000端口已开放
- 检查云服务器防火墙设置
- 验证Token是否正确

### 2. Electron应用显示"远程控制断开"
- 确认云服务器上的Flask服务正在运行
- 检查Electron端的云服务器地址配置
- 确认网络能访问云服务器
- 查看Electron控制台日志

### 3. 远程命令无响应
- 确认Electron应用处于JA指示模式
- 检查选择的JA目标是否有效
- 查看服务器和Electron日志

### 4. 认证失败
- 验证Token是否正确
- 确认URL中包含正确的token参数

## 日志查看

### Flask服务器日志
控制台输出包含连接状态和命令处理信息

### Electron应用日志
打开开发者工具查看控制台日志

## 安全注意事项

1. 此系统使用简单的Token验证，适用于实验环境
2. 云服务器已配置公网访问，请妥善保管Token
3. 建议定期更换访问Token
4. 仅供研究实验使用

## 技术栈

- **后端**: Python Flask + Flask-SocketIO
- **前端**: HTML5 + CSS3 + JavaScript + Socket.IO Client
- **桌面端**: Electron + Node.js + Socket.IO Client

## 许可证

此项目仅供内部研究使用。