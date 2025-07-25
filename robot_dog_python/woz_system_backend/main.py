"""
WOZ系统后端主应用 - FastAPI入口点
"""
import logging
import asyncio
import signal
from contextlib import asynccontextmanager
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from flask.cli import F
import uvicorn
import threading
import numpy as np
import librosa
import subprocess
import shlex


from .config import (
    API_HOST, API_PORT, API_PREFIX, CORS_ORIGINS, 
    LOG_LEVEL, LOG_FORMAT, STATIC_ROOT
)
from .database import db
# from .dds_bridge import dds_bridge
from .api_handlers import participant_handler, map_handler, target_handler

import os
import sys
import time
import json

# 配置日志
logging.basicConfig(
    level=LOG_LEVEL,
    format=LOG_FORMAT,
    handlers=[
        logging.StreamHandler(),  # 输出到终端
        logging.FileHandler("app.log")  # 输出到文件
    ]
)
logger = logging.getLogger(__name__)

# ==== DDS相关导入 ====
communication_dir_path = "/home/d3lab/Projects/RemoteControlDog/robot_dog_python/communication"
sys.path.append(communication_dir_path)
from unitree_sdk2py.core.channel import ChannelPublisher, ChannelSubscriber, ChannelFactoryInitialize
from dds_data_structure import SpeechControl, RobotLog

ChannelFactoryInitialize(networkInterface="enP8p1s0")

# 全局关闭事件
shutdown_event = asyncio.Event()

class DogStatus:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(DogStatus, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        if not hasattr(self, '_initialized') or not self._initialized:

            self.dds_sub_dog_status = ChannelSubscriber("rt/robot_log", RobotLog)
            self.dds_sub_dog_status.Init()
            self.dds_cmd_dog_status = RobotLog()
            self._initialized = True
            self.running = True
            self.dog_log = 0

    def dds_listener_thread(self):
        import io
        from contextlib import redirect_stdout
        from functools import wraps
        while self.running and not shutdown_event.is_set():
            try:
                # 创建一个StringIO对象来捕获输出
                captured_output = io.StringIO()
                
                # 重定向stdout并调用Read
                with redirect_stdout(captured_output):
                    msg = self.dds_sub_dog_status.Read(timeout=1)
                
                # 获取捕获的输出
                output = captured_output.getvalue()
                
                # 过滤掉不想要的错误信息
                if output and not output.startswith("[Reader] take sample error"):
                    print(output, end='')  # end='' 因为原本的print已经包含换行
                
                if msg:
                    self.dog_log = msg.event_id
                    print(f"Received dog status: {msg}")
                    
            except Exception as e:
                pass
            time.sleep(0.4)  # 避免过于频繁的轮询
        logger.info("DDS listener thread stopped")

dog_status = DogStatus()

class SpeechController:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(SpeechController, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        if not hasattr(self, '_initialized') or not self._initialized:
            

            self.dds_pub_speech_control = ChannelPublisher("SpeechControl", SpeechControl)
            self.dds_pub_speech_control.Init()
            self.dds_cmd_speech_control = SpeechControl()
            self._initialized = True

    def synthesis_speech(self, text, volume=-1):
        self.dds_cmd_speech_control.text_to_speak = text
        self.dds_cmd_speech_control.volume = volume
        self.dds_pub_speech_control.Write(self.dds_cmd_speech_control)

    def set_volume(self, volume: int):
        self.dds_cmd_speech_control.volume = volume
        self.dds_cmd_speech_control.text_to_speak = ""
        self.dds_pub_speech_control.Write(self.dds_cmd_speech_control)

speech_controller = SpeechController()

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
    
    # # 初始化DDS桥接器
    # try:
    #     await dds_bridge.initialize()
    #     logger.info("DDS bridge initialized successfully")
    # except Exception as e:
    #     logger.warning(f"DDS bridge initialization failed: {e}")
    
    logger.info("WOZ System Backend started successfully")
    
    yield
    
    # 关闭时清理
    logger.info("Shutting down WOZ System Backend...")
    
    # 设置全局关闭事件
    shutdown_event.set()
    
    # 停止DDS监听线程
    try:
        dog_status.running = False
        logger.info("Stopping DDS listener thread...")
        # 等待DDS线程结束（最多等5秒）
        await asyncio.sleep(0.5)
    except Exception as e:
        logger.error(f"Error stopping DDS listener: {e}")
    
    # await dds_bridge.shutdown()
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


@app.post(f"{API_PREFIX}/sessions/{{session_id}}/call_name", status_code=202)
async def call_name(session_id: str, data: Dict):
    global dds_cmd_speech_control, dds_pub_speech_control

    """触发呼唤名字动作"""
    participant_name = data.get('participantName',"小朋友")
    logger.info(f"Received call_name for session {session_id}, participant: {participant_name}")

    speech_controller.synthesis_speech(f"{participant_name}，快看我这里")
    
    return {"message": f"Call name command for {participant_name} sent."}


@app.post(f"{API_PREFIX}/sessions/{{session_id}}/voice_prompt", status_code=202)
async def voice_prompt(session_id: str, data: Dict):
    """触发语音提示动作"""
    logger.info(f"Received voice_prompt for session {session_id}, data: {data}")

    participant_name = data.get('participantName',"小朋友")

    # await dds_bridge.send_voice_prompt_command(data)
    speech_controller.synthesis_speech(f"{participant_name}你看这里")
    return {"message": "Voice prompt command sent."}


@app.post(f"{API_PREFIX}/sessions/{{session_id}}/end_leg_lift", status_code=202)
async def end_leg_lift(session_id: str):
    """触发结束抬脚动作"""
    logger.info(f"Received end_leg_lift for session {session_id}")
    # TODO: 实现结束抬脚的具体逻辑
    # await dds_bridge.send_end_leg_lift_command()
    return {"message": "End leg lift command sent."}


@app.post(f"{API_PREFIX}/sessions/{{session_id}}/child_left_frame", status_code=200)
async def child_left_frame(session_id: str, data: Dict):
    """记录孩子脱离画面事件"""
    logger.info(f"Received child_left_frame for session {session_id}, data: {data}")
    # TODO: 实现记录孩子脱离画面的具体逻辑，可能只是记录日志或数据库
    # await db.log_event(...)
    speech_controller.synthesis_speech(f"可不可以站到我面前来呀？", volume=-1)
    return {"message": "Child left frame event recorded."}

@app.post(f"{API_PREFIX}/sessions/{{session_id}}/ja_success", status_code=200)
async def ja_success(session_id: str, data: Dict):
    """记录孩子脱离画面事件"""
    logger.info(f"Received ja_success for session {session_id}, data: {data}")
    participantName = data.get("participantName", "小朋友")
    speech_controller.synthesis_speech(f"{participantName}，你太棒啦！", volume=-1)

    return {"message": "JA success event recorded."}

@app.post(f"{API_PREFIX}/sessions/{{session_id}}/ja_failure", status_code=200)
async def ja_failure(session_id: str, data: Dict):
    """记录孩子脱离画面事件"""
    logger.info(f"Received ja_failure for session {session_id}, data: {data}")
    participantName = data.get("participantName", "小朋友")
    speech_controller.synthesis_speech(f"我们再试一次。", volume=-1)
    return {"message": "JA failure event recorded."}

@app.post(f"{API_PREFIX}/sessions/{{session_id}}/actions", status_code=202)
async def trigger_session_action(session_id: str, action_data: Dict):
    """触发会话动作"""
    try:
        action_type = action_data.get("actionType")
        payload = action_data.get("payload", {})
        
        if action_type == "GENERATE_SPEECH":
            text = payload.get("text", "")
            participant_name = payload.get("participantName", "")

        
        elif action_type == "LOG_EVENT":
            event_name = payload.get("eventName", "")
            event_details = payload.get("details", {})

        
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
    return {
        "body_log": dog_status.dog_log
    }
    # return await dds_bridge.get_robot_status()


@app.post(f"{API_PREFIX}/robot/commands", status_code=202)
async def send_robot_command(command_data: Dict):
    """发送机器人控制命令"""
    try:
        # success = await dds_bridge.send_robot_command(command_data)
        # if not success:
        #     raise HTTPException(status_code=500, detail="Failed to send robot command")
        
        return {"message": "Command sent successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to send robot command: {e}")
        raise HTTPException(status_code=500, detail="Failed to send robot command")


# ==================== 麦克风音频流API ====================

# 音频流参数 (调整以降低延迟和优化语音)
CHUNK = 2048  # 减小块大小以降低延迟
FORMAT = "S16_LE"  # 16-bit signed little endian (与原来的pyaudio.paInt16相同)
CHANNELS = 1
RATE = 48000  # 设置为48000Hz以匹配硬件原生采样率，避免重采样


@app.websocket(f"{API_PREFIX}/ws/mic")
async def websocket_mic_stream(websocket: WebSocket, samplerate: int = 16000):
    await websocket.accept()
    logger.info(f"Microphone WebSocket connection established. Target samplerate: {samplerate}")
    
    # 目标采样率
    TARGET_RATE = samplerate
    
    # 统计变量
    packets_sent = 0
    stats_start_time = time.time()
    last_stats_time = stats_start_time
    
    # arecord 进程
    arecord_process = None
    
    # 异步统计任务
    async def log_stats():
        nonlocal packets_sent, last_stats_time
        while not shutdown_event.is_set():
            try:
                await asyncio.sleep(5.0)  # 每5秒统计一次
                current_time = time.time()
                elapsed = current_time - last_stats_time
                if elapsed > 0:
                    packets_per_second = packets_sent / elapsed
                    logger.info(f"Audio stats - Packets sent: {packets_sent}, Rate: {packets_per_second:.2f} packets/sec")
                    packets_sent = 0
                    last_stats_time = current_time
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in stats logging: {e}")
    
    stats_task = asyncio.create_task(log_stats())
    
    try:
        # 构建 arecord 命令
        # 使用 plughw 设备避免 ALSA 配置问题
        # hw:0,0 是 USB PnP Audio Device
        cmd = [
            "arecord",
            "-D", "hw:0,0",
            "-f", FORMAT,        # 格式
            "-c", str(CHANNELS), # 声道数
            "-r", str(RATE),     # 采样率
            "-t", "raw",         # 输出原始数据
            "--buffer-size=8192",  # 设置缓冲区大小，减少延迟
            "-q"                 # 安静模式，减少日志输出
        ]
        
        logger.info(f"Starting arecord with command: {' '.join(cmd)}")
        
        # 创建子进程
        arecord_process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        logger.info("arecord process started successfully")
        
        # 给 arecord 一点时间初始化
        await asyncio.sleep(0.5)
        
        # 检查进程是否仍在运行
        if arecord_process.returncode is not None:
            stderr_output = await arecord_process.stderr.read()
            logger.error(f"arecord process exited with code {arecord_process.returncode}. stderr: {stderr_output.decode()}")
            raise Exception("arecord process failed to start")
        
        # 读取音频数据
        empty_reads = 0
        while not shutdown_event.is_set():
            try:
                # 读取较小的数据块，让读取更快响应
                data = await asyncio.wait_for(
                    arecord_process.stdout.read(512),  # 减小读取块大小
                    timeout=2.0  # 增加超时时间
                )
                
                if not data:
                    empty_reads += 1
                    if empty_reads > 5:  # 允许最多5次空读取
                        logger.warning("No data received from arecord after multiple attempts")
                        break
                    await asyncio.sleep(0.1)  # 短暂等待后重试
                    continue
                
                empty_reads = 0  # 重置空读取计数
                
                # 处理音频数据
                processed_data = data
                
                # 如果需要重采样
                if TARGET_RATE != RATE:
                    try:
                        # 将字节数据转换为numpy数组 (int16) -> float32
                        audio_np = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
                        
                        # 使用librosa进行重采样
                        resampled_audio = librosa.resample(audio_np, orig_sr=RATE, target_sr=TARGET_RATE)
                        
                        # 将重采样后的数据转换回int16，然后转换为字节
                        resampled_audio_int16 = (resampled_audio * 32767).astype(np.int16)
                        processed_data = resampled_audio_int16.tobytes()
                    except Exception as e:
                        logger.error(f"Error during resampling: {e}")
                        continue
                
                # 发送音频数据（只发送纯音频字节流）
                await websocket.send_bytes(processed_data)
                packets_sent += 1
                
            except asyncio.TimeoutError:
                # 超时是正常的，继续循环
                continue
            except asyncio.CancelledError:
                logger.info("Audio streaming cancelled")
                break
            except WebSocketDisconnect:
                logger.info("WebSocket client disconnected")
                break
            except Exception as e:
                logger.error(f"Error during audio streaming: {e}")
                break
    
    except Exception as e:
        logger.error(f"Failed to start arecord: {e}")
        await websocket.close(code=1011, reason="Audio capture failed")
    
    finally:
        # 清理工作
        logger.info("Starting audio stream cleanup...")
        
        # 取消统计任务
        stats_task.cancel()
        try:
            await stats_task
        except asyncio.CancelledError:
            pass
        
        # 终止 arecord 进程
        if arecord_process:
            try:
                logger.info("Terminating arecord process...")
                arecord_process.terminate()
                # 等待进程结束（最多等2秒）
                try:
                    await asyncio.wait_for(arecord_process.wait(), timeout=2.0)
                    logger.info("arecord process terminated gracefully")
                except asyncio.TimeoutError:
                    logger.warning("arecord process did not terminate in time, killing it")
                    arecord_process.kill()
                    await arecord_process.wait()
            except Exception as e:
                logger.error(f"Error terminating arecord: {e}")
        
        # 输出最终统计
        total_time = time.time() - stats_start_time
        logger.info(f"WebSocket closed. Total time: {total_time:.2f}s, Total packets sent: {packets_sent}")
        logger.info("Microphone WebSocket connection closed")


# ==================== 健康检查API ====================

@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "dds_connected": True
    }


@app.get("/")
async def root():
    """根端点"""
    return {
        "message": "WOZ System Backend API",
        "version": "1.0.0",
        "docs": "/docs"
    }


def handle_shutdown(signum, frame):
    """处理关闭信号"""
    logger.info(f"Received signal {signum}, initiating shutdown...")
    shutdown_event.set()
    dog_status.running = False


def run_server():
    # 注册信号处理器
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)
    
    # 启动DDS监听线程
    dog_log_thread = threading.Thread(target=dog_status.dds_listener_thread)
    dog_log_thread.daemon = True
    dog_log_thread.start()
    
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
