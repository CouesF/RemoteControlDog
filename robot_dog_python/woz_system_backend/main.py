"""
WOZ系统后端主应用 - FastAPI入口点
"""
import logging
import asyncio
from contextlib import asynccontextmanager
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from .config import (
    API_HOST, API_PORT, API_PREFIX, CORS_ORIGINS, 
    LOG_LEVEL, LOG_FORMAT, STATIC_ROOT
)
from .database import db
from .dds_bridge import dds_bridge
from .api_handlers import participant_handler, map_handler, target_handler

# 配置日志
logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化
    logger.info("Starting WOZ System Backend...")
    
    # 初始化数据库
    try:
        db.init_tables()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise
    
    # 初始化DDS桥接器
    try:
        await dds_bridge.initialize()
        logger.info("DDS bridge initialized successfully")
    except Exception as e:
        logger.warning(f"DDS bridge initialization failed: {e}")
    
    logger.info("WOZ System Backend started successfully")
    
    yield
    
    # 关闭时清理
    logger.info("Shutting down WOZ System Backend...")
    await dds_bridge.shutdown()
    logger.info("WOZ System Backend shutdown complete")


# 创建FastAPI应用
app = FastAPI(
    title="WOZ System Backend API",
    description="机器人辅助训练Wizard-of-Oz系统后端API",
    version="1.0.0",
    lifespan=lifespan
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件服务
app.mount("/static", StaticFiles(directory=str(STATIC_ROOT)), name="static")


# 全局异常处理器
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


# ==================== 被试管理API ====================

@app.get(f"{API_PREFIX}/participants", response_model=List[Dict])
async def get_participants():
    """获取所有被试者列表"""
    return await participant_handler.get_all_participants()


@app.get(f"{API_PREFIX}/participants/{{participant_id}}", response_model=Dict)
async def get_participant(participant_id: str):
    """根据ID获取被试者"""
    return await participant_handler.get_participant_by_id(participant_id)


@app.post(f"{API_PREFIX}/participants", response_model=Dict, status_code=201)
async def create_participant(participant_data: Dict):
    """创建新被试者"""
    return await participant_handler.create_participant(participant_data)


@app.put(f"{API_PREFIX}/participants/{{participant_id}}", response_model=Dict)
async def update_participant(participant_id: str, participant_data: Dict):
    """更新被试者信息"""
    return await participant_handler.update_participant(participant_id, participant_data)


@app.delete(f"{API_PREFIX}/participants/{{participant_id}}", status_code=204)
async def delete_participant(participant_id: str):
    """删除被试者"""
    await participant_handler.delete_participant(participant_id)


@app.post(f"{API_PREFIX}/participants/{{participant_id}}/images", response_model=Dict, status_code=201)
async def upload_participant_image(
    participant_id: str,
    imageFile: UploadFile = File(...),
    imageType: str = Form(...)
):
    """为被试者上传图片"""
    return await participant_handler.upload_participant_image(participant_id, imageFile, imageType)


@app.get(f"{API_PREFIX}/participants/{{participant_id}}/images", response_model=List[Dict])
async def get_participant_images(participant_id: str):
    """获取被试者的所有图片"""
    return await participant_handler.get_participant_images(participant_id)


@app.delete(f"{API_PREFIX}/images/{{image_id}}", status_code=204)
async def delete_image(image_id: str):
    """删除图片"""
    await participant_handler.delete_image(image_id)


# ==================== 地图管理API ====================

@app.get(f"{API_PREFIX}/maps", response_model=List[Dict])
async def get_maps():
    """获取所有地图列表"""
    return await map_handler.get_all_maps()


@app.get(f"{API_PREFIX}/maps/{{map_id}}", response_model=Dict)
async def get_map(map_id: str):
    """根据ID获取地图"""
    return await map_handler.get_by_id(map_id)


@app.post(f"{API_PREFIX}/maps", response_model=Dict, status_code=201)
async def create_map(map_data: Dict):
    """创建新地图"""
    return await map_handler.create_map(map_data)


@app.put(f"{API_PREFIX}/maps/{{map_id}}", response_model=Dict)
async def update_map(map_id: str, map_data: Dict):
    """更新地图信息"""
    return await map_handler.update_map(map_id, map_data)


@app.delete(f"{API_PREFIX}/maps/{{map_id}}", status_code=204)
async def delete_map(map_id: str):
    """删除地图"""
    await map_handler.delete_map(map_id)


@app.get(f"{API_PREFIX}/maps/{{map_id}}/targets", response_model=List[Dict])
async def get_map_targets(map_id: str):
    """获取地图的所有目标点"""
    return await map_handler.get_map_targets(map_id)


# ==================== 目标点管理API ====================

@app.post(f"{API_PREFIX}/maps/{{map_id}}/targets", response_model=Dict, status_code=201)
async def create_target(
    map_id: str,
    targetName: str = Form(...),
    description: str = Form(""),
    pose: str = Form(...),  # JSON字符串
    targetImgFile: Optional[UploadFile] = File(None),
    envImgFile: Optional[UploadFile] = File(None)
):
    """在地图上创建新目标点"""
    target_data = {
        'targetName': targetName,
        'description': description,
        'pose': pose
    }
    return await map_handler.create_target(map_id, target_data, targetImgFile, envImgFile)


@app.get(f"{API_PREFIX}/targets/{{target_id}}", response_model=Dict)
async def get_target(target_id: str):
    """根据ID获取目标点"""
    return await target_handler.get_by_id(target_id)


@app.put(f"{API_PREFIX}/targets/{{target_id}}", response_model=Dict)
async def update_target(
    target_id: str,
    targetName: str = Form(...),
    description: str = Form(""),
    pose: str = Form(...),  # JSON字符串
    targetImgFile: Optional[UploadFile] = File(None),
    envImgFile: Optional[UploadFile] = File(None)
):
    """更新目标点信息"""
    target_data = {
        'targetName': targetName,
        'description': description,
        'pose': pose
    }
    return await map_handler.update_target(target_id, target_data, targetImgFile, envImgFile)


@app.put(f"{API_PREFIX}/maps/{{map_id}}/targets/order")
async def update_targets_order(map_id: str, order_data: Dict):
    """批量更新目标点顺序"""
    target_ids = order_data.get('targetIds', [])
    if not target_ids:
        raise HTTPException(status_code=400, detail="targetIds is required")
    
    await map_handler.update_targets_order(map_id, target_ids)
    return {"message": "Target order updated successfully"}


@app.delete(f"{API_PREFIX}/targets/{{target_id}}", status_code=204)
async def delete_target(target_id: str):
    """删除目标点"""
    await map_handler.delete_target(target_id)


# ==================== 会话管理API ====================

@app.post(f"{API_PREFIX}/sessions", response_model=Dict, status_code=201)
async def create_session(session_data: Dict):
    """创建新实验会话"""
    # TODO: 实现会话创建逻辑
    raise HTTPException(status_code=501, detail="Session creation not implemented yet")


@app.put(f"{API_PREFIX}/sessions/{{session_id}}/status", response_model=Dict)
async def update_session_status(session_id: str, status_data: Dict):
    """更新会话状态"""
    # TODO: 实现会话状态更新逻辑
    raise HTTPException(status_code=501, detail="Session status update not implemented yet")


@app.post(f"{API_PREFIX}/sessions/{{session_id}}/instructions", response_model=Dict, status_code=201)
async def create_instruction(session_id: str, instruction_data: Dict):
    """在会话中创建新指令"""
    # TODO: 实现指令创建逻辑
    raise HTTPException(status_code=501, detail="Instruction creation not implemented yet")


@app.post(f"{API_PREFIX}/instructions/{{instruction_id}}/prompts", response_model=Dict, status_code=201)
async def add_prompt(instruction_id: str, prompt_data: Dict):
    """为指令添加提示尝试"""
    # TODO: 实现提示添加逻辑
    raise HTTPException(status_code=501, detail="Prompt addition not implemented yet")


@app.post(f"{API_PREFIX}/sessions/{{session_id}}/actions", status_code=202)
async def trigger_session_action(session_id: str, action_data: Dict):
    """触发会话动作"""
    try:
        action_type = action_data.get("actionType")
        payload = action_data.get("payload", {})
        
        if action_type == "GENERATE_SPEECH":
            text = payload.get("text", "")
            participant_name = payload.get("participantName", "")
            success = await dds_bridge.send_speech_command(text, participant_name)
            if not success:
                raise HTTPException(status_code=500, detail="Failed to generate speech")
        
        elif action_type == "LOG_EVENT":
            event_name = payload.get("eventName", "")
            event_details = payload.get("details", {})
            success = await dds_bridge.log_event(event_name, event_details)
            if not success:
                raise HTTPException(status_code=500, detail="Failed to log event")
        
        else:
            raise HTTPException(status_code=400, detail=f"Unknown action type: {action_type}")
        
        return {"message": "Action triggered successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to trigger action: {e}")
        raise HTTPException(status_code=500, detail="Failed to trigger action")


# ==================== 机器人状态API ====================

@app.get(f"{API_PREFIX}/robot/status", response_model=Dict)
async def get_robot_status():
    """获取机器人状态"""
    return await dds_bridge.get_robot_status()


@app.post(f"{API_PREFIX}/robot/commands", status_code=202)
async def send_robot_command(command_data: Dict):
    """发送机器人控制命令"""
    try:
        success = await dds_bridge.send_robot_command(command_data)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to send robot command")
        
        return {"message": "Command sent successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to send robot command: {e}")
        raise HTTPException(status_code=500, detail="Failed to send robot command")


# ==================== 健康检查API ====================

@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {
        "status": "healthy",
        "timestamp": asyncio.get_event_loop().time(),
        "dds_connected": dds_bridge.is_connected
    }


@app.get("/")
async def root():
    """根端点"""
    return {
        "message": "WOZ System Backend API",
        "version": "1.0.0",
        "docs": "/docs"
    }


def run_server():
    """运行服务器"""
    uvicorn.run(
        "woz_system_backend.main:app",
        host=API_HOST,
        port=API_PORT,
        reload=False,
        log_level=LOG_LEVEL.lower()
    )


if __name__ == "__main__":
    run_server()
