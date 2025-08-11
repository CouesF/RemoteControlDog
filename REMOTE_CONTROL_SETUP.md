# 机器狗实验远程控制系统 - 完整设置指南

## 系统概述

本系统实现了通过手机浏览器远程控制Electron应用中"JA成功"和"JA失败"按钮的功能。

### 主要文件结构
```
RemoteControlDog/
├── remote_control_server/           # Flask WebSocket服务器
│   ├── app.py                      # 主服务器文件
│   ├── requirements.txt            # Python依赖
│   ├── start_server.sh            # Linux/Mac启动脚本
│   ├── start_server.bat           # Windows启动脚本
│   ├── README.md                  # 详细说明文档
│   └── templates/                 # HTML模板
│       ├── control.html           # 控制界面
│       └── error.html             # 错误页面
└── control_end_electron/           # Electron应用
    ├── package.json               # 已添加socket.io-client依赖
    ├── src/main/
    │   ├── index.js               # 已集成RemoteControlHandler
    │   └── remote_control_handler.js  # WebSocket客户端处理器
    ├── src/preload/
    │   └── preload.js             # 已添加远程控制API
    └── src/renderer/js/pages/
        └── experimentControl.js   # 已集成远程控制逻辑
```

## 快速启动指南

### 步骤1: 启动Flask服务器

#### 方法A: 使用启动脚本（推荐）

**Linux/Mac:**
```bash
cd remote_control_server
chmod +x start_server.sh
./start_server.sh
```

**Windows:**
```cmd
cd remote_control_server
start_server.bat
```

#### 方法B: 手动启动
```bash
cd remote_control_server
pip install -r requirements.txt
python app.py
```

### 步骤2: 启动Electron应用

```bash
cd control_end_electron
npm install  # 首次运行需要安装依赖
npm start
```

### 步骤3: 手机访问控制界面

1. 使用云服务器进行中转（无需同一网络）
2. 在手机浏览器中访问：
   ```
   http://121.43.134.209:5000/?token=remote_control_2024
   ```
   云服务器地址：`121.43.134.209:5000`

## 测试流程

### 1. 验证连接状态

**预期结果:**
- 手机界面显示"🟢 已连接"
- Electron应用右上角显示"🟢 远程控制已连接"
- 手机界面显示"Electron客户端: 1"

### 2. 进入JA指示模式

**操作步骤:**
1. 在Electron应用中选择一个JA目标
2. 点击"开始Target指示"按钮
3. 确认进入JA指示模式（页面显示"JA指示中"状态）

### 3. 测试远程控制

**JA成功测试:**
1. 在手机上点击"✅ JA成功"按钮
2. 观察Electron应用反应：
   - 执行JA成功逻辑
   - 播放成功语音（如果配置）
   - 返回导航模式
   - 目标状态更新为"完成"

**JA失败测试:**
1. 重新进入JA指示模式
2. 在手机上点击"❌ JA失败"按钮  
3. 观察Electron应用反应：
   - 执行JA失败逻辑
   - 播放失败语音（如果配置）
   - 进入下一等级或返回导航模式

### 4. 验证反馈机制

**预期行为:**
- 手机界面显示命令执行结果
- 命令执行状态实时反馈
- 连接状态实时更新

## 故障排除

### 问题1: 手机无法访问控制界面

**可能原因及解决方案:**

1. **云服务器连接问题**
   - 确认云服务器5000端口已开放
   - 检查云服务器防火墙配置
   - 尝试ping云服务器：`ping 121.43.134.209`

2. **Flask服务未启动**
   - 确认云服务器上Flask服务正在运行
   - 检查云服务器控制台输出

3. **Token错误**
   - 检查URL中token参数是否正确
   - 确认为：`token=remote_control_2024`

### 问题2: Electron应用显示"远程控制断开"

**解决步骤:**
1. 确认云服务器上的Flask服务正在运行
2. 检查本地网络是否能访问云服务器
3. 验证Electron中的云服务器地址配置是否正确
4. 检查控制台日志查看连接错误

### 问题3: 远程命令无响应

**检查项目:**
1. 确认Electron应用处于JA指示模式
2. 验证已选择有效的JA目标
3. 查看服务器和Electron控制台日志

### 问题4: 依赖安装失败

**解决方案:**
```bash
# Python环境
pip install --upgrade pip
pip install flask flask-socketio

# Node.js环境
npm install --legacy-peer-deps
```

## 配置自定义

### 修改访问Token

1. 编辑 `remote_control_server/app.py`:
   ```python
   VALID_TOKEN = "your_custom_token"
   ```

2. 编辑 `control_end_electron/src/main/remote_control_handler.js`:
   ```javascript
   token: 'your_custom_token'
   ```

### 修改云服务器地址

如需更换云服务器，需要同时修改两个地方：

1. 编辑 `control_end_electron/src/main/remote_control_handler.js`:
   ```javascript
   this.ws = io('http://your_server_ip:5000', {
   ```

2. 更新文档中的访问地址

### 修改服务器端口

1. 编辑 `remote_control_server/app.py`:
   ```python
   socketio.run(app, host='0.0.0.0', port=8080, debug=True)
   ```

2. 编辑 `control_end_electron/src/main/remote_control_handler.js`:
   ```javascript
   this.ws = io('http://localhost:8080', {
   ```

## 安全注意事项

1. **仅内部使用**: 此系统设计用于内部测试环境
2. **网络安全**: 建议在受信任的私有网络中使用
3. **Token保护**: 不要在公共场所暴露访问Token
4. **定期更新**: 定期更改访问Token

## 技术支持

如遇到问题，请检查：
1. 服务器控制台日志
2. Electron开发者工具控制台
3. 手机浏览器开发者工具

## 系统要求

**服务器端:**
- Python 3.7+
- Flask 2.3+
- Flask-SocketIO 5.3+

**客户端:**
- Node.js 16+
- Electron 28+
- 现代浏览器（支持WebSocket）

## 成功部署检查清单

- [ ] Flask服务器成功启动并显示监听地址
- [ ] Electron应用启动无错误
- [ ] 手机能够访问控制界面
- [ ] 连接状态显示正常
- [ ] JA成功命令测试通过
- [ ] JA失败命令测试通过
- [ ] 命令反馈机制正常工作
- [ ] 断线重连机制正常工作

完成以上检查后，系统即可正常使用。