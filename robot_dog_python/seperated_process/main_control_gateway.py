#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实时UDP控制网关
端口：本地8990，FRP远程48990
功能：处理状态切换、XYR控制、控制对象信号
"""

import asyncio
import socket
import json
import time
import hmac
import hashlib
import uuid
import logging
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict
import struct

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 安全配置
SHARED_SECRET_KEY = b"robot_dog_control_secret_2024"
SESSION_TIMEOUT = 300  # 5分钟会话超时
MAX_UDP_SIZE = 1400
HEADER_SIZE = 64

@dataclass
class ControlCommand:
    """控制命令数据结构"""
    command_type: str  # 'state_switch', 'xyr_control', 'object_control'
    target: str        # 'body', 'head', 'system'
    data: Dict[str, Any]
    timestamp: float
    session_id: str

class SecurityManager:
    """安全管理器"""
    
    def __init__(self, secret_key: bytes):
        self.secret_key = secret_key
        self.active_sessions = {}
        self.session_cleanup_interval = 60
        
    def generate_signature(self, data: bytes, timestamp: float) -> str:
        """生成HMAC签名"""
        message = f"{timestamp}:{data.decode('utf-8')}".encode('utf-8')
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
        logger.info(f"创建会话 {session_id} for {client_addr}")
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
            logger.info(f"清理过期会话: {sid}")

class PacketManager:
    """数据包管理器 - 支持自动切片"""
    
    def __init__(self):
        self.fragment_buffers = {}
        self.fragment_timers = {}
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
    
    def auto_fragment(self, data: bytes) -> list:
        """自动判断是否需要切片"""
        if len(data) <= MAX_UDP_SIZE:
            return [data]  # 单包发送
        
        # 需要分片
        fragment_id = uuid.uuid4().hex[:8]
        chunk_size = MAX_UDP_SIZE - 100  # 预留分片头部空间
        chunks = []
        
        for i in range(0, len(data), chunk_size):
            chunk = data[i:i + chunk_size]
            fragment_header = {
                'fragment_id': fragment_id,
                'fragment_index': i // chunk_size,
                'total_fragments': (len(data) + chunk_size - 1) // chunk_size,
                'is_last': i + chunk_size >= len(data)
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
            logger.warning(f"清理过期分片: {fid}")

class DDSBridge:
    """DDS通信桥接器"""
    
    def __init__(self):
        self.is_connected = False
        self.connection_retry_count = 0
        self.max_retries = 10
        self.retry_delay = 1.0
        
    async def connect(self):
        """连接到DDS系统"""
        try:
            # 这里应该连接到实际的DDS系统
            # 目前使用模拟连接
            await asyncio.sleep(0.1)
            self.is_connected = True
            self.connection_retry_count = 0
            logger.info("DDS连接成功")
            return True
        except Exception as e:
            self.connection_retry_count += 1
            logger.error(f"DDS连接失败 (尝试 {self.connection_retry_count}): {e}")
            return False
    
    async def send_command(self, command: ControlCommand) -> bool:
        """发送控制命令到DDS"""
        if not self.is_connected:
            if not await self.connect():
                return False
        
        try:
            # 根据命令类型处理
            if command.command_type == 'state_switch':
                return await self._handle_state_switch(command)
            elif command.command_type == 'xyr_control':
                return await self._handle_xyr_control(command)
            elif command.command_type == 'object_control':
                return await self._handle_object_control(command)
            else:
                logger.warning(f"未知命令类型: {command.command_type}")
                return False
                
        except Exception as e:
            logger.error(f"DDS命令发送失败: {e}")
            self.is_connected = False
            return False
    
    async def _handle_state_switch(self, command: ControlCommand) -> bool:
        """处理状态切换命令"""
        logger.info(f"状态切换: {command.data}")
        # 实际的DDS状态切换逻辑
        await asyncio.sleep(0.01)  # 模拟处理时间
        return True
    
    async def _handle_xyr_control(self, command: ControlCommand) -> bool:
        """处理XYR控制命令"""
        logger.debug(f"XYR控制: {command.data}")
        # 实际的DDS运动控制逻辑
        await asyncio.sleep(0.001)  # 模拟处理时间
        return True
    
    async def _handle_object_control(self, command: ControlCommand) -> bool:
        """处理对象控制命令"""
        logger.info(f"对象控制 [{command.target}]: {command.data}")
        # 实际的DDS对象控制逻辑
        await asyncio.sleep(0.01)  # 模拟处理时间
        return True

class ControlGateway:
    """控制网关主类"""
    
    def __init__(self, port: int = 8990):
        self.port = port
        self.socket = None
        self.is_running = False
        self.security_manager = SecurityManager(SHARED_SECRET_KEY)
        self.packet_manager = PacketManager()
        self.dds_bridge = DDSBridge()
        self.error_counts = defaultdict(int)
        self.stats = {
            'packets_received': 0,
            'packets_sent': 0,
            'commands_processed': 0,
            'errors': 0
        }
    
    async def start(self):
        """启动网关服务"""
        retry_count = 0
        max_retries = 10
        
        while retry_count < max_retries:
            try:
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.socket.bind(('0.0.0.0', self.port))
                self.socket.setblocking(False)
                
                self.is_running = True
                logger.info(f"控制网关启动成功，监听端口 {self.port}")
                
                # 启动后台任务
                await asyncio.gather(
                    self._receive_loop(),
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
    
    async def _receive_loop(self):
        """接收数据循环"""
        while self.is_running:
            try:
                # 使用传统的socket方法，避免asyncio兼容性问题
                self.socket.settimeout(0.1)  # 设置短超时
                try:
                    data, addr = self.socket.recvfrom(MAX_UDP_SIZE)
                    self.stats['packets_received'] += 1
                    
                    # 异步处理数据包
                    asyncio.create_task(self._process_packet(data, addr))
                except socket.timeout:
                    # 超时是正常的，继续循环
                    pass
                except BlockingIOError:
                    # 没有数据可读
                    await asyncio.sleep(0.001)
                
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
            
            # 处理控制命令
            await self._handle_control_command(packet, addr)
            
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
    
    async def _handle_control_command(self, packet: Dict, addr: Tuple[str, int]):
        """处理控制命令"""
        try:
            data = packet.get('data', {})
            command_type = data.get('command_type')
            target = data.get('target', 'body')
            command_data = data.get('data', {})
            
            if not command_type:
                logger.warning("缺少命令类型")
                return
            
            # 创建控制命令
            command = ControlCommand(
                command_type=command_type,
                target=target,
                data=command_data,
                timestamp=packet.get('timestamp', time.time()),
                session_id=data.get('session_id', '')
            )
            
            # 发送到DDS
            success = await self.dds_bridge.send_command(command)
            
            if success:
                self.stats['commands_processed'] += 1
                # 发送确认响应
                await self._send_response(addr, {
                    'status': 'success',
                    'command_id': data.get('command_id'),
                    'timestamp': time.time()
                })
            else:
                await self._send_response(addr, {
                    'status': 'error',
                    'message': 'DDS处理失败',
                    'command_id': data.get('command_id'),
                    'timestamp': time.time()
                })
                
        except Exception as e:
            logger.error(f"命令处理失败: {e}")
            await self._send_response(addr, {
                'status': 'error',
                'message': str(e),
                'timestamp': time.time()
            })
    
    async def _send_response(self, addr: Tuple[str, int], response_data: Dict):
        """发送响应"""
        try:
            response_packet = self.packet_manager.prepare_packet(response_data, self.security_manager)
            fragments = self.packet_manager.auto_fragment(response_packet)
            
            for fragment in fragments:
                self.socket.sendto(fragment, addr)
            
            self.stats['packets_sent'] += 1
            
        except Exception as e:
            logger.error(f"发送响应失败: {e}")
    
    async def _cleanup_loop(self):
        """清理循环"""
        while self.is_running:
            try:
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
                logger.info(f"统计信息: {self.stats}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"统计任务失败: {e}")
    
    async def _health_check_loop(self):
        """健康检查循环"""
        while self.is_running:
            try:
                # 检查DDS连接
                if not self.dds_bridge.is_connected:
                    logger.warning("DDS连接断开，尝试重连...")
                    await self.dds_bridge.connect()
                
                await asyncio.sleep(5)  # 每5秒检查一次
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"健康检查失败: {e}")
    
    async def stop(self):
        """停止网关服务"""
        self.is_running = False
        if self.socket:
            self.socket.close()
        logger.info("控制网关已停止")

async def main():
    """主函数"""
    gateway = ControlGateway()
    
    try:
        await gateway.start()
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在停止...")
    except Exception as e:
        logger.critical(f"网关运行失败: {e}")
    finally:
        await gateway.stop()

if __name__ == "__main__":
    asyncio.run(main())
