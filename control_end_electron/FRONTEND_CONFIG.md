# 前端配置说明

## 概述
本文档说明如何配置前端应用连接到后端服务器 `118.31.58.101:8995`。

## 配置文件

### 1. 环境变量配置 (`.env`)
项目根目录的 `.env` 文件已配置为连接到您的后端服务器：

```env
TARGET_CS_HOST=118.31.58.101
TARGET_CS_PORT=8995
```

这个配置用于：
- Electron主进程的UDP通信
- 机器人控制命令传输
- 实时数据交换

### 2. 前端API配置 (`src/renderer/js/config.js`)
新创建的配置文件包含所有前端设置：

```javascript
export const CONFIG = {
    API: {
        BASE_URL: 'http://118.31.58.101:8995',
        TIMEOUT: 10000,
        ENDPOINTS: {
            PARTICIPANTS: '/api/participants',
            MAPS: '/api/maps',
            SESSIONS: '/api/sessions',
            TARGETS: '/api/targets',
            IMAGES: '/api/images',
            ROBOT: '/api/robot'
        }
    },
    WEBSOCKET: {
        URL: 'ws://118.31.58.101:8995/ws'
    }
    // ... 其他配置
};
```

### 3. API基础类更新 (`src/renderer/js/api/base.js`)
API基础类已更新为使用配置文件中的地址：

```javascript
import CONFIG from '../config.js';

// 创建默认实例，配置后端API地址
const apiInstance = new BaseAPI(CONFIG.API.BASE_URL);
apiInstance.setTimeout(CONFIG.API.TIMEOUT);
```

### 4. 常量文件更新 (`src/renderer/js/utils/constants.js`)
常量文件已更新为从配置文件导入设置：

```javascript
import CONFIG from '../config.js';

export const API_ENDPOINTS = CONFIG.API.ENDPOINTS;
export const ROBOT_COMMANDS = CONFIG.ROBOT.COMMANDS;
export const SESSION_STATUS = CONFIG.SESSION.STATUS;
export const VALIDATION_RULES = CONFIG.VALIDATION;
```

## 配置验证

### 检查配置是否正确
1. 确认 `.env` 文件中的 `TARGET_CS_HOST` 和 `TARGET_CS_PORT` 设置正确
2. 确认 `config.js` 文件中的 `API.BASE_URL` 指向正确的后端地址
3. 重启Electron应用以加载新配置

### 测试连接
1. 启动前端应用：
   ```bash
   cd control_end_electron
   npm start
   ```

2. 检查浏览器开发者工具的网络标签，确认API请求发送到正确的地址

3. 检查Electron主进程日志，确认UDP连接到正确的服务器

## 故障排除

### 常见问题
1. **API请求失败**
   - 检查后端服务器是否运行在 `118.31.58.101:8995`
   - 检查防火墙设置
   - 确认网络连接

2. **机器人控制无响应**
   - 检查 `.env` 文件中的 `TARGET_CS_HOST` 和 `TARGET_CS_PORT`
   - 检查UDP端口是否开放
   - 查看Electron主进程控制台日志

3. **WebSocket连接失败**
   - 确认后端支持WebSocket连接
   - 检查 `config.js` 中的 `WEBSOCKET.URL` 设置

### 日志检查
- Electron主进程日志：在终端中查看启动应用时的输出
- 渲染进程日志：在应用中按 F12 打开开发者工具查看控制台
- 网络请求：在开发者工具的Network标签中查看API请求

## 环境切换

### 开发环境 vs 生产环境
在 `config.js` 中可以通过修改 `ENV.CURRENT` 来切换环境：

```javascript
export const ENV = {
    DEVELOPMENT: 'development',
    PRODUCTION: 'production',
    CURRENT: 'development' // 修改这里切换环境
};
```

### 不同后端地址
如需连接到不同的后端服务器，只需修改：
1. `.env` 文件中的 `TARGET_CS_HOST` 和 `TARGET_CS_PORT`
2. `config.js` 文件中的 `API.BASE_URL` 和 `WEBSOCKET.URL`

## 注意事项

1. **端口配置**：确保前端配置的端口与后端实际运行端口一致
2. **协议选择**：HTTP vs HTTPS，WebSocket vs WebSocket Secure (WSS)
3. **跨域问题**：如果遇到CORS错误，需要在后端配置允许跨域请求
4. **网络安全**：生产环境建议使用HTTPS和WSS协议

## 更新配置后的操作

1. 重启Electron应用
2. 清除浏览器缓存（如果使用浏览器版本）
3. 检查所有API调用是否使用新的地址
4. 测试机器人控制功能
5. 验证实时数据传输

配置完成后，前端应用将连接到您的后端服务器 `118.31.58.101:8995`。
