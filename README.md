# WOZ机器人辅助训练系统

这是一个基于Wizard-of-Oz方法的机器人辅助训练系统，用于自闭症儿童的社交技能训练。系统包含前端控制界面和后端API服务。

## 系统架构

```
RemoteControlDog/
├── robot_dog_python/           # 机器狗控制和后端系统
│   ├── woz_system_backend/     # WOZ系统后端 (FastAPI)
│   ├── seperated_process/      # 机器狗控制模块
│   └── start_woz_backend.py    # 后端启动脚本
├── control_end_electron/       # 前端控制界面 (Electron)
└── cloud_server_python/        # 云端服务器
```

## 功能特性

### 后端系统 (FastAPI)
- **被试管理**: 创建、编辑、删除被试者信息
- **地图管理**: 管理实验环境地图和目标点
- **会话控制**: 实验会话的创建和状态管理
- **机器人控制**: 通过DDS与机器狗通信
- **文件管理**: 图片上传和静态文件服务
- **数据存储**: SQLite数据库存储所有数据

### 前端界面 (Electron)
- **被试管理页面**: 管理被试者信息和图片
- **地图管理页面**: 配置实验环境和目标点
- **实验控制页面**: 实时控制实验进程
- **结果查看页面**: 查看实验数据和结果
- **机器人控制**: 实时控制机器狗动作

## 快速开始

### 1. 安装依赖

#### 后端依赖
```bash
cd robot_dog_python
pip install -r requirements.txt
```

#### 前端依赖
```bash
cd control_end_electron
npm install
```

### 2. 启动后端服务

```bash
cd robot_dog_python
python start_woz_backend.py
```

后端服务将在 `http://localhost:8000` 启动
- API文档: `http://localhost:8000/docs`
- 健康检查: `http://localhost:8000/health`

### 3. 启动前端应用

```bash
cd control_end_electron
npm start
```

## API文档

### 被试管理 API

- `GET /api/participants` - 获取所有被试者
- `POST /api/participants` - 创建新被试者
- `GET /api/participants/{id}` - 获取指定被试者
- `PUT /api/participants/{id}` - 更新被试者信息
- `DELETE /api/participants/{id}` - 删除被试者
- `POST /api/participants/{id}/images` - 上传被试者图片
- `GET /api/participants/{id}/images` - 获取被试者图片列表

### 地图管理 API

- `GET /api/maps` - 获取所有地图
- `POST /api/maps` - 创建新地图
- `PUT /api/maps/{id}` - 更新地图信息
- `DELETE /api/maps/{id}` - 删除地图
- `GET /api/maps/{id}/targets` - 获取地图目标点

### 机器人控制 API

- `GET /api/robot/status` - 获取机器人状态
- `POST /api/robot/commands` - 发送机器人控制命令

## 数据库结构

系统使用SQLite数据库，包含以下主要表：

- `participants` - 被试者信息
- `participant_images` - 被试者图片
- `maps` - 地图信息
- `ja_targets` - RJA目标点
- `sessions` - 实验会话
- `instructions` - 指令记录
- `prompt_attempts` - 提示尝试记录
- `event_logs` - 事件日志

## 配置说明

### 后端配置 (`robot_dog_python/woz_system_backend/config.py`)

```python
# API配置
API_HOST = "0.0.0.0"
API_PORT = 8000

# 数据库配置
DATABASE_PATH = PROJECT_ROOT / "woz_system.db"

# 文件上传配置
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp"}
```

### 前端配置 (`control_end_electron/src/renderer/js/api/base.js`)

```javascript
// 后端API地址
const apiInstance = new BaseAPI('http://localhost:8000');
```

## 开发指南

### 后端开发

1. **添加新的API端点**: 在 `api_handlers.py` 中添加处理器类和方法
2. **数据库操作**: 使用 `database.py` 中的Database类
3. **文件处理**: 使用 `file_utils.py` 中的FileHandler类
4. **机器狗通信**: 通过 `dds_bridge.py` 与现有系统集成

### 前端开发

1. **添加新页面**: 在 `src/renderer/js/pages/` 目录下创建新的页面类
2. **API调用**: 使用 `src/renderer/js/api/` 目录下的API类
3. **组件开发**: 在 `src/renderer/js/components/` 目录下创建可复用组件
4. **样式修改**: 编辑 `src/renderer/assets/css/` 目录下的CSS文件

## 部署说明

### 生产环境部署

1. **后端部署**:
   ```bash
   # 使用gunicorn部署
   pip install gunicorn
   gunicorn -w 4 -k uvicorn.workers.UvicornWorker robot_dog_python.woz_system_backend.main:app
   ```

2. **前端打包**:
   ```bash
   cd control_end_electron
   npm run build
   npm run dist
   ```

### Docker部署

```dockerfile
# Dockerfile示例
FROM python:3.9-slim

WORKDIR /app
COPY robot_dog_python/ ./robot_dog_python/
COPY requirements.txt .

RUN pip install -r requirements.txt

EXPOSE 8000
CMD ["python", "robot_dog_python/start_woz_backend.py"]
```

## 故障排除

### 常见问题

1. **后端启动失败**:
   - 检查端口8000是否被占用
   - 确认所有依赖已正确安装
   - 查看日志输出获取详细错误信息

2. **前端无法连接后端**:
   - 确认后端服务正在运行
   - 检查API地址配置是否正确
   - 查看浏览器控制台的网络错误

3. **数据库错误**:
   - 确认数据库文件权限正确
   - 检查磁盘空间是否充足
   - 查看数据库日志

## 贡献指南

1. Fork项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建Pull Request

## 许可证

本项目采用MIT许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 联系方式

如有问题或建议，请通过以下方式联系：

- 项目Issues: [GitHub Issues](https://github.com/your-repo/issues)
- 邮箱: your-email@example.com

## 更新日志

### v1.0.0 (2025-06-25)
- 初始版本发布
- 实现基础的被试管理功能
- 实现地图管理功能
- 集成机器狗控制系统
- 提供完整的前后端API接口
