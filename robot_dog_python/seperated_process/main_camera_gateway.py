#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
优化版实时UDP摄像头网关 (v4 - CSI Video Stream Support)
端口：本地8991，FRP远程58991
功能：多摄像头管理、实时视频流传输、性能优化、CSI视频流支持
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

# <--- ADDED START: Head Tracking Configuration --->
# This is the full horizontal Field of View (FOV) of your camera in degrees.
# You will need to TUNE THIS VALUE experimentally.
# A common value for robot cameras is between 90 and 120 degrees.
# How to tune:
# 1. Command the head to its maximum right position (e.g., +90 degrees).
# 2. Adjust this FOV value until the marker appears at the far right edge of the screen.
CAMERA_HORIZONTAL_FOV_DEG = 90.0

# This is the maximum yaw angle for the head motor, as defined in your head control script.
HEAD_MAX_YAW_DEG = 90.0
# <--- ADDED END --->
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
SESSION_TIMEOUT = 3000  # 50分钟会话超时
MAX_UDP_SIZE = 8192  # 增大UDP包大小，减少分片
FRAGMENT_THRESHOLD = 1400  # 分片阈值提高
HEADER_SIZE = 32  # 减小头部大小

# 摄像头配置 - 优化性能
CAMERA_CONFIGS = {
    0: {
        "type": "csi",
        "resolution": (480, 320),
        "fps": 10,
        "quality": 20,
        "name": "CSI-0-R",
        "sensor_id": 0,
        "enable_recording": False,  # 添加录制开关

        "flip_method": "both",

        "crop_params": {
            "top": 48,      # Pixels to remove from the top
            "bottom": 48,   # Pixels to remove from the bottom
            "left": 72,    # Pixels to remove from the left
            "right": 72    # Pixels to remove from the right
        },
        
        "is_fisheye": True,
        "undistorted_resolution": (480, 320), # Desired output size
        "fisheye_params": {
            'mappingCoeffs': np.array([4.093337128000973e+02,-8.756678171982792e-04,1.333600250402446e-07,-6.812123301267790e-10]), # a0, a2, a3, a4. Placeholder - adjust for this camera
            'imageSize': np.array([320, 480]),  # rows, cols. Note the order
            'distortionCenter': np.array([240.0, 160.0]), # Placeholder - adjust for this camera
            'stretchMatrix': np.array([[1.5, 0.0], [0.0, 1.5]]),
            'undistorted_fov_deg': 110.0 # Optional: control output FOV
        }
    },
    1: {
        "type": "csi",
        "resolution": (480, 320),
        "fps": 10,
        "quality": 20,
        "name": "CSI-1-L",
        "sensor_id": 1,
        "enable_recording": False,  # 添加录制开关

        "flip_method": "both",

        "crop_params": {
            "top": 48,      # Pixels to remove from the top
            "bottom": 48,   # Pixels to remove from the bottom
            "left": 72,    # Pixels to remove from the left
            "right": 72    # Pixels to remove from the right
        },

        "is_fisheye": True,
        "undistorted_resolution": (480, 320), # Desired output size
        "fisheye_params": {
            'mappingCoeffs': np.array([411.0715,-0.00081114,0.0,0.0]), # a0, a2, a3, a4
            'imageSize': np.array([320, 480]),  # rows, cols. Note the order
            'distortionCenter': np.array([240.0, 160.0]), # Placeholder - adjust for this camera
            'stretchMatrix': np.array([[1.5, 0.0], [0.0, 1.5]]),
            'undistorted_fov_deg': 110.0 # Optional: control output FOV
        }
    },
    2: {
        "type": "usb",
        "resolution": (640, 480),
        "fps": 15,
        "quality": 50,
        "name": "USB-2",
        "enable_recording": True,  # 只录制USB摄像头

        "flip_method": "both",

        "is_fisheye": True,
        "undistorted_resolution": (640, 480), # Desired output size
        "fisheye_params": {
            'mappingCoeffs': np.array([272.428,-0.002384499,0.0,0.0]), # a0, a2, a3, a4
            'imageSize': np.array([480, 640]),  # rows, cols
            'distortionCenter': np.array([328.71590201,234.40496395759]), # cx (horizontal), cy (vertical)
            'stretchMatrix': np.array([[1.0, 0.0], [0.0, 1.0]]),
            'undistorted_fov_deg': 110.0 # Optional: control output FOV
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

class CSIVideoStreamer:
    """CSI摄像头视频流处理器 - 使用持续的GStreamer管道"""
    
    def __init__(self, sensor_id=0, width=1280, height=720, fps=15):
        self.sensor_id = sensor_id
        self.width = width
        self.height = height
        self.fps = fps
        self.process = None
        self.is_running = False
        self.frame_queue = Queue(maxsize=2)
        self.read_thread = None
        self.temp_fifo = f"/tmp/csi_fifo_{sensor_id}"
        
    def _create_gstreamer_command(self) -> List[str]:
        """创建GStreamer命令行"""
        return [
            "gst-launch-1.0",
            "nvarguscamerasrc",
            f"sensor-id={self.sensor_id}",
            "!",
            f"video/x-raw(memory:NVMM),width={self.width},height={self.height},framerate={self.fps}/1",
            "!",
            "nvvidconv",
            "!",
            "video/x-raw,format=BGR",
            "!",
            "videoconvert",
            "!",
            "jpegenc",
            f"quality={85}",
            "!",
            "multifilesink",
            f"location={self.temp_fifo}_%d.jpg",
            "max-files=1",
            "next-file=4"  # 每个缓冲区后切换到下一个文件
        ]
    
    def _create_gstreamer_stdout_command(self) -> List[str]:
        """创建输出到stdout的GStreamer命令"""
        return [
            "gst-launch-1.0",
            "nvarguscamerasrc",
            f"sensor-id={self.sensor_id}",
            "!",
            f"video/x-raw(memory:NVMM),width={self.width},height={self.height},framerate={self.fps}/1",
            "!",
            "nvvidconv",
            "!",
            "video/x-raw,format=BGR",
            "!",
            "videoconvert",
            "!",
            "jpegenc",
            f"quality={85}",
            "!",
            "fdsink",
            "fd=1"
        ]
    
    def _create_opencv_compatible_command(self) -> List[str]:
        """创建与OpenCV兼容的管道命令（输出原始视频流）"""
        return [
            "gst-launch-1.0",
            "nvarguscamerasrc",
            f"sensor-id={self.sensor_id}",
            "!",
            f"video/x-raw(memory:NVMM),width={self.width},height={self.height},framerate={self.fps}/1",
            "!",
            "nvvidconv",
            "!",
            "video/x-raw,format=BGR",
            "!",
            "videoconvert",
            "!",
            "video/x-raw,format=BGR",
            "!",
            "appsink",
            "drop=1",
            "max-buffers=2"
        ]
    
    def start_stream_method1(self) -> bool:
        """方法1：使用文件输出方式"""
        try:
            # 清理旧的临时文件
            for i in range(10):
                temp_file = f"{self.temp_fifo}_{i}.jpg"
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            
            cmd = self._create_gstreamer_command()
            logger.info(f"启动CSI流（方法1）: {' '.join(cmd)}")
            
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid
            )
            
            self.is_running = True
            self.read_thread = threading.Thread(target=self._read_files_loop, daemon=True)
            self.read_thread.start()
            
            # 等待第一帧
            time.sleep(2)
            return self.test_capture()
            
        except Exception as e:
            logger.error(f"CSI流启动失败（方法1）: {e}")
            return False
    
    def start_stream_method2(self) -> bool:
        """方法2：使用stdout管道方式"""
        try:
            cmd = self._create_gstreamer_stdout_command()
            logger.info(f"启动CSI流（方法2）: {' '.join(cmd)}")
            
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0,
                preexec_fn=os.setsid
            )
            
            self.is_running = True
            self.read_thread = threading.Thread(target=self._read_stdout_loop, daemon=True)
            self.read_thread.start()
            
            # 等待第一帧
            time.sleep(2)
            return self.test_capture()
            
        except Exception as e:
            logger.error(f"CSI流启动失败（方法2）: {e}")
            return False
    
    def start_stream(self) -> bool:
        """启动视频流 - 尝试不同方法"""
        # 首先尝试方法1（文件方式）
        if self.start_stream_method1():
            logger.info(f"CSI-{self.sensor_id} 使用文件方式启动成功")
            return True
        
        # 如果方法1失败，清理并尝试方法2
        self.stop_stream()
        time.sleep(1)
        
        if self.start_stream_method2():
            logger.info(f"CSI-{self.sensor_id} 使用管道方式启动成功")
            return True
        
        logger.error(f"CSI-{self.sensor_id} 所有方法都失败")
        return False
    
    def _read_files_loop(self):
        """文件读取循环"""
        frame_counter = 0
        last_file_time = 0
        
        while self.is_running:
            try:
                current_file = f"{self.temp_fifo}_{frame_counter % 10}.jpg"
                
                if os.path.exists(current_file):
                    # 检查文件是否更新
                    file_time = os.path.getmtime(current_file)
                    if file_time > last_file_time:
                        # 读取图像
                        try:
                            frame = cv2.imread(current_file)
                            if frame is not None:
                                timestamp = time.time()
                                
                                # 放入队列
                                if self.frame_queue.full():
                                    try:
                                        self.frame_queue.get_nowait()
                                    except Empty:
                                        pass
                                
                                try:
                                    self.frame_queue.put_nowait((frame, timestamp))
                                except Full:
                                    pass
                                
                                last_file_time = file_time
                        except Exception as e:
                            logger.debug(f"读取图像文件失败: {e}")
                
                frame_counter = (frame_counter + 1) % 10
                time.sleep(1.0 / (self.fps * 2))  # 轮询频率
                
            except Exception as e:
                logger.error(f"文件读取循环异常: {e}")
                time.sleep(0.1)
    
    def _read_stdout_loop(self):
        """stdout读取循环（JPEG流解析）"""
        buffer = b''
        jpeg_start = b'\xff\xd8'
        jpeg_end = b'\xff\xd9'
        
        while self.is_running:
            try:
                if self.process and self.process.stdout:
                    chunk = self.process.stdout.read(8192)
                    if not chunk:
                        break
                    
                    buffer += chunk
                    
                    # 查找完整的JPEG图像
                    while True:
                        start_pos = buffer.find(jpeg_start)
                        if start_pos == -1:
                            break
                        
                        end_pos = buffer.find(jpeg_end, start_pos + 2)
                        if end_pos == -1:
                            break
                        
                        # 提取JPEG数据
                        jpeg_data = buffer[start_pos:end_pos + 2]
                        buffer = buffer[end_pos + 2:]
                        
                        # 解码图像
                        try:
                            nparr = np.frombuffer(jpeg_data, np.uint8)
                            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                            
                            if frame is not None:
                                timestamp = time.time()
                                
                                # 放入队列
                                if self.frame_queue.full():
                                    try:
                                        self.frame_queue.get_nowait()
                                    except Empty:
                                        pass
                                
                                try:
                                    self.frame_queue.put_nowait((frame, timestamp))
                                except Full:
                                    pass
                        except Exception as e:
                            logger.debug(f"JPEG解码失败: {e}")
                
            except Exception as e:
                logger.error(f"stdout读取异常: {e}")
                time.sleep(0.1)
    
    def capture_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        """捕获一帧"""
        try:
            frame_data = self.frame_queue.get_nowait()
            return True, frame_data[0]
        except Empty:
            return False, None
    
    def test_capture(self) -> bool:
        """测试捕获功能"""
        for _ in range(10):  # 尝试10次
            ret, frame = self.capture_frame()
            if ret and frame is not None:
                logger.info(f"CSI-{self.sensor_id} 视频流测试成功: {frame.shape}")
                return True
            time.sleep(0.1)
        
        logger.error(f"CSI-{self.sensor_id} 视频流测试失败")
        return False
    
    def stop_stream(self):
        """停止视频流"""
        self.is_running = False
        
        if self.read_thread:
            self.read_thread.join(timeout=3)
        
        if self.process:
            try:
                # 发送SIGTERM给进程组
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
                self.process.wait(timeout=5)
            except (subprocess.TimeoutExpired, ProcessLookupError, OSError):
                try:
                    # 如果SIGTERM不行，使用SIGKILL
                    os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
                except (ProcessLookupError, OSError):
                    pass
            finally:
                self.process = None
        
        # 清理临时文件
        for i in range(10):
            temp_file = f"{self.temp_fifo}_{i}.jpg"
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except:
                pass
        
        # 清空队列
        while not self.frame_queue.empty():
            try:
                self.frame_queue.get_nowait()
            except Empty:
                break

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
    """智能摄像头处理器 (v2 - Streamlined Initialization)"""

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
        self.subscriber_count = 0  # Track number of active subscribers
        self.output_dir = RECORDING_PATH
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

        # <--- ADDED: Store reference to shared state --->
        self.head_state = head_state
        self.head_state_lock = head_state_lock
        # <--- END OF ADDED BLOCK --->

        self.corrector: Optional[FisheyeCorrector] = None 

        if self.config.get("is_fisheye", False):
            try:
                self.corrector = FisheyeCorrector(self.config)
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

    def start_recording(self):
        """Starts recording if not already in progress with robust error handling."""
        # 检查是否启用录制
        if not self.config.get('enable_recording', False):
            return  # 录制未启用
            
        if self.is_recording:
            return  # Already recording, do nothing

        # --- Start Recording with robust initialization ---
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        cam_name = self.config.get('name', f'cam{self.camera_id}').replace(" ", "_")
        output_filename = os.path.join(self.output_dir, f"{cam_name}_{timestamp}.mp4")

        # Determine correct resolution after potential cropping
        if self.corrector:
            width, height = self.config['undistorted_resolution']
        else:
            width, height = self.config['resolution']

        if 'crop_params' in self.config:
            params = self.config['crop_params']
            width -= (params.get('left', 0) + params.get('right', 0))
            height -= (params.get('top', 0) + params.get('bottom', 0))

        fps = self.config.get('fps', 15)
        
        # 尝试多种编码器以提高兼容性
        codecs_to_try = [
            ('XVID', cv2.VideoWriter_fourcc(*'XVID')),  # 更兼容的编码器
            ('mp4v', cv2.VideoWriter_fourcc(*'mp4v')),  # 原始编码器
            ('H264', cv2.VideoWriter_fourcc(*'H264')),  # H264编码器
            ('MJPG', cv2.VideoWriter_fourcc(*'MJPG')),  # MJPEG编码器（最兼容）
        ]
        
        self.video_writer = None
        self.current_output_file = output_filename
        
        for codec_name, fourcc in codecs_to_try:
            try:
                # 确保输出目录存在
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
        """Stops recording if in progress with robust cleanup."""
        if not self.is_recording:
            return # Not recording, do nothing

        self.is_recording = False
        
        if self.video_writer:
            try:
                # 安全释放视频写入器
                self.video_writer.release()
                logger.info(f"Camera {self.camera_id}: Recording stopped. Stats: {getattr(self, 'recording_stats', {})}")
                
                # 检查文件是否成功创建
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

    def _get_csi_gstreamer_pipeline(self, sensor_id, width, height, fps, flip=0) -> str:
        """
        Returns a robust GStreamer pipeline string for OpenCV to consume CSI camera frames.
        This pipeline is built for headless operation on NVIDIA Jetson.
        """
        # --- MORE ROBUST GStreamer Pipeline ---
        # Your observation about redder edges points to a lens shading issue.
        # This version adds 'lsc-mode=1' to enable automatic Lens Shading Correction.
        # Combining auto white balance ('wbmode=1') and auto LSC ('lsc-mode=1') is the
        # most robust way to ensure uniform, accurate color across the entire image.
        pipeline = (
            f"nvarguscamerasrc sensor-id={sensor_id} wbmode=1 lsc-mode=2 ! "
            f"video/x-raw(memory:NVMM), width=(int){width}, height=(int){height}, format=(string)NV12, framerate=(fraction){fps}/1 ! "
            f"nvvidconv flip-method={flip} ! "
            f"video/x-raw, width=(int){width}, height=(int){height}, format=(string)BGRx ! "
            f"videoconvert ! "
            f"video/x-raw, format=(string)BGR ! appsink drop=true max-buffers=1"
        )
        logger.info(f"Generated GStreamer pipeline for CSI-{sensor_id}: {pipeline}")
        return pipeline

    def _try_csi_camera(self) -> bool:
        """Initializes a CSI camera using a GStreamer pipeline with OpenCV."""
        try:
            sensor_id = self.config.get('sensor_id', self.camera_id)
            width, height = self.config['resolution']
            fps = self.config['fps']

            # Check if nvargus-daemon is running, which is crucial
            try:
                subprocess.run(['pgrep', 'nvargus-daemon'], check=True, capture_output=True)
            except (subprocess.CalledProcessError, FileNotFoundError):
                logger.warning("nvargus-daemon is not running. Attempting to start it.")
                # This might require passwordless sudo setup for the user
                try:
                    subprocess.run(['sudo', 'systemctl', 'restart', 'nvargus-daemon'], check=True, timeout=10)
                    time.sleep(3) # Give the daemon time to start
                    logger.info("nvargus-daemon restarted successfully.")
                except Exception as e:
                    logger.error(f"Failed to start nvargus-daemon: {e}. CSI camera will likely fail.")
                    return False

            pipeline = self._get_csi_gstreamer_pipeline(sensor_id, width, height, fps)
            
            # Use cv2.CAP_GSTREAMER to be explicit
            self.cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)

            if not self.cap or not self.cap.isOpened():
                logger.error(f"CSI Camera {self.camera_id} failed to open with VideoCapture.")
                # Provide the test command for easy debugging
                test_cmd = f"gst-launch-1.0 {pipeline.replace('appsink drop=true max-buffers=1', 'fakesink -v')}"
                logger.error(f"Please test this command in your terminal: \n{test_cmd}")
                return False

            # Test by reading a single frame
            ret, frame = self.cap.read()
            if not ret or frame is None:
                logger.error(f"CSI Camera {self.camera_id} opened but could not read a frame.")
                self.cap.release()
                return False

            logger.info(f"CSI Camera {self.camera_id} initialized successfully. Frame resolution: {frame.shape}")
            self.stats['capture_method'] = 'csi_opencv'
            return True

        except Exception as e:
            logger.error(f"Exception during CSI camera initialization for ID {self.camera_id}: {e}", exc_info=True)
            return False

    def _try_usb_camera(self) -> bool:
        """Initializes a standard USB camera."""
        try:
            logger.info(f"Initializing USB camera at index {self.camera_id} (/dev/video{self.camera_id})")
            
            # Be explicit with the backend
            self.cap = cv2.VideoCapture(self.camera_id, cv2.CAP_V4L2)

            if not self.cap or not self.cap.isOpened():
                logger.error(f"USB Camera {self.camera_id} failed to open.")
                return False

            width, height = self.config['resolution']
            fps = self.config['fps']
            
            # Set desired properties
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            self.cap.set(cv2.CAP_PROP_FPS, fps)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1) # Reduce latency

            # Verify by reading a frame
            ret, frame = self.cap.read()
            if not ret or frame is None:
                logger.error(f"USB Camera {self.camera_id} opened but could not read a frame.")
                self.cap.release()
                return False
            
            actual_w = self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
            actual_h = self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
            logger.info(f"USB Camera {self.camera_id} initialized successfully. Frame resolution: {frame.shape}, Actual V4L2 geometry: {actual_w}x{actual_h}")
            self.stats['capture_method'] = 'usb_opencv'
            return True

        except Exception as e:
            logger.error(f"Exception during USB camera initialization for ID {self.camera_id}: {e}", exc_info=True)
            return False


    async def start(self) -> bool:
        """Starts the camera based on its configured type."""
        cam_type = self.config.get("type", "usb").lower()
        success = False

        if cam_type == "csi":
            success = self._try_csi_camera()
        elif cam_type == "usb":
            success = self._try_usb_camera()
        else:
            logger.error(f"Unsupported camera type '{cam_type}' for camera ID {self.camera_id}")
            return False

        if not success:
            logger.error(f"All initialization attempts failed for camera {self.camera_id} ({self.config['name']})")
            return False

        self.is_running = True
        self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.capture_thread.start()
        
        logger.info(f"Camera {self.camera_id} ({self.config['name']}) started successfully using method: {self.stats['capture_method']}")
        return True

    def _capture_loop(self):
        """Camera capture loop with detailed performance timing."""
        if not self.cap:
                logger.error(f"Capture loop for camera {self.camera_id} started without a valid VideoCapture object.")
                return
                
        frame_interval = 1.0 / self.config['fps']
        consecutive_failures = 0
        max_failures = 30
        
        logger.info(f"Camera {self.camera_id} capture loop starting with target interval {frame_interval:.3f}s")

        while self.is_running:
            # --- Timing logic starts here ---
            t_loop_start = time.perf_counter()

            # 1. Measure frame capture time
            ret, frame = self.cap.read()
            t_capture_done = time.perf_counter()

            if not ret or frame is None:
                consecutive_failures += 1
                logger.warning(f"Failed to read frame from camera {self.camera_id}. Failure count: {consecutive_failures}")
                if consecutive_failures > max_failures:
                    logger.error(f"Camera {self.camera_id} exceeded max consecutive read failures. Stopping capture thread.")
                    self.is_running = False
                    break
                time.sleep(0.1)
                continue
            
            consecutive_failures = 0
            self.stats['last_capture_time'] = time.time()
            self.stats['frames_captured'] += 1

            # 2. Measure frame processing time (correction, encoding, etc.)
            jpg_bytes = self._process_frame(frame)
            t_process_done = time.perf_counter()
            
            if jpg_bytes:
                cam_frame = CameraFrame(
                    camera_id=self.camera_id,
                    frame_data=jpg_bytes,
                    timestamp=self.stats['last_capture_time'],
                    frame_id=uuid.uuid4().hex[:8],
                    resolution=(frame.shape[1], frame.shape[0]),
                    quality=self.config['quality']
                )

                with self._frame_lock:
                    self._latest_frame = cam_frame
        
        logger.warning(f"Capture loop for camera {self.camera_id} has exited.")


    def _process_frame(self, frame: np.ndarray) -> Optional[bytes]:
        """Processes the frame (resize if needed and JPEG encode)."""
        try:
            # --- ADD THIS BLOCK TO CHECK RESOLUTION ---
            if frame is not None:
                # The .shape attribute gives (height, width, color_channels)
                height, width, _ = frame.shape
                # logger.info(f"Camera {self.camera_id}: Captured raw frame with resolution {width}x{height}")
            # --- END OF BLOCK ---
            # --- ADD THIS BLOCK for correction ---
            # 1. Apply fisheye correction if a corrector exists
            if self.corrector:
                corrected_frame = self.corrector.correct(frame)
            else:
                corrected_frame = frame
            # --- END OF ADDED BLOCK ---

            # --- Stage 2: Cropping Stage ---
            # Check if crop parameters are defined for this camera
            if 'crop_params' in self.config:
                params = self.config['crop_params']
                h, w, _ = corrected_frame.shape

                # Get crop values, defaulting to 0 if not specified
                top, bottom = params.get('top', 0), params.get('bottom', 0)
                left, right = params.get('left', 0), params.get('right', 0)
                
                # Sanity check to prevent cropping more than the image size
                if (top + bottom < h) and (left + right < w):
                    # Use NumPy slicing to crop the image
                    cropped_frame = corrected_frame[top:h-bottom, left:w-right]
                    # logger.info(f"Cam {self.camera_id}: Cropped frame from {w}x{h} to {cropped_frame.shape[1]}x{cropped_frame.shape[0]}")
                else:
                    logger.warning(f"Cam {self.camera_id}: Invalid crop values, skipping crop.")
                    cropped_frame = corrected_frame
            else:
                # If no crop_params, just pass the corrected frame through
                cropped_frame = corrected_frame
            # --- End of Cropping Stage ---

            # 2. Determine target size for encoding
            if self.corrector:
                target_width, target_height = self.config['undistorted_resolution']
            else:
                target_width, target_height = self.config['resolution']

            # 3. Resize if the corrected/original frame doesn't match the final target size
            if cropped_frame.shape[1] != target_width or cropped_frame.shape[0] != target_height:
                final_frame = cv2.resize(cropped_frame, (target_width, target_height), interpolation=cv2.INTER_AREA)
            else:
                final_frame = cropped_frame

            if self.config.get('type') == 'csi':

                final_frame = gray_world_awb(final_frame)
                # 空间校色
                final_frame = radial_color_correction_v2(final_frame, g_center=0.92, g_edge=1.09, r_center=1.03, r_edge=0.89)
                # 提升整体亮度
                final_frame = np.clip(final_frame * 1.18, 0, 255).astype(np.uint8)
                # 加点红/绿
                b, g, r = cv2.split(final_frame)
                b = np.clip(b * 0.98, 0, 255).astype(np.uint8)
                g = np.clip(g * 1.0, 0, 255).astype(np.uint8)
                r = np.clip(r * 1.07, 0, 255).astype(np.uint8)
                final_frame = cv2.merge([b, g, r])

            # 安全的视频写入，带错误处理
            if self.is_recording and self.video_writer:
                try:
                    # 验证帧数据有效性
                    if final_frame is not None and final_frame.size > 0:
                        # 确保帧尺寸正确
                        expected_height, expected_width = final_frame.shape[:2]
                        if hasattr(self, 'recording_stats'):
                            # 写入帧到视频文件
                            self.video_writer.write(final_frame)
                            self.recording_stats['frames_written'] += 1
                            self.recording_stats['last_write_time'] = time.time()
                        else:
                            # 如果没有统计信息，直接写入
                            self.video_writer.write(final_frame)
                    else:
                        if hasattr(self, 'recording_stats'):
                            self.recording_stats['write_errors'] += 1
                        logger.warning(f"Camera {self.camera_id}: Invalid frame data for recording")
                        
                except Exception as e:
                    if hasattr(self, 'recording_stats'):
                        self.recording_stats['write_errors'] += 1
                    logger.error(f"Camera {self.camera_id}: Video write error: {e}")
                    
                    # 如果写入错误过多，停止录制以避免进一步问题
                    if hasattr(self, 'recording_stats') and self.recording_stats['write_errors'] > 10:
                        logger.error(f"Camera {self.camera_id}: Too many write errors, stopping recording")
                        self.stop_recording()

                # <--- ADDED START: Draw Head Direction Marker --->
            if DDS_ENABLED:
                current_yaw = 0.0
                with self.head_state_lock:
                    current_yaw = self.head_state.get('yaw_deg', 0.0)

                # Get frame dimensions
                h, w, _ = final_frame.shape
                center_x = w // 2

                # Map the yaw angle to a pixel coordinate on the screen
                # The angle is normalized from -1 to 1 based on the camera's FOV
                # Clamp the angle to prevent the marker from going way off-screen
                clamped_yaw = max(-HEAD_MAX_YAW_DEG, min(current_yaw, HEAD_MAX_YAW_DEG))
                angle_ratio = clamped_yaw / (CAMERA_HORIZONTAL_FOV_DEG / 2.0)
                
                # Calculate the marker's x position
                marker_x = int(center_x + (angle_ratio * center_x))
                marker_x = max(0, min(marker_x, w - 1)) # Clamp to screen bounds

                # Draw an arrowed line as the marker
                # Points from the top-center downwards to the calculated x position
                marker_start_pt = (marker_x, 0)
                marker_end_pt = (marker_x, 20)
                cv2.arrowedLine(final_frame, marker_start_pt, marker_end_pt, (0, 0, 255), 2, cv2.LINE_AA)
            # <--- ADDED END --->


            # 4. JPEG Encode the final frame
            encode_params = [cv2.IMWRITE_JPEG_QUALITY, self.config['quality']]
            success, encoded_jpg = cv2.imencode('.jpg', final_frame, encode_params)

            return encoded_jpg.tobytes() if success else None
        except Exception as e:
            logger.error(f"Frame processing failed for camera {self.camera_id}: {e}")
            return None
    
    # ... keep get_latest_frame and get_camera_info methods as they are ...
    def get_latest_frame(self) -> Optional[CameraFrame]:
        """Gets the most recent frame, non-blocking."""
        with self._frame_lock:
            # Return the frame and immediately clear it so it's not sent twice
            frame = self._latest_frame
            self._latest_frame = None 
            return frame
    
    def get_camera_info(self) -> Dict[str, Any]:
        """获取摄像头信息"""
        info = {
            'camera_id': self.camera_id,
            'name': self.config['name'],
            'type': self.config['type'],
            'is_running': self.is_running,
            'capture_method': self.stats['capture_method'],
            'stats': self.stats.copy()
        }
        
        if self.cap and self.cap.isOpened():
            info['actual_width'] = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            info['actual_height'] = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            info['actual_fps'] = self.cap.get(cv2.CAP_PROP_FPS)
        
        return info

    def stop(self):
        """Stops the camera and releases resources."""
        if self.is_recording:
            self.stop_recording() # This will properly stop and release the writer

        logger.info(f"Stopping camera {self.camera_id}...")
        self.is_running = False

        if self.capture_thread and self.capture_thread.is_alive():
            self.capture_thread.join(timeout=3)

        if self.cap:
            logger.info(f"Releasing VideoCapture object for camera {self.camera_id}.")
            self.cap.release()
            self.cap = None

        with self._frame_lock:
            self._latest_frame = None
        
        logger.info(f"Camera {self.camera_id} stopped.")


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
        # <--- ADDED START: DDS State and Thread Management --->
        if DDS_ENABLED:
            self.head_state = {'yaw_deg': 0.0} # Shared dictionary for head angle
            self.head_state_lock = threading.Lock()
            self.dds_thread = threading.Thread(target=self._dds_subscriber_loop, daemon=True)
        # <--- ADDED END --->
    
    def _dds_subscriber_loop(self):
        """A dedicated thread to listen for DDS HeadCommand messages."""
        logger.info("DDS subscriber thread started.")
        # NOTE: You might need to specify your network interface here
        # Example: ChannelFactoryInitialize(networkInterface="eth0")
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
                msg = sub.Read(100) # Read with a 100ms timeout
                if msg:
                    with self.head_state_lock:
                        self.head_state['yaw_deg'] = msg.yaw_deg
                    # logger.debug(f"Received head yaw: {msg.yaw_deg:.2f}°")
            except Exception as e:
                logger.error(f"Error in DDS subscriber loop: {e}")
                time.sleep(1) # Avoid spamming errors
        
        # sub.Close() # Proper cleanup
        logger.info("DDS subscriber thread stopped.")
    
    async def start(self):
        """启动网关服务"""
        loop = asyncio.get_running_loop()
        logger.info(f"正在启动摄像头网关，监听端口 {self.port}")

        if DDS_ENABLED:
            self.is_running = True # Set running flag before starting thread
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
        for camera_id, config in CAMERA_CONFIGS.items(): #
            try:
                if DDS_ENABLED: #
                    # --- MODIFIED TO PASS THE PATH ---
                    camera = SmartCameraHandler(camera_id, config, self.head_state, self.head_state_lock, RECORDING_PATH) #
                else:
                    # Pass dummy data if DDS is disabled
                    camera = SmartCameraHandler(camera_id, config, {}, threading.Lock(), RECORDING_PATH) #
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
                camera.start_recording() # This will only start if it's not already running

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
                    camera.subscriber_count = max(0, camera.subscriber_count - 1) # Prevent going below zero
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
                'resolution': config['resolution'],
                'fps': config['fps'],
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
            # 返回所有摄像头信息
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
                await self._send_fragmented_binary(addr, full_packet)
                
        except Exception as e:
            logger.error(f"发送二进制帧失败: {e}")
    
    async def _send_fragmented_binary(self, addr: Tuple[str, int], data: bytes):
        """发送分片二进制数据"""
        if not self.transport: 
            return
        try:
            fragment_id = uuid.uuid4().hex[:8].encode('ascii')
            chunk_size = FRAGMENT_THRESHOLD - 20
            total_fragments = (len(data) + chunk_size - 1) // chunk_size
            
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
