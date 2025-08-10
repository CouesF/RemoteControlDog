#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
优化版实时UDP摄像头网关 (v5 - USB Camera Focused)
端口：本地8991，FRP远程58991
功能：多摄像头管理、实时视频流传输、性能优化
"""

import asyncio
import socket
import json
import time
import hmac
import hashlib
import uuid
import logging
import cv2
import numpy as np
from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass
import struct
import threading
from queue import Queue, Empty, Full
import base64
import subprocess
import os
import signal
import sys

from main_distortion_corrector import FisheyeCorrector
import numpy as np
import cv2

current_script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_script_dir)
communication_dir_path = os.path.join(parent_dir, 'communication')
sys.path.append(communication_dir_path)

try:
    from dds_data_structure import HeadCommand
    from unitree_sdk2py.core.channel import ChannelSubscriber, ChannelFactoryInitialize
    DDS_ENABLED = True
except ImportError as e:
    DDS_ENABLED = False
    print(f"Warning: DDS libraries not found or failed to import. Head tracking will be disabled. Error: {e}")

# <--- Head Tracking Configuration --->
CAMERA_HORIZONTAL_FOV_DEG = 90.0
HEAD_MAX_YAW_DEG = 90.0

RECORDING_PATH = os.path.expanduser("/home/d3lab/Projects/RemoteControlDog/robot_dog_python/robot_recordings")

def radial_color_correction_v2(img, g_center, g_edge, r_center, r_edge):
    h, w = img.shape[:2]
    Y, X = np.ogrid[:h, :w]
    center_x, center_y = w / 2, h / 2
    distance = np.sqrt((X - center_x) ** 2 + (Y - center_y) ** 2)
    max_dist = np.sqrt(center_x ** 2 + center_y ** 2)
    alpha = distance / max_dist  # 0=中心，1=四周

    g_gain = g_center * (1 - alpha) + g_edge * alpha
    r_gain = r_center * (1 - alpha) + r_edge * alpha

    b, g, r = cv2.split(img)
    g = np.clip(g * g_gain, 0, 255)
    r = np.clip(r * r_gain, 0, 255)
    img_corr = cv2.merge([b.astype(np.uint8), g.astype(np.uint8), r.astype(np.uint8)])
    return img_corr

def gray_world_awb(img):
    """
    灰世界自动白平衡算法。
    输入img: BGR格式np.uint8图像，输出自动平衡后的np.uint8图像。
    """
    img = img.astype(np.float32)
    avg_b = np.mean(img[:, :, 0])
    avg_g = np.mean(img[:, :, 1])
    avg_r = np.mean(img[:, :, 2])
    avg_gray = (avg_b + avg_g + avg_r) / 3
    img[:, :, 0] *= avg_gray / avg_b
    img[:, :, 1] *= avg_gray / avg_g
    img[:, :, 2] *= avg_gray / avg_r
    img = np.clip(img, 0, 255)
    return img.astype(np.uint8)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 安全配置
SHARED_SECRET_KEY = b"robot_dog_camera_secret_2024"
SESSION_TIMEOUT = 60*60  # 60分钟会话超时
MAX_UDP_SIZE = 50000  # 增大UDP包大小，减少分片
FRAGMENT_THRESHOLD = 1400  # 分片阈值提高
HEADER_SIZE = 32  # 减小头部大小

# 摄像头配置 - 优化结构，分离捕获和传输配置
CAMERA_CONFIGS = {
    0: {
        # 基本信息
        "name": "USB-F",
        "device_id": 0,
        
        # 摄像头捕获设置
        "capture": {
            "format": "MJPG",           # 摄像头格式
            "resolution": (640, 480),   # 摄像头分辨率
            "fps": 25,                  # 摄像头帧率
        },
        
        # 传输设置
        "stream": {
            "resolution": (640, 480),   # 传输分辨率
            "fps": 10,                  # 传输帧率
            "quality": 15,              # JPEG质量
        },
        
        # 处理选项
        "processing": {
            "enable_fisheye_correction": True,
            "enable_flip": True,        # 是否翻转
            "flip_method": "both",      # "horizontal", "vertical", "both", "none"
            "enable_rotation": False,   # 是否旋转
            "rotation_angle": 0,        # 旋转角度 (90, 180, 270)
            
            # 去畸变参数（只有enable_fisheye_correction为True时生效）
            "fisheye_params": {
                'mappingCoeffs': np.array([272.428,-0.002384499,0.0,0.0]),
                'imageSize': np.array([480, 640]),
                'distortionCenter': np.array([328.71590201,234.40496395759]),
                'stretchMatrix': np.array([[1.0, 0.0], [0.0, 1.0]]),
                'undistorted_fov_deg': 110.0
            }
        },
        
        # 录制设置
        "recording": {
            "enable": True,             # 是否启用录制
        }
    },
    2: {
        "name": "USB-l",
        "device_id": 2,
        
        "capture": {
            "format": "YUY2",
            "resolution": (320, 240),
            "fps": 30,
        },
        
        "stream": {
            "resolution": (160, 120),
            "fps": 10,
            "quality": 10,
        },
        
        "processing": {
            "enable_fisheye_correction": False,
            "enable_flip": False,
            "flip_method": "both",
            "enable_rotation": False,
            "rotation_angle": 0,
        },
        
        "recording": {
            "enable": False,
        }
    },
    4: {
        "name": "USB-r",
        "device_id": 4,
        
        "capture": {
            "format": "YUY2",
            "resolution": (320, 240),
            "fps": 30,
        },
        
        "stream": {
            "resolution": (160, 120),
            "fps": 10,
            "quality": 10,
        },
        
        "processing": {
            "enable_fisheye_correction": True,
            "enable_flip": False,
            "flip_method": "none",
            "enable_rotation": False,
            "rotation_angle": 0,
            
            "fisheye_params": {
                'mappingCoeffs': np.array([166.6676260242524,-0.003056583298314,0.0,0.0]),
                'imageSize': np.array([240, 320]),
                'distortionCenter': np.array([160,120]),
                'stretchMatrix': np.array([[1.0, 0.0], [0.0, 1.0]]),
                'undistorted_fov_deg': 110.0
            }
        },
        
        "recording": {
            "enable": False,
        }
    },
}

@dataclass
class CameraFrame:
    """摄像头帧数据结构"""
    camera_id: int
    frame_data: bytes
    timestamp: float
    frame_id: str
    resolution: Tuple[int, int]
    quality: int

class SecurityManager:
    """安全管理器"""
    
    def __init__(self, secret_key: bytes):
        self.secret_key = secret_key
        self.active_sessions = {}
        
    def generate_signature(self, data: bytes, timestamp: float) -> str:
        """生成HMAC签名"""
        message = f"{timestamp}:{data.decode('utf-8') if isinstance(data, bytes) else str(data)}".encode('utf-8')
        signature = hmac.new(self.secret_key, message, hashlib.sha256).hexdigest()
        return signature
    
    def verify_signature(self, data: bytes, timestamp: float, signature: str) -> bool:
        """验证HMAC签名"""
        expected_signature = self.generate_signature(data, timestamp)
        return hmac.compare_digest(expected_signature, signature)
    
    def verify_timestamp(self, timestamp: float, tolerance: float = 30.0) -> bool:
        """验证时间戳（防重放攻击）"""
        current_time = time.time()
        return abs(current_time - timestamp) <= tolerance
    
    def create_session(self, client_addr: Tuple[str, int]) -> str:
        """创建会话"""
        session_id = uuid.uuid4().hex
        self.active_sessions[session_id] = {
            'client_addr': client_addr,
            'created_at': time.time(),
            'last_activity': time.time()
        }
        logger.info(f"创建摄像头会话 {session_id} for {client_addr}")
        return session_id
    
    def validate_session(self, session_id: str, client_addr: Tuple[str, int]) -> bool:
        """验证会话"""
        if session_id not in self.active_sessions:
            return False
        
        session = self.active_sessions[session_id]
        if session['client_addr'] != client_addr:
            return False
        
        if time.time() - session['last_activity'] > SESSION_TIMEOUT:
            del self.active_sessions[session_id]
            return False
        
        session['last_activity'] = time.time()
        return True
    
    def cleanup_expired_sessions(self):
        """清理过期会话"""
        current_time = time.time()
        expired_sessions = [
            sid for sid, session in self.active_sessions.items()
            if current_time - session['last_activity'] > SESSION_TIMEOUT
        ]
        
        for sid in expired_sessions:
            if sid in self.active_sessions:
                del self.active_sessions[sid]
                logger.info(f"清理过期摄像头会话: {sid}")

class PacketManager:
    """数据包管理器 - 支持自动切片"""
    
    def __init__(self):
        self.fragment_buffers = {}
        self.fragment_timeout = 10.0
    
    def prepare_packet(self, data: Dict[str, Any], security_manager: SecurityManager) -> bytes:
        """准备发送数据包"""
        timestamp = time.time()
        packet = {
            'timestamp': timestamp,
            'data': data
        }
        
        packet_json = json.dumps(packet, ensure_ascii=False)
        packet_bytes = packet_json.encode('utf-8')
        
        header = {}
        header_bytes = json.dumps(header).encode('utf-8')
        header_size_packed = struct.pack('!H', len(header_bytes))
        
        return header_size_packed + header_bytes + packet_bytes
    
    def auto_fragment(self, data: bytes) -> List[bytes]:
        """自动判断是否需要切片"""
        if len(data) <= MAX_UDP_SIZE:
            return [data]
        
        fragment_id = uuid.uuid4().hex[:8]
        chunk_size = MAX_UDP_SIZE - 100
        chunks = []
        
        total_fragments = (len(data) + chunk_size - 1) // chunk_size
        
        for i in range(0, len(data), chunk_size):
            chunk = data[i:i + chunk_size]
            fragment_index = i // chunk_size
            
            fragment_header = {
                'fragment_id': fragment_id,
                'fragment_index': fragment_index,
                'total_fragments': total_fragments,
                'is_last': fragment_index == total_fragments - 1
            }
            
            header_bytes = json.dumps(fragment_header).encode('utf-8')
            header_size = struct.pack('!H', len(header_bytes))
            
            fragment_packet = header_size + header_bytes + chunk
            chunks.append(fragment_packet)
        
        return chunks
    
    def process_received_packet(self, data: bytes, addr: Tuple[str, int]) -> Optional[Dict[str, Any]]:
        """处理接收到的数据包"""
        try:
            if len(data) < 2:
                return None
            
            header_size = struct.unpack('!H', data[:2])[0]
            if len(data) < 2 + header_size:
                return None
            
            header_bytes = data[2:2 + header_size]
            header = json.loads(header_bytes.decode('utf-8'))
            
            if 'fragment_id' in header:
                return self._handle_fragment(header, data[2 + header_size:], addr)
            else:
                return self._handle_complete_packet(header, data[2 + header_size:])
        
        except Exception as e:
            logger.error(f"数据包处理失败: {e}")
            return None
    
    def _handle_fragment(self, header: Dict, chunk: bytes, addr: Tuple[str, int]) -> Optional[Dict[str, Any]]:
        """处理分片包"""
        fragment_id = header['fragment_id']
        fragment_index = header['fragment_index']
        total_fragments = header['total_fragments']
        
        if fragment_id not in self.fragment_buffers:
            self.fragment_buffers[fragment_id] = {
                'chunks': {},
                'total_fragments': total_fragments,
                'addr': addr,
                'timestamp': time.time()
            }
        
        self.fragment_buffers[fragment_id]['chunks'][fragment_index] = chunk
        
        buffer = self.fragment_buffers[fragment_id]
        if len(buffer['chunks']) == total_fragments:
            complete_data = b''.join(buffer['chunks'][i] for i in range(total_fragments))
            del self.fragment_buffers[fragment_id]
            return self._parse_complete_data(complete_data)
        
        return None
    
    def _handle_complete_packet(self, header: Dict, data: bytes) -> Optional[Dict[str, Any]]:
        """处理完整数据包"""
        return self._parse_complete_data(data)
    
    def _parse_complete_data(self, data: bytes) -> Optional[Dict[str, Any]]:
        """解析完整数据"""
        try:
            packet = json.loads(data.decode('utf-8'))
            return packet
        except Exception as e:
            logger.error(f"数据解析失败: {e}")
            return None
    
    def cleanup_expired_fragments(self):
        """清理过期分片"""
        current_time = time.time()
        expired_fragments = [
            fid for fid, buffer in self.fragment_buffers.items()
            if current_time - buffer['timestamp'] > self.fragment_timeout
        ]
        
        for fid in expired_fragments:
            if fid in self.fragment_buffers:
                del self.fragment_buffers[fid]
                logger.warning(f"清理过期摄像头分片: {fid}")

class SmartCameraHandler:
    """智能摄像头处理器"""

    def __init__(self, camera_id: int, config: Dict[str, Any], head_state: Dict, head_state_lock: threading.Lock, recording_path: str):
        self.camera_id = camera_id
        self.config = config
        self.cap: Optional[cv2.VideoCapture] = None
        self.is_running = False
        self.capture_thread = None

        self._latest_frame: Optional[CameraFrame] = None
        self._frame_lock = threading.Lock()

        self.is_recording = False
        self.video_writer: Optional[cv2.VideoWriter] = None
        self.subscriber_count = 0
        self.output_dir = RECORDING_PATH
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

        self.head_state = head_state
        self.head_state_lock = head_state_lock

        # 初始化去畸变校正器（如果启用）
        self.corrector: Optional[FisheyeCorrector] = None 
        if self.config['processing']['enable_fisheye_correction']:
            try:
                # 为FisheyeCorrector准备兼容的配置格式
                compat_config = {
                    'is_fisheye': True,
                    'undistorted_resolution': self.config['stream']['resolution'],
                    'fisheye_params': self.config['processing']['fisheye_params']
                }
                self.corrector = FisheyeCorrector(compat_config)
                logger.info(f"Camera {self.camera_id}: Fisheye corrector initialized")
            except Exception as e:
                logger.error(f"Failed to initialize FisheyeCorrector for camera {self.camera_id}: {e}")
                self.corrector = None

        self.stats = {
            'frames_captured': 0,
            'frames_dropped': 0,
            'frames_sent': 0,
            'last_capture_time': 0,
            'capture_method': 'uninitialized'
        }

        # 计算传输帧率控制
        self.frame_interval = 1.0 / self.config['stream']['fps']
        self.last_send_time = 0

    def start_recording(self):
        """开始录制"""
        if not self.config['recording']['enable']:
            return
            
        if self.is_recording:
            return

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        cam_name = self.config['name'].replace(" ", "_")
        output_filename = os.path.join(self.output_dir, f"{cam_name}_{timestamp}.mp4")

        # 使用传输分辨率作为录制分辨率
        width, height = self.config['stream']['resolution']
        fps = self.config['stream']['fps']
        
        # 尝试多种编码器
        codecs_to_try = [
            ('XVID', cv2.VideoWriter_fourcc(*'XVID')),
            ('mp4v', cv2.VideoWriter_fourcc(*'mp4v')),
            ('H264', cv2.VideoWriter_fourcc(*'H264')),
            ('MJPG', cv2.VideoWriter_fourcc(*'MJPG')),
        ]
        
        self.video_writer = None
        self.current_output_file = output_filename
        
        for codec_name, fourcc in codecs_to_try:
            try:
                os.makedirs(os.path.dirname(output_filename), exist_ok=True)
                
                self.video_writer = cv2.VideoWriter(output_filename, fourcc, fps, (width, height))
                
                if self.video_writer and self.video_writer.isOpened():
                    self.is_recording = True
                    self.recording_stats = {
                        'frames_written': 0,
                        'write_errors': 0,
                        'last_write_time': time.time(),
                        'codec_used': codec_name
                    }
                    logger.info(f"Camera {self.camera_id}: Started recording to {output_filename} using {codec_name} codec")
                    return
                else:
                    if self.video_writer:
                        self.video_writer.release()
                        self.video_writer = None
                    logger.warning(f"Camera {self.camera_id}: Failed to initialize with {codec_name} codec")
            except Exception as e:
                logger.warning(f"Camera {self.camera_id}: Exception with {codec_name} codec: {e}")
                if self.video_writer:
                    try:
                        self.video_writer.release()
                    except:
                        pass
                    self.video_writer = None
        
        logger.error(f"Camera {self.camera_id}: Failed to initialize video recording with any codec")

    def stop_recording(self):
        """停止录制"""
        if not self.is_recording:
            return

        self.is_recording = False
        
        if self.video_writer:
            try:
                self.video_writer.release()
                logger.info(f"Camera {self.camera_id}: Recording stopped. Stats: {getattr(self, 'recording_stats', {})}")
                
                if hasattr(self, 'current_output_file') and os.path.exists(self.current_output_file):
                    file_size = os.path.getsize(self.current_output_file)
                    if file_size > 0:
                        logger.info(f"Camera {self.camera_id}: Video file saved successfully ({file_size} bytes)")
                    else:
                        logger.warning(f"Camera {self.camera_id}: Video file is empty, removing it")
                        try:
                            os.remove(self.current_output_file)
                        except:
                            pass
                else:
                    logger.warning(f"Camera {self.camera_id}: Video file was not created")
                    
            except Exception as e:
                logger.error(f"Camera {self.camera_id}: Error during recording cleanup: {e}")
            finally:
                self.video_writer = None
                if hasattr(self, 'recording_stats'):
                    delattr(self, 'recording_stats')
                if hasattr(self, 'current_output_file'):
                    delattr(self, 'current_output_file')

    def _initialize_usb_camera(self) -> bool:
        """初始化USB摄像头"""
        try:
            device_id = self.config['device_id']
            capture_config = self.config['capture']
            
            logger.info(f"Initializing USB camera at device ID {device_id}")
            self.cap = cv2.VideoCapture(device_id, cv2.CAP_V4L2)

            if not self.cap or not self.cap.isOpened():
                logger.error(f"USB Camera {device_id}: Failed to open.")
                return False

            # 设置摄像头参数
            fourcc_format = capture_config.get("format", "MJPG")
            self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*fourcc_format))
            logger.info(f"USB Camera {device_id}: Setting format to {fourcc_format}")

            width, height = capture_config['resolution']
            fps = capture_config['fps']
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            self.cap.set(cv2.CAP_PROP_FPS, fps)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            # 验证设置
            ret, frame = self.cap.read()
            if not ret or frame is None:
                logger.error(f"USB Camera {device_id}: Could not read frame with specified settings")
                self.cap.release()
                return False
            
            actual_w = self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
            actual_h = self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
            actual_fps = self.cap.get(cv2.CAP_PROP_FPS)
            logger.info(f"USB Camera {device_id} initialized successfully. Format: {fourcc_format}")
            logger.info(f"Requested: {width}x{height} @ {fps}fps. Actual: {int(actual_w)}x{int(actual_h)} @ {actual_fps}fps")
            
            self.stats['capture_method'] = f'usb_{fourcc_format.lower()}'
            return True

        except Exception as e:
            logger.error(f"Exception during USB camera initialization for ID {device_id}: {e}", exc_info=True)
            return False

    async def start(self) -> bool:
        """启动摄像头"""
        success = self._initialize_usb_camera()

        if not success:
            logger.error(f"Camera {self.camera_id} ({self.config['name']}) initialization failed")
            return False

        self.is_running = True
        self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.capture_thread.start()
        
        logger.info(f"Camera {self.camera_id} ({self.config['name']}) started successfully")
        return True

    def _capture_loop(self):
        """摄像头捕获循环"""
        if not self.cap:
            logger.error(f"Capture loop for camera {self.camera_id} started without valid VideoCapture")
            return
                
        capture_interval = 1.0 / self.config['capture']['fps']
        consecutive_failures = 0
        max_failures = 30
        
        logger.info(f"Camera {self.camera_id} capture loop starting")

        while self.is_running:
            ret, frame = self.cap.read()

            if not ret or frame is None:
                consecutive_failures += 1
                logger.warning(f"Failed to read frame from camera {self.camera_id}. Failure count: {consecutive_failures}")
                if consecutive_failures > max_failures:
                    logger.error(f"Camera {self.camera_id} exceeded max consecutive read failures")
                    self.is_running = False
                    break
                time.sleep(0.1)
                continue
            
            consecutive_failures = 0
            capture_time = time.time()
            self.stats['last_capture_time'] = capture_time
            self.stats['frames_captured'] += 1

            # 检查是否需要发送帧（根据传输帧率控制）
            current_time = time.time()
            if current_time - self.last_send_time >= self.frame_interval:
                jpg_bytes = self._process_frame(frame, capture_time)
                if jpg_bytes:
                    cam_frame = CameraFrame(
                        camera_id=self.camera_id,
                        frame_data=jpg_bytes,
                        timestamp=capture_time, # Use the more accurate capture time
                        frame_id=uuid.uuid4().hex[:8],
                        resolution=self.config['stream']['resolution'],
                        quality=self.config['stream']['quality']
                    )

                    with self._frame_lock:
                        self._latest_frame = cam_frame
                    
                    self.last_send_time = current_time
            
            # 按捕获帧率控制循环
            time.sleep(max(0, capture_interval - (time.time() - current_time)))
        
        logger.warning(f"Capture loop for camera {self.camera_id} has exited")

    def _apply_rotation(self, frame: np.ndarray, angle: int) -> np.ndarray:
        """应用旋转"""
        if angle == 90:
            return cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
        elif angle == 180:
            return cv2.rotate(frame, cv2.ROTATE_180)
        elif angle == 270:
            return cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
        else:
            return frame

    def _apply_flip(self, frame: np.ndarray, flip_method: str) -> np.ndarray:
        """应用翻转"""
        if flip_method == "horizontal":
            return cv2.flip(frame, 1)
        elif flip_method == "vertical":
            return cv2.flip(frame, 0)
        elif flip_method == "both":
            return cv2.flip(frame, -1)
        else:
            return frame

    def _process_frame(self, frame: np.ndarray, capture_time: float) -> Optional[bytes]:
        """处理帧"""
        process_start_time = time.time()
        try:
            processed_frame = frame.copy()
            processing_config = self.config['processing']

            # 1. 应用去畸变校正
            if processing_config['enable_fisheye_correction'] and self.corrector:
                processed_frame = self.corrector.correct(processed_frame)

            # 2. 应用旋转
            if processing_config['enable_rotation'] and processing_config['rotation_angle'] != 0:
                processed_frame = self._apply_rotation(processed_frame, processing_config['rotation_angle'])

            # 3. 应用翻转
            if processing_config['enable_flip'] and processing_config['flip_method'] != "none":
                processed_frame = self._apply_flip(processed_frame, processing_config['flip_method'])

            # 4. 调整到传输分辨率
            target_width, target_height = self.config['stream']['resolution']
            if processed_frame.shape[1] != target_width or processed_frame.shape[0] != target_height:
                processed_frame = cv2.resize(processed_frame, (target_width, target_height), interpolation=cv2.INTER_AREA)

            # 5. 录制视频（使用处理后的帧）
            if self.is_recording and self.video_writer:
                try:
                    if processed_frame is not None and processed_frame.size > 0:
                        if hasattr(self, 'recording_stats'):
                            self.video_writer.write(processed_frame)
                            self.recording_stats['frames_written'] += 1
                            self.recording_stats['last_write_time'] = time.time()
                        else:
                            self.video_writer.write(processed_frame)
                    else:
                        if hasattr(self, 'recording_stats'):
                            self.recording_stats['write_errors'] += 1
                        logger.warning(f"Camera {self.camera_id}: Invalid frame data for recording")
                        
                except Exception as e:
                    if hasattr(self, 'recording_stats'):
                        self.recording_stats['write_errors'] += 1
                    logger.error(f"Camera {self.camera_id}: Video write error: {e}")
                    
                    if hasattr(self, 'recording_stats') and self.recording_stats['write_errors'] > 10:
                        logger.error(f"Camera {self.camera_id}: Too many write errors, stopping recording")
                        self.stop_recording()

            # 6. 绘制头部方向标记
            if DDS_ENABLED:
                current_yaw = 0.0
                with self.head_state_lock:
                    current_yaw = self.head_state.get('yaw_deg', 0.0)

                h, w, _ = processed_frame.shape
                center_x = w // 2

                clamped_yaw = max(-HEAD_MAX_YAW_DEG, min(current_yaw, HEAD_MAX_YAW_DEG))
                angle_ratio = clamped_yaw / (CAMERA_HORIZONTAL_FOV_DEG / 2.0)
                
                marker_x = int(center_x + (angle_ratio * center_x))
                marker_x = max(0, min(marker_x, w - 1))

                marker_start_pt = (marker_x, 0)
                marker_end_pt = (marker_x, 20)
                cv2.arrowedLine(processed_frame, marker_start_pt, marker_end_pt, (0, 0, 255), 2, cv2.LINE_AA)

            # 7. JPEG编码
            encode_params = [cv2.IMWRITE_JPEG_QUALITY, self.config['stream']['quality']]
            success, encoded_jpg = cv2.imencode('.jpg', processed_frame, encode_params)
            
            process_end_time = time.time()
            
            if success:
                # logger.info(f"[PERF] Cam {self.camera_id}: Frame processed in {(process_end_time - process_start_time)*1000:.2f} ms. Capture-to-encode delay: {(process_end_time - capture_time)*1000:.2f} ms.")
                return encoded_jpg.tobytes()
            else:
                logger.warning(f"Cam {self.camera_id}: JPEG encoding failed.")
                return None

        except Exception as e:
            logger.error(f"Frame processing failed for camera {self.camera_id}: {e}")
            return None
    
    def get_latest_frame(self) -> Optional[CameraFrame]:
        """获取最新帧"""
        with self._frame_lock:
            return self._latest_frame
    
    def get_camera_info(self) -> Dict[str, Any]:
        """获取摄像头信息"""
        info = {
            'camera_id': self.camera_id,
            'name': self.config['name'],
            'device_id': self.config['device_id'],
            'is_running': self.is_running,
            'capture_method': self.stats['capture_method'],
            'capture_config': self.config['capture'],
            'stream_config': self.config['stream'],
            'processing_config': self.config['processing'],
            'recording_config': self.config['recording'],
            'stats': self.stats.copy()
        }
        
        if self.cap and self.cap.isOpened():
            info['actual_width'] = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            info['actual_height'] = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            info['actual_fps'] = self.cap.get(cv2.CAP_PROP_FPS)
        
        return info

    def stop(self):
        """停止摄像头"""
        if self.is_recording:
            self.stop_recording()

        logger.info(f"Stopping camera {self.camera_id}...")
        self.is_running = False

        if self.capture_thread and self.capture_thread.is_alive():
            self.capture_thread.join(timeout=3)

        if self.cap:
            logger.info(f"Releasing VideoCapture object for camera {self.camera_id}")
            self.cap.release()
            self.cap = None

        with self._frame_lock:
            self._latest_frame = None
        
        logger.info(f"Camera {self.camera_id} stopped")

class UDPProtocol(asyncio.DatagramProtocol):
    """UDP协议处理器"""
    
    def __init__(self, gateway):
        self.gateway = gateway
    
    def connection_made(self, transport):
        self.gateway.transport = transport
        logger.info("UDP传输连接已建立")
    
    def datagram_received(self, data, addr):
        """接收到数据报"""
        if self.gateway.is_running:
            self.gateway.stats['packets_received'] += 1
            asyncio.create_task(self.gateway._process_packet(data, addr))
    
    def error_received(self, exc):
        logger.error(f"UDP传输错误: {exc}")
    
    def connection_lost(self, exc):
        if exc:
            logger.error(f"UDP连接丢失: {exc}")
        else:
            logger.info("UDP连接正常关闭")

class CameraGateway:
    """摄像头网关主类"""
    
    def __init__(self, port: int = 8991):
        self.port = port
        self.transport: Optional[asyncio.DatagramTransport] = None
        self.protocol = None
        self.is_running = False
        self.security_manager = SecurityManager(SHARED_SECRET_KEY)
        self.packet_manager = PacketManager()
        self.cameras: Dict[int, SmartCameraHandler] = {}
        self.active_clients: Dict[Tuple[str, int], Dict] = {}
        self.stats = {
            'packets_received': 0,
            'packets_sent': 0,
            'frames_sent': 0,
            'errors': 0
        }
        if DDS_ENABLED:
            self.head_state = {'yaw_deg': 0.0}
            self.head_state_lock = threading.Lock()
            self.dds_thread = threading.Thread(target=self._dds_subscriber_loop, daemon=True)
    
    def _dds_subscriber_loop(self):
        """DDS订阅循环"""
        logger.info("DDS subscriber thread started.")
        try:
            ChannelFactoryInitialize() 
            sub = ChannelSubscriber("HeadCommand", HeadCommand)
            sub.Init()
            logger.info("Successfully subscribed to DDS topic 'HeadCommand'.")
        except Exception as e:
            logger.error(f"Failed to initialize DDS subscriber: {e}. Head tracking is disabled.")
            return

        while self.is_running:
            try:
                msg = sub.Read(100)
                if msg:
                    with self.head_state_lock:
                        self.head_state['yaw_deg'] = msg.yaw_deg
            except Exception as e:
                logger.error(f"Error in DDS subscriber loop: {e}")
                time.sleep(1)
        
        logger.info("DDS subscriber thread stopped.")
    
    async def start(self):
        """启动网关服务"""
        loop = asyncio.get_running_loop()
        logger.info(f"正在启动摄像头网关，监听端口 {self.port}")

        if DDS_ENABLED:
            self.is_running = True
            self.dds_thread.start()

        try:
            self.transport, self.protocol = await loop.create_datagram_endpoint(
                lambda: UDPProtocol(self),
                local_addr=('0.0.0.0', self.port)
            )

            self.is_running = True
            logger.info("摄像头网关启动成功")

            await self._initialize_cameras()

            await asyncio.gather(
                self._stream_loop(),
                self._cleanup_loop(),
                self._stats_loop(),
                self._health_check_loop()
            )
        except Exception as e:
            logger.critical(f"启动失败: {e}", exc_info=True)
            raise
    
    async def _initialize_cameras(self):
        """初始化摄像头"""
        for camera_id, config in CAMERA_CONFIGS.items():
            try:
                if DDS_ENABLED:
                    camera = SmartCameraHandler(camera_id, config, self.head_state, self.head_state_lock, RECORDING_PATH)
                else:
                    camera = SmartCameraHandler(camera_id, config, {}, threading.Lock(), RECORDING_PATH)
                if await camera.start():
                    self.cameras[camera_id] = camera
                    logger.info(f"摄像头 {camera_id} ({config['name']}) 初始化成功")
                else:
                    logger.warning(f"摄像头 {camera_id} ({config['name']}) 初始化失败")
            except Exception as e:
                logger.error(f"摄像头 {camera_id} 初始化异常: {e}")
    
    async def _process_packet(self, data: bytes, addr: Tuple[str, int]):
        """处理数据包"""
        try:
            packet = self.packet_manager.process_received_packet(data, addr)
            if not packet:
                return
            
            await self._handle_request(packet, addr)
            
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"数据包处理失败: {e}")
    
    async def _handle_request(self, packet: Dict, addr: Tuple[str, int]):
        """处理客户端请求"""
        try:
            data = packet.get('data', {})
            request_type = data.get('request_type')
            
            if request_type == 'subscribe':
                await self._handle_subscribe(data, addr)
            elif request_type == 'unsubscribe':
                await self._handle_unsubscribe(data, addr)
            elif request_type == 'get_camera_list':
                await self._handle_get_camera_list(addr)
            elif request_type == 'capture_screenshot':
                await self._handle_capture_screenshot(data, addr)
            elif request_type == 'get_camera_info':
                await self._handle_get_camera_info(data, addr)
            else:
                logger.warning(f"未知请求类型: {request_type} from {addr}")
                
        except Exception as e:
            logger.error(f"请求处理失败: {e}")
    
    async def _handle_subscribe(self, data: Dict, addr: Tuple[str, int]):
        """处理订阅请求"""
        camera_ids = data.get('camera_ids', [])
        session_id = data.get('session_id', uuid.uuid4().hex)
        
        for cam_id in camera_ids:
            if cam_id in self.cameras:
                camera = self.cameras[cam_id]
                camera.subscriber_count += 1
                camera.start_recording()

        self.active_clients[addr] = {
            'session_id': session_id,
            'camera_ids': camera_ids,
            'last_activity': time.time()
        }
        
        logger.info(f"客户端 {addr} 订阅摄像头: {camera_ids} (会话ID: {session_id})")
        
        await self._send_response(addr, {
            'status': 'success',
            'message': 'subscription_confirmed',
            'session_id': session_id,
            'camera_ids': camera_ids
        })
    
    async def _handle_unsubscribe(self, data: Dict, addr: Tuple[str, int]):
        """处理取消订阅请求"""
        if addr in self.active_clients:
            subscribed_ids = self.active_clients[addr].get('camera_ids', [])
            for cam_id in subscribed_ids:
                if cam_id in self.cameras:
                    camera = self.cameras[cam_id]
                    camera.subscriber_count = max(0, camera.subscriber_count - 1)
                    if camera.subscriber_count == 0:
                        camera.stop_recording()
            del self.active_clients[addr]
            logger.info(f"客户端 {addr} 取消订阅")
        
        await self._send_response(addr, {
            'status': 'success',
            'message': 'unsubscribed'
        })
    
    async def _handle_get_camera_list(self, addr: Tuple[str, int]):
        """处理获取摄像头列表请求"""
        camera_list = []
        for camera_id, camera in self.cameras.items():
            config = CAMERA_CONFIGS[camera_id]
            camera_list.append({
                'camera_id': camera_id,
                'name': config['name'],
                'resolution': config['stream']['resolution'],  # 使用传输分辨率
                'fps': config['stream']['fps'],                # 使用传输帧率
                'is_active': camera.is_running,
                'capture_method': camera.stats.get('capture_method', 'unknown')
            })
        
        await self._send_response(addr, {
            'status': 'success',
            'message': 'camera_list',
            'cameras': camera_list
        })
    
    async def _handle_get_camera_info(self, data: Dict, addr: Tuple[str, int]):
        """处理获取摄像头详细信息请求"""
        camera_id = data.get('camera_id')
        
        if camera_id is None:
            camera_info = {}
            for cid, camera in self.cameras.items():
                camera_info[cid] = camera.get_camera_info()
        else:
            if camera_id not in self.cameras:
                await self._send_response(addr, {
                    'status': 'error', 
                    'message': 'camera_not_found'
                })
                return
            camera_info = {camera_id: self.cameras[camera_id].get_camera_info()}
        
        await self._send_response(addr, {
            'status': 'success',
            'message': 'camera_info',
            'camera_info': camera_info
        })
    
    async def _handle_capture_screenshot(self, data: Dict, addr: Tuple[str, int]):
        """处理截图请求"""
        camera_id = data.get('camera_id', 0)
        
        if camera_id not in self.cameras:
            await self._send_response(addr, {'status': 'error', 'message': 'camera_not_found'})
            return
        
        camera = self.cameras[camera_id]
        frame = camera.get_latest_frame()
        
        if frame:
            frame_base64 = base64.b64encode(frame.frame_data).decode('utf-8')
            await self._send_response(addr, {
                'status': 'success', 'message': 'screenshot_captured',
                'camera_id': camera_id, 'frame_id': frame.frame_id,
                'timestamp': frame.timestamp, 'resolution': frame.resolution,
                'data': frame_base64
            })
        else:
            await self._send_response(addr, {'status': 'error', 'message': 'no_frame_available'})
    
    async def _stream_loop(self):
        """视频流发送循环"""
        while self.is_running:
            try:
                if not self.active_clients:
                    await asyncio.sleep(0.1)
                    continue

                for addr, client_info in list(self.active_clients.items()):
                    await self._send_frames_to_client(addr, client_info)
                
                await asyncio.sleep(0.001)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"流发送循环失败: {e}")
                await asyncio.sleep(0.1)
    
    async def _send_frames_to_client(self, addr: Tuple[str, int], client_info: Dict):
        """向客户端发送视频帧"""
        client_info['last_activity'] = time.time()
        for camera_id in client_info['camera_ids']:
            if camera_id not in self.cameras: 
                continue
            
            camera = self.cameras[camera_id]
            frame = camera.get_latest_frame()
            
            if frame:
                await self._send_binary_frame(addr, frame)
                self.stats['frames_sent'] += 1
                camera.stats['frames_sent'] += 1
    
    async def _send_binary_frame(self, addr: Tuple[str, int], frame: CameraFrame):
        """发送二进制帧数据"""
        if not self.transport: 
            return
        try:
            send_time = time.time()
            # logger.info(f"[SEND] Sending frame {frame.frame_id} from Cam {frame.camera_id} to {addr}. Frame timestamp: {frame.timestamp:.3f}, Send-capture delay: {(send_time - frame.timestamp)*1000:.2f} ms")

            frame_header = struct.pack('!B Q HHHB', 
                0xFF,                               # Magic number
                int(frame.timestamp * 1000000),     # Microsecond timestamp
                frame.camera_id,                    # Camera ID
                frame.resolution[0],                # Width
                frame.resolution[1],                # Height
                frame.quality                       # Quality
            )
            
            frame_id_bytes = frame.frame_id.encode('ascii')[:8].ljust(8, b'\x00')
            data_length = struct.pack('!I', len(frame.frame_data))
            
            full_packet = frame_header + frame_id_bytes + data_length + frame.frame_data
            
            if len(full_packet) <= FRAGMENT_THRESHOLD:
                self.transport.sendto(full_packet, addr)
                self.stats['packets_sent'] += 1
            else:
                await self._send_fragmented_binary(addr, full_packet, frame.frame_id)
                
        except Exception as e:
            logger.error(f"发送二进制帧失败: {e}")
    
    async def _send_fragmented_binary(self, addr: Tuple[str, int], data: bytes, original_frame_id: str):
        """发送分片二进制数据"""
        if not self.transport: 
            return
        try:
            # Use the original frame_id as the fragment_id for better tracking
            fragment_id = original_frame_id.encode('ascii')
            chunk_size = FRAGMENT_THRESHOLD - 20
            total_fragments = (len(data) + chunk_size - 1) // chunk_size
            
            logger.info(f"[FRAG] Sending fragmented frame {original_frame_id} to {addr}. Total chunks: {total_fragments}")

            for i in range(total_fragments):
                chunk = data[i*chunk_size : (i+1)*chunk_size]
                fragment_header = struct.pack('!B8sHHH',
                    0xFE, fragment_id, i, total_fragments, len(chunk)
                )
                fragment_packet = fragment_header + chunk
                self.transport.sendto(fragment_packet, addr)
                self.stats['packets_sent'] += 1
                
        except Exception as e:
            logger.error(f"发送分片二进制数据失败: {e}")

    async def _send_response(self, addr: Tuple[str, int], response_data: Dict):
        """发送JSON响应"""
        if not self.transport: 
            return
        try:
            response_packet = self.packet_manager.prepare_packet(response_data, self.security_manager)
            self.transport.sendto(response_packet, addr)
            self.stats['packets_sent'] += 1
        except Exception as e:
            logger.error(f"发送响应失败: {e}")
    
    async def _cleanup_loop(self):
        """清理循环"""
        while self.is_running:
            await asyncio.sleep(60)
            try:
                current_time = time.time()
                expired_clients = [
                    addr for addr, client_info in self.active_clients.items()
                    if current_time - client_info['last_activity'] > SESSION_TIMEOUT
                ]
                for addr in expired_clients:
                    if addr in self.active_clients:
                        subscribed_ids = self.active_clients[addr].get('camera_ids', [])
                        for cam_id in subscribed_ids:
                            if cam_id in self.cameras:
                                camera = self.cameras[cam_id]
                                camera.subscriber_count = max(0, camera.subscriber_count - 1)
                                if camera.subscriber_count == 0:
                                    camera.stop_recording()
                        del self.active_clients[addr]
                        logger.info(f"清理过期客户端: {addr}")
                
                self.security_manager.cleanup_expired_sessions()
                self.packet_manager.cleanup_expired_fragments()
            except Exception as e:
                logger.error(f"清理任务失败: {e}")
    
    async def _stats_loop(self):
        """统计循环"""
        while self.is_running:
            await asyncio.sleep(30)
            try:
                logger.info(f"网关统计: {self.stats}")
                for cid, cam in self.cameras.items():
                    logger.info(f"摄像头 {cid} 统计: {cam.stats}")
                    # 重置计数器
                    cam.stats['frames_captured'] = 0
                    cam.stats['frames_dropped'] = 0
                    cam.stats['frames_sent'] = 0
            except Exception as e:
                logger.error(f"统计任务失败: {e}")
    
    async def _health_check_loop(self):
        """健康检查循环"""
        while self.is_running:
            await asyncio.sleep(120)
            try:
                for camera_id, camera in list(self.cameras.items()):
                    if not camera.is_running:
                        logger.warning(f"摄像头 {camera_id} 已停止，尝试重启...")
                        await camera.start()
                    elif camera.capture_thread and not camera.capture_thread.is_alive():
                        logger.warning(f"摄像头 {camera_id} 捕获线程已停止，尝试重启...")
                        camera.stop()
                        await asyncio.sleep(2)
                        await camera.start()
            except Exception as e:
                logger.error(f"健康检查失败: {e}")
    
    async def stop(self):
        """停止网关服务"""
        if not self.is_running: 
            return
        self.is_running = False
        logger.info("正在停止网关服务...")

        if DDS_ENABLED and self.dds_thread.is_alive():
            self.dds_thread.join(timeout=2)
        
        for camera in self.cameras.values():
            camera.stop()
        
        if self.transport:
            self.transport.close()
        
        await asyncio.sleep(1)
        logger.info("摄像头网关已停止")

async def main():
    gateway = CameraGateway()
    
    try:
        await gateway.start()
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在停止...")
    finally:
        await gateway.stop()

if __name__ == "__main__":
    asyncio.run(main())
