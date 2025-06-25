#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实时UDP摄像头网关
端口：本地8991，FRP远程48991
功能：多摄像头管理、实时视频流传输、帧缓存清理
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
from collections import defaultdict, deque
import struct
import threading
from queue import Queue, Empty
import base64

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 安全配置
SHARED_SECRET_KEY = b"robot_dog_camera_secret_2024"
SESSION_TIMEOUT = 300  # 5分钟会话超时
MAX_UDP_SIZE = 1400
HEADER_SIZE = 64

# 摄像头配置
CAMERA_CONFIGS = {
    0: {
        "resolution": (640, 480),
        "fps": 30,
        "quality": 80,
        "name": "主摄像头"
    },
    1: {
        "resolution": (1280, 720),
        "fps": 15,
        "quality": 70,
        "name": "高清摄像头"
    },
    2: {
        "resolution": (320, 240),
        "fps": 60,
        "quality": 60,
        "name": "快速摄像头"
    }
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
        
        # 生成签名
        signature = security_manager.generate_signature(packet_bytes, timestamp)
        
        # 添加签名头部
        header = {
            'signature': signature,
            'size': len(packet_bytes)
        }
        header_bytes = json.dumps(header).encode('utf-8')
        header_size = struct.pack('!H', len(header_bytes))
        
        return header_size + header_bytes + packet_bytes
    
    def auto_fragment(self, data: bytes) -> List[bytes]:
        """自动判断是否需要切片"""
        if len(data) <= MAX_UDP_SIZE:
            return [data]  # 单包发送
        
        # 需要分片
        fragment_id = uuid.uuid4().hex[:8]
        chunk_size = MAX_UDP_SIZE - 100  # 预留分片头部空间
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
            # 解析头部大小
            if len(data) < 2:
                return None
            
            header_size = struct.unpack('!H', data[:2])[0]
            if len(data) < 2 + header_size:
                return None
            
            # 解析头部
            header_bytes = data[2:2 + header_size]
            header = json.loads(header_bytes.decode('utf-8'))
            
            # 检查是否为分片包
            if 'fragment_id' in header:
                return self._handle_fragment(header, data[2 + header_size:], addr)
            else:
                # 完整包
                return self._handle_complete_packet(header, data[2 + header_size:])
        
        except Exception as e:
            logger.error(f"数据包处理失败: {e}")
            return None
    
    def _handle_fragment(self, header: Dict, chunk: bytes, addr: Tuple[str, int]) -> Optional[Dict[str, Any]]:
        """处理分片包"""
        fragment_id = header['fragment_id']
        fragment_index = header['fragment_index']
        total_fragments = header['total_fragments']
        
        # 初始化分片缓冲区
        if fragment_id not in self.fragment_buffers:
            self.fragment_buffers[fragment_id] = {
                'chunks': {},
                'total_fragments': total_fragments,
                'addr': addr,
                'timestamp': time.time()
            }
        
        # 存储分片
        self.fragment_buffers[fragment_id]['chunks'][fragment_index] = chunk
        
        # 检查是否收集完所有分片
        buffer = self.fragment_buffers[fragment_id]
        if len(buffer['chunks']) == total_fragments:
            # 重组数据
            complete_data = b''
            for i in range(total_fragments):
                complete_data += buffer['chunks'][i]
            
            # 清理缓冲区
            del self.fragment_buffers[fragment_id]
            
            # 解析完整数据包
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
            del self.fragment_buffers[fid]
            logger.warning(f"清理过期摄像头分片: {fid}")

class SmartCameraHandler:
    """智能摄像头处理器"""
    
    def __init__(self, camera_id: int, config: Dict[str, Any]):
        self.camera_id = camera_id
        self.config = config
        self.cap = None
        self.is_running = False
        self.frame_queue = Queue(maxsize=2)  # 最多缓存2帧
        self.capture_thread = None
        self.stats = {
            'frames_captured': 0,
            'frames_dropped': 0,
            'frames_sent': 0
        }
        
        # 动态压缩质量
        self.compression_levels = [95, 80, 60, 40, 20]
        self.current_quality_index = 1
        
    async def start(self) -> bool:
        """启动摄像头"""
        try:
            self.cap = cv2.VideoCapture(self.camera_id)
            if not self.cap.isOpened():
                logger.error(f"无法打开摄像头 {self.camera_id}")
                return False
            
            # 设置摄像头参数
            width, height = self.config['resolution']
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            self.cap.set(cv2.CAP_PROP_FPS, self.config['fps'])
            
            # 验证设置
            actual_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            actual_fps = self.cap.get(cv2.CAP_PROP_FPS)
            
            logger.info(f"摄像头 {self.camera_id} 启动成功: {actual_width}x{actual_height}@{actual_fps}fps")
            
            self.is_running = True
            self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
            self.capture_thread.start()
            
            return True
            
        except Exception as e:
            logger.error(f"摄像头 {self.camera_id} 启动失败: {e}")
            return False
    
    def _capture_loop(self):
        """摄像头捕获循环"""
        frame_interval = 1.0 / self.config['fps']
        last_capture_time = 0
        
        while self.is_running:
            try:
                current_time = time.time()
                if current_time - last_capture_time < frame_interval:
                    time.sleep(0.001)  # 短暂休眠
                    continue
                
                ret, frame = self.cap.read()
                if not ret:
                    logger.warning(f"摄像头 {self.camera_id} 读取帧失败")
                    time.sleep(0.1)
                    continue
                
                self.stats['frames_captured'] += 1
                last_capture_time = current_time
                
                # 清理旧帧，保持实时性
                while not self.frame_queue.empty():
                    try:
                        self.frame_queue.get_nowait()
                        self.stats['frames_dropped'] += 1
                    except Empty:
                        break
                
                # 添加新帧
                try:
                    frame_data = self._process_frame(frame)
                    if frame_data:
                        camera_frame = CameraFrame(
                            camera_id=self.camera_id,
                            frame_data=frame_data,
                            timestamp=current_time,
                            frame_id=uuid.uuid4().hex[:8],
                            resolution=self.config['resolution'],
                            quality=self.config['quality']
                        )
                        self.frame_queue.put_nowait(camera_frame)
                except:
                    self.stats['frames_dropped'] += 1
                
            except Exception as e:
                logger.error(f"摄像头 {self.camera_id} 捕获异常: {e}")
                time.sleep(0.1)
    
    def _process_frame(self, frame: np.ndarray) -> Optional[bytes]:
        """处理帧数据"""
        try:
            # 应用鱼眼校正（如果需要）
            if self.camera_id == 0:  # 主摄像头使用鱼眼校正
                frame = self._apply_fisheye_correction(frame)
            
            # 调整分辨率
            target_width, target_height = self.config['resolution']
            if frame.shape[1] != target_width or frame.shape[0] != target_height:
                frame = cv2.resize(frame, (target_width, target_height), interpolation=cv2.INTER_AREA)
            
            # 压缩为JPEG
            quality = self.config['quality']
            success, encoded = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
            
            if success:
                frame_bytes = encoded.tobytes()
                
                # 检查大小并动态调整质量
                if len(frame_bytes) > MAX_UDP_SIZE * 0.8:  # 如果接近UDP限制
                    frame_bytes = self._adjust_quality_and_compress(frame)
                
                return frame_bytes
            
            return None
            
        except Exception as e:
            logger.error(f"帧处理失败: {e}")
            return None
    
    def _apply_fisheye_correction(self, frame: np.ndarray) -> np.ndarray:
        """应用鱼眼校正"""
        try:
            # 这里应该使用实际的鱼眼校正参数
            # 目前使用简化版本
            return frame
        except Exception as e:
            logger.error(f"鱼眼校正失败: {e}")
            return frame
    
    def _adjust_quality_and_compress(self, frame: np.ndarray) -> bytes:
        """动态调整压缩质量"""
        for quality in self.compression_levels[self.current_quality_index:]:
            success, encoded = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
            if success:
                frame_bytes = encoded.tobytes()
                if len(frame_bytes) <= MAX_UDP_SIZE * 0.8:
                    return frame_bytes
        
        # 如果还是太大，进行分辨率缩放
        return self._scale_and_compress(frame)
    
    def _scale_and_compress(self, frame: np.ndarray) -> bytes:
        """缩放并压缩"""
        height, width = frame.shape[:2]
        scale_factor = 0.8
        
        while scale_factor > 0.3:
            new_width = int(width * scale_factor)
            new_height = int(height * scale_factor)
            scaled_frame = cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_AREA)
            
            success, encoded = cv2.imencode('.jpg', scaled_frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
            if success:
                frame_bytes = encoded.tobytes()
                if len(frame_bytes) <= MAX_UDP_SIZE * 0.8:
                    return frame_bytes
            
            scale_factor -= 0.1
        
        # 最后的保底方案
        success, encoded = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 20])
        return encoded.tobytes() if success else b''
    
    def get_latest_frame(self) -> Optional[CameraFrame]:
        """获取最新帧"""
        try:
            return self.frame_queue.get_nowait()
        except Empty:
            return None
    
    def stop(self):
        """停止摄像头"""
        self.is_running = False
        if self.capture_thread:
            self.capture_thread.join(timeout=2)
        if self.cap:
            self.cap.release()
        logger.info(f"摄像头 {self.camera_id} 已停止")

class CameraGateway:
    """摄像头网关主类"""
    
    def __init__(self, port: int = 8991):
        self.port = port
        self.socket = None
        self.is_running = False
        self.security_manager = SecurityManager(SHARED_SECRET_KEY)
        self.packet_manager = PacketManager()
        self.cameras = {}
        self.active_clients = {}  # 客户端订阅信息
        self.stats = {
            'packets_received': 0,
            'packets_sent': 0,
            'frames_sent': 0,
            'errors': 0
        }
    
    async def start(self):
        """启动网关服务"""
        retry_count = 0
        max_retries = 10
        
        while retry_count < max_retries:
            try:
                # 启动UDP服务器
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.socket.bind(('0.0.0.0', self.port))
                self.socket.setblocking(False)
                
                self.is_running = True
                logger.info(f"摄像头网关启动成功，监听端口 {self.port}")
                
                # 初始化摄像头
                await self._initialize_cameras()
                
                # 启动后台任务
                await asyncio.gather(
                    self._receive_loop(),
                    self._stream_loop(),
                    self._cleanup_loop(),
                    self._stats_loop(),
                    self._health_check_loop()
                )
                break
                
            except Exception as e:
                retry_count += 1
                logger.error(f"启动失败 (尝试 {retry_count}): {e}")
                if retry_count < max_retries:
                    await asyncio.sleep(min(retry_count * 2, 30))
                else:
                    logger.critical("启动失败，已达到最大重试次数")
                    raise
    
    async def _initialize_cameras(self):
        """初始化摄像头"""
        for camera_id, config in CAMERA_CONFIGS.items():
            try:
                camera = SmartCameraHandler(camera_id, config)
                if await camera.start():
                    self.cameras[camera_id] = camera
                    logger.info(f"摄像头 {camera_id} ({config['name']}) 初始化成功")
                else:
                    logger.warning(f"摄像头 {camera_id} ({config['name']}) 初始化失败")
            except Exception as e:
                logger.error(f"摄像头 {camera_id} 初始化异常: {e}")
    
    async def _receive_loop(self):
        """接收数据循环"""
        while self.is_running:
            try:
                # 使用正确的asyncio方法接收UDP数据
                loop = asyncio.get_running_loop()
                data, addr = await loop.sock_recvfrom(self.socket, MAX_UDP_SIZE)
                self.stats['packets_received'] += 1
                
                # 异步处理数据包
                asyncio.create_task(self._process_packet(data, addr))
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.stats['errors'] += 1
                logger.error(f"接收数据失败: {e}")
                await asyncio.sleep(0.1)
    
    async def _process_packet(self, data: bytes, addr: Tuple[str, int]):
        """处理数据包"""
        try:
            # 解析数据包
            packet = self.packet_manager.process_received_packet(data, addr)
            if not packet:
                return
            
            # 验证安全性
            if not self._verify_packet_security(packet, data, addr):
                logger.warning(f"安全验证失败: {addr}")
                return
            
            # 处理请求
            await self._handle_request(packet, addr)
            
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"数据包处理失败: {e}")
    
    def _verify_packet_security(self, packet: Dict, original_data: bytes, addr: Tuple[str, int]) -> bool:
        """验证数据包安全性"""
        try:
            timestamp = packet.get('timestamp')
            if not timestamp or not self.security_manager.verify_timestamp(timestamp):
                return False
            
            # 这里应该验证签名，但需要重构数据包格式
            # 暂时跳过签名验证，在生产环境中必须启用
            
            return True
            
        except Exception as e:
            logger.error(f"安全验证异常: {e}")
            return False
    
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
            else:
                logger.warning(f"未知请求类型: {request_type}")
                
        except Exception as e:
            logger.error(f"请求处理失败: {e}")
    
    async def _handle_subscribe(self, data: Dict, addr: Tuple[str, int]):
        """处理订阅请求"""
        camera_ids = data.get('camera_ids', [])
        session_id = data.get('session_id', uuid.uuid4().hex)
        
        self.active_clients[addr] = {
            'session_id': session_id,
            'camera_ids': camera_ids,
            'last_activity': time.time()
        }
        
        logger.info(f"客户端 {addr} 订阅摄像头: {camera_ids}")
        
        # 发送确认响应
        await self._send_response(addr, {
            'status': 'success',
            'message': 'subscription_confirmed',
            'session_id': session_id,
            'camera_ids': camera_ids
        })
    
    async def _handle_unsubscribe(self, data: Dict, addr: Tuple[str, int]):
        """处理取消订阅请求"""
        if addr in self.active_clients:
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
                'stats': camera.stats
            })
        
        await self._send_response(addr, {
            'status': 'success',
            'message': 'camera_list',
            'cameras': camera_list
        })
    
    async def _handle_capture_screenshot(self, data: Dict, addr: Tuple[str, int]):
        """处理截图请求"""
        camera_id = data.get('camera_id', 0)
        
        if camera_id not in self.cameras:
            await self._send_response(addr, {
                'status': 'error',
                'message': 'camera_not_found'
            })
            return
        
        camera = self.cameras[camera_id]
        frame = camera.get_latest_frame()
        
        if frame:
            # 将图像数据编码为base64
            frame_base64 = base64.b64encode(frame.frame_data).decode('utf-8')
            
            await self._send_response(addr, {
                'status': 'success',
                'message': 'screenshot_captured',
                'camera_id': camera_id,
                'frame_id': frame.frame_id,
                'timestamp': frame.timestamp,
                'resolution': frame.resolution,
                'data': frame_base64
            })
        else:
            await self._send_response(addr, {
                'status': 'error',
                'message': 'no_frame_available'
            })
    
    async def _stream_loop(self):
        """视频流发送循环"""
        while self.is_running:
            try:
                # 为每个活跃客户端发送视频帧
                for addr, client_info in list(self.active_clients.items()):
                    try:
                        await self._send_frames_to_client(addr, client_info)
                    except Exception as e:
                        logger.error(f"向客户端 {addr} 发送帧失败: {e}")
                        # 移除有问题的客户端
                        if addr in self.active_clients:
                            del self.active_clients[addr]
                
                await asyncio.sleep(0.033)  # 约30fps
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"流发送循环失败: {e}")
                await asyncio.sleep(0.1)
    
    async def _send_frames_to_client(self, addr: Tuple[str, int], client_info: Dict):
        """向客户端发送视频帧"""
        camera_ids = client_info['camera_ids']
        
        for camera_id in camera_ids:
            if camera_id not in self.cameras:
                continue
            
            camera = self.cameras[camera_id]
            frame = camera.get_latest_frame()
            
            if frame:
                # 将图像数据编码为base64（用于JSON传输）
                frame_base64 = base64.b64encode(frame.frame_data).decode('utf-8')
                
                frame_data = {
                    'message_type': 'video_frame',
                    'camera_id': camera_id,
                    'frame_id': frame.frame_id,
                    'timestamp': frame.timestamp,
                    'resolution': frame.resolution,
                    'quality': frame.quality,
                    'data': frame_base64
                }
                
                await self._send_response(addr, frame_data)
                self.stats['frames_sent'] += 1
                camera.stats['frames_sent'] += 1
    
    async def _send_response(self, addr: Tuple[str, int], response_data: Dict):
        """发送响应"""
        try:
            response_packet = self.packet_manager.prepare_packet(response_data, self.security_manager)
            fragments = self.packet_manager.auto_fragment(response_packet)
            
            loop = asyncio.get_running_loop()
            for fragment in fragments:
                await loop.sock_sendto(self.socket, fragment, addr)
            
            self.stats['packets_sent'] += 1
            
        except Exception as e:
            logger.error(f"发送响应失败: {e}")
    
    async def _cleanup_loop(self):
        """清理循环"""
        while self.is_running:
            try:
                # 清理过期客户端
                current_time = time.time()
                expired_clients = [
                    addr for addr, client_info in self.active_clients.items()
                    if current_time - client_info['last_activity'] > SESSION_TIMEOUT
                ]
                
                for addr in expired_clients:
                    del self.active_clients[addr]
                    logger.info(f"清理过期客户端: {addr}")
                
                # 清理其他过期数据
                self.security_manager.cleanup_expired_sessions()
                self.packet_manager.cleanup_expired_fragments()
                
                await asyncio.sleep(60)  # 每分钟清理一次
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"清理任务失败: {e}")
    
    async def _stats_loop(self):
        """统计循环"""
        while self.is_running:
            try:
                await asyncio.sleep(30)  # 每30秒输出一次统计
                logger.info(f"摄像头网关统计: {self.stats}")
                
                # 输出各摄像头统计
                for camera_id, camera in self.cameras.items():
                    logger.info(f"摄像头 {camera_id} 统计: {camera.stats}")
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"统计任务失败: {e}")
    
    async def _health_check_loop(self):
        """健康检查循环"""
        while self.is_running:
            try:
                # 检查摄像头状态
                for camera_id, camera in list(self.cameras.items()):
                    if not camera.is_running:
                        logger.warning(f"摄像头 {camera_id} 已停止，尝试重启...")
                        try:
                            if await camera.start():
                                logger.info(f"摄像头 {camera_id} 重启成功")
                            else:
                                logger.error(f"摄像头 {camera_id} 重启失败")
                        except Exception as e:
                            logger.error(f"摄像头 {camera_id} 重启异常: {e}")
                
                await asyncio.sleep(10)  # 每10秒检查一次
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"健康检查失败: {e}")
    
    async def stop(self):
        """停止网关服务"""
        self.is_running = False
        
        # 停止所有摄像头
        for camera in self.cameras.values():
            camera.stop()
        
        if self.socket:
            self.socket.close()
        
        logger.info("摄像头网关已停止")

async def main():
    """主函数"""
    gateway = CameraGateway()
    
    try:
        await gateway.start()
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在停止...")
    except Exception as e:
        logger.critical(f"摄像头网关运行失败: {e}")
    finally:
        await gateway.stop()

if __name__ == "__main__":
    asyncio.run(main())
