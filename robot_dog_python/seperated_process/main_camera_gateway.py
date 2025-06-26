#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
优化版实时UDP摄像头网关 (v2 - Fixed)
端口：本地8991，FRP远程48991
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

# 配置日志
logging.basicConfig(
    level=logging.INFO, # Changed to INFO for production, DEBUG is very verbose
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 安全配置
SHARED_SECRET_KEY = b"robot_dog_camera_secret_2024"
SESSION_TIMEOUT = 300  # 5分钟会话超时
MAX_UDP_SIZE = 8192  # 增大UDP包大小，减少分片
FRAGMENT_THRESHOLD = 1400  # 分片阈值提高
HEADER_SIZE = 32  # 减小头部大小

# 摄像头配置 - 优化性能
CAMERA_CONFIGS = {
    # 0: {
    #     "resolution": (640, 480),
    #     "fps": 20,  # 降低帧率减少CPU占用
    #     "quality": 75,  # 适中的质量
    #     "name": "主摄像头"
    # },
    1: {
        "resolution": (640, 480),  # 降低分辨率
        "fps": 15,
        "quality": 70,
        "name": "高清摄像头"
    },
    2: {
        "resolution": (640, 480),
        "fps": 20,  # 小分辨率可以保持较高帧率
        "quality": 70,
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
        
        # 头部格式: [2-byte length of header] + [JSON header]
        header = {} # No security for now, keeping it simple
        header_bytes = json.dumps(header).encode('utf-8')
        header_size_packed = struct.pack('!H', len(header_bytes))
        
        return header_size_packed + header_bytes + packet_bytes
    
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
            complete_data = b''.join(buffer['chunks'][i] for i in range(total_fragments))
            
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
            if fid in self.fragment_buffers:
                del self.fragment_buffers[fid]
                logger.warning(f"清理过期摄像头分片: {fid}")

class SmartCameraHandler:
    """智能摄像头处理器"""
    
    def __init__(self, camera_id: int, config: Dict[str, Any]):
        self.camera_id = camera_id
        self.config = config
        self.cap = None
        self.is_running = False
        self.frame_queue = Queue(maxsize=2)  # 最多缓存2帧,防止延迟
        self.capture_thread = None
        self.stats = {
            'frames_captured': 0,
            'frames_dropped': 0,
            'frames_sent': 0,
            'last_capture_time': 0
        }
    
    async def start(self) -> bool:
        """启动摄像头"""
        try:
            self.cap = cv2.VideoCapture(self.camera_id)
            if not self.cap.isOpened():
                logger.error(f"无法打开摄像头 {self.camera_id}")
                return False
            
            width, height = self.config['resolution']
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            self.cap.set(cv2.CAP_PROP_FPS, self.config['fps'])
            
            actual_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            actual_fps = self.cap.get(cv2.CAP_PROP_FPS)
            
            logger.info(f"摄像头 {self.camera_id} 启动: {actual_width}x{actual_height}@{actual_fps}fps (Requested: {width}x{height}@{self.config['fps']}fps)")
            
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
        
        while self.is_running:
            try:
                capture_start_time = time.time()
                
                # 精确控制帧率
                time_since_last_frame = capture_start_time - self.stats['last_capture_time']
                if time_since_last_frame < frame_interval:
                    time.sleep(frame_interval - time_since_last_frame)
                
                self.stats['last_capture_time'] = time.time()
                
                ret, frame = self.cap.read()
                if not ret:
                    logger.warning(f"摄像头 {self.camera_id} 读取帧失败")
                    time.sleep(0.1)
                    continue
                
                self.stats['frames_captured'] += 1
                
                # 编码帧
                frame_data = self._process_frame(frame)
                if not frame_data:
                    self.stats['frames_dropped'] += 1
                    continue

                camera_frame = CameraFrame(
                    camera_id=self.camera_id,
                    frame_data=frame_data,
                    timestamp=self.stats['last_capture_time'],
                    frame_id=uuid.uuid4().hex[:8],
                    resolution=self.config['resolution'],
                    quality=self.config['quality']
                )

                # 如果队列已满，丢弃旧帧以保持实时性
                if self.frame_queue.full():
                    try:
                        self.frame_queue.get_nowait()
                        self.stats['frames_dropped'] += 1
                    except Empty:
                        pass # Race condition, another thread might have taken it.
                
                self.frame_queue.put_nowait(camera_frame)
                
            except Full:
                self.stats['frames_dropped'] += 1
            except Exception as e:
                logger.error(f"摄像头 {self.camera_id} 捕获异常: {e}", exc_info=True)
                time.sleep(0.1)
    
    def _process_frame(self, frame: np.ndarray) -> Optional[bytes]:
        """处理帧数据（调整大小和压缩）"""
        try:
            target_width, target_height = self.config['resolution']
            if frame.shape[1] != target_width or frame.shape[0] != target_height:
                frame = cv2.resize(frame, (target_width, target_height), interpolation=cv2.INTER_AREA)
            
            quality = self.config['quality']
            success, encoded_jpg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
            
            return encoded_jpg.tobytes() if success else None
            
        except Exception as e:
            logger.error(f"帧处理失败: {e}")
            return None
    
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
            # 异步处理数据包
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
        self.active_clients: Dict[Tuple[str, int], Dict] = {}  # 客户端订阅信息
        self.stats = {
            'packets_received': 0,
            'packets_sent': 0,
            'frames_sent': 0,
            'errors': 0
        }
    
    async def start(self):
        """启动网关服务"""
        loop = asyncio.get_running_loop()
        logger.info(f"正在启动摄像头网关，监听端口 {self.port}")

        try:
            # 启动UDP服务器 - THE ASYNCIO WAY
            self.transport, self.protocol = await loop.create_datagram_endpoint(
                lambda: UDPProtocol(self),
                local_addr=('0.0.0.0', self.port)
            )

            self.is_running = True
            logger.info("摄像头网关启动成功")

            await self._initialize_cameras()

            await asyncio.gather(
                # _receive_loop is replaced by the UDPProtocol
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
                camera = SmartCameraHandler(camera_id, config)
                if await camera.start():
                    self.cameras[camera_id] = camera
                else:
                    logger.warning(f"摄像头 {camera_id} ({config['name']}) 初始化失败")
            except Exception as e:
                logger.error(f"摄像头 {camera_id} 初始化异常: {e}")
    
    async def _process_packet(self, data: bytes, addr: Tuple[str, int]):
        """处理数据包"""
        try:
            packet = self.packet_manager.process_received_packet(data, addr)
            if not packet:
                # This could be a binary frame from another client, just ignore
                return
            
            # 安全性验证可以稍后添加
            
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
            else:
                logger.warning(f"未知请求类型: {request_type} from {addr}")
                
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
                'is_active': camera.is_running
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
                
                await asyncio.sleep(0.001) # Yield to event loop to prevent tight loop
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"流发送循环失败: {e}")
                await asyncio.sleep(0.1)
    
    async def _send_frames_to_client(self, addr: Tuple[str, int], client_info: Dict):
        """向客户端发送视频帧"""
        client_info['last_activity'] = time.time()
        for camera_id in client_info['camera_ids']:
            if camera_id not in self.cameras: continue
            
            camera = self.cameras[camera_id]
            frame = camera.get_latest_frame()
            
            if frame:
                await self._send_binary_frame(addr, frame)
                self.stats['frames_sent'] += 1
                camera.stats['frames_sent'] += 1
    
    async def _send_binary_frame(self, addr: Tuple[str, int], frame: CameraFrame):
        """发送二进制帧数据 - 优化版"""
        if not self.transport: return
        try:
            # FIX: Correct struct format string to include 'Q' for the 8-byte timestamp.
            frame_header = struct.pack('!B Q HHHB', 
                0xFF,                               # Magic number (B)
                int(frame.timestamp * 1000000),     # Microsecond timestamp (Q)
                frame.camera_id,                    # Camera ID (H)
                frame.resolution[0],                # Width (H)
                frame.resolution[1],                # Height (H)
                frame.quality                       # Quality (B)
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
        if not self.transport: return
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
        if not self.transport: return
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
                    # Reset stats to see rates
                    cam.stats['frames_captured'] = 0
                    cam.stats['frames_dropped'] = 0
                    cam.stats['frames_sent'] = 0
            except Exception as e:
                logger.error(f"统计任务失败: {e}")
    
    async def _health_check_loop(self):
        """健康检查循环"""
        while self.is_running:
            await asyncio.sleep(60)
            try:
                for camera_id, camera in list(self.cameras.items()):
                    if not camera.is_running or not camera.capture_thread.is_alive():
                        logger.warning(f"摄像头 {camera_id} 已停止，尝试重启...")
                        await camera.start()
            except Exception as e:
                logger.error(f"健康检查失败: {e}")
    
    async def stop(self):
        """停止网关服务"""
        if not self.is_running: return
        self.is_running = False
        logger.info("正在停止网关服务...")
        
        for camera in self.cameras.values():
            camera.stop()
        
        if self.transport:
            self.transport.close()
        
        # Allow time for tasks to finish
        await asyncio.sleep(0.5)
        logger.info("摄像头网关已停止")

async def main():
    gateway = CameraGateway()
    loop = asyncio.get_event_loop()
    
    try:
        await gateway.start()
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在停止...")
    finally:
        await gateway.stop()

if __name__ == "__main__":
    asyncio.run(main())
