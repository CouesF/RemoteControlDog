#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
摄像头网关客户端 - v4 (Fixed)
兼容新版 CameraGateway (带分片和二进制协议)
"""

import asyncio
import socket
import json
import time
import struct
import cv2
import numpy as np
import uuid
import logging
from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass
import threading
from queue import Queue, Empty, Full

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 服务器配置
# SERVER_HOST = "127.0.0.1"  # For local testing, use 127.0.0.1
SERVER_HOST = "118.31.58.101" # For remote server
# SERVER_PORT = 8991 # For local testing, use 8991
SERVER_PORT = 48991 # For remote server
MAX_UDP_SIZE = 8192
RECEIVE_TIMEOUT = 5.0

@dataclass
class CameraFrame:
    """摄像头帧数据"""
    camera_id: int
    frame_data: bytes
    timestamp: float
    frame_id: str
    resolution: Tuple[int, int]
    quality: int

class FragmentBuffer:
    """分片缓冲区 - 用于重组来自服务器的包"""
    def __init__(self):
        self.buffers: Dict[str, Dict] = {}
        self.timeout = 10.0

    def add_fragment(self, data: bytes) -> Optional[bytes]:
        """添加分片，如果完整则重组并返回"""
        try:
            # Protocol: Magic(B)=0xFE, FragID(8s), Index(H), Total(H), Length(H)
            if len(data) < 15: return None

            magic, frag_id_bytes, index, total, length = struct.unpack('!B8sHHH', data[:15])
            if magic != 0xFE: return None

            frag_id = frag_id_bytes.decode('ascii').rstrip('\x00')
            chunk = data[15:15 + length]

            if frag_id not in self.buffers:
                # Initialize buffer for a new fragmented packet
                self.buffers[frag_id] = {
                    'chunks': [None] * total, # pre-allocate list for direct indexing
                    'count' : 0,
                    'total': total,
                    'timestamp': time.time()
                }

            buffer = self.buffers[frag_id]
            if buffer['chunks'][index] is None:
                buffer['chunks'][index] = chunk
                buffer['count'] += 1

            if buffer['count'] == buffer['total']:
                # Reassemble
                full_data = b''.join(buffer['chunks'])
                del self.buffers[frag_id]
                return full_data
            return None
        except Exception as e:
            logger.error(f"Fragment reassembly error: {e}")
            return None

    def cleanup_expired(self):
        """清理过期分片"""
        expired = [fid for fid, buf in self.buffers.items() if time.time() - buf['timestamp'] > self.timeout]
        for fid in expired:
            if fid in self.buffers:
                del self.buffers[fid]
                logger.warning(f"Cleaned up expired fragment buffer: {fid}")

class CameraClient:
    """摄像头客户端"""
    
    def __init__(self, server_host: str = SERVER_HOST, server_port: int = SERVER_PORT):
        self.server_addr = (server_host, server_port)
        self.socket = None
        self.is_running = False
        self.session_id = None
        self.fragment_buffer = FragmentBuffer()
        self.frame_queue = Queue(maxsize=5) # Cache a few frames
        self.receive_thread = None
        self.response_queue = Queue()
        self.camera_list = []
        self.subscribed_cameras = []

    async def connect(self) -> bool:
        """连接到服务器"""
        logger.info(f"Attempting to connect to {self.server_addr}")
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.settimeout(RECEIVE_TIMEOUT)
            self.is_running = True
            
            self.receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
            self.receive_thread.start()
            
            logger.info("Receive thread started, testing connection by requesting camera list...")
            if await self.get_camera_list():
                logger.info("Connection test successful!")
                return True
            
            logger.error("Connection test failed. Server did not respond with camera list.")
            return False
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False

    def _receive_loop(self):
        """接收数据循环"""
        logger.info("Receive loop started")
        while self.is_running:
            try:
                data, addr = self.socket.recvfrom(MAX_UDP_SIZE)
                self._process_received_data(data)
            except socket.timeout:
                continue
            except Exception as e:
                if self.is_running:
                    logger.error(f"Receive loop error: {e}")
        logger.info("Receive loop stopped")

    def _process_received_data(self, data: bytes):
        """处理接收到的数据"""
        if not data: return
        
        magic = data[0]

        if magic == 0xFF: # Binary frame data
            self._handle_binary_frame(data)
        elif magic == 0xFE: # Fragmented binary data
            full_data = self.fragment_buffer.add_fragment(data)
            if full_data:
                self._process_received_data(full_data) # Recursively process reassembled packet
        else: # Assumed to be JSON data from the server
            self._handle_json_packet(data)

    def _handle_binary_frame(self, data: bytes):
        """处理二进制帧数据"""
        try:
            # FIX: Match server's corrected binary frame header format.
            # Header format: Magic(B)=0xFF, Timestamp_us(Q), CamID(H), W(H), H(H), Quality(B)
            header_format = '!B Q HHHB'
            header_size = struct.calcsize(header_format) # Should be 16

            frame_id_size = 8
            data_length_size = 4
            min_packet_size = header_size + frame_id_size + data_length_size

            if len(data) < min_packet_size:
                logger.warning(f"Received binary frame is too short: {len(data)} bytes")
                return

            header_tuple = struct.unpack(header_format, data[:header_size])
            _magic, timestamp_us, camera_id, width, height, quality = header_tuple
            
            frame_id_bytes = data[header_size : header_size + frame_id_size]
            frame_id = frame_id_bytes.rstrip(b'\x00').decode('ascii')
            
            data_length_bytes = data[header_size + frame_id_size : min_packet_size]
            data_length = struct.unpack('!I', data_length_bytes)[0]
            
            frame_data = data[min_packet_size:]

            if len(frame_data) < data_length:
                logger.warning(f"Incomplete frame for {frame_id}. Got {len(frame_data)}, expected {data_length}")
                return

            complete_frame = CameraFrame(
                camera_id=camera_id,
                frame_data=frame_data[:data_length], # Slice to expected size
                timestamp=timestamp_us / 1000000.0,
                frame_id=frame_id,
                resolution=(width, height),
                quality=quality
            )

            # Keep queue fresh by discarding old frames if full
            while self.frame_queue.full(): self.frame_queue.get_nowait()
            self.frame_queue.put_nowait(complete_frame)

        except (struct.error, IndexError, UnicodeDecodeError) as e:
            logger.error(f"Failed to parse binary frame: {e} | Data: {data[:32].hex()}")

    def _handle_json_packet(self, data: bytes):
        """处理JSON数据包, 匹配服务端的格式"""
        try:
            # Server format: [2-byte length of header] + [JSON header] + [JSON payload]
            header_len = struct.unpack('!H', data[:2])[0]
            payload_json = data[2 + header_len:].decode('utf-8')
            packet = json.loads(payload_json)

            if 'data' in packet:
                self._handle_response(packet['data'])

        except (json.JSONDecodeError, struct.error, IndexError) as e:
            logger.error(f"Failed to parse JSON packet from server: {e}")

    def _handle_response(self, response: Dict[str, Any]):
        """处理服务器响应"""
        msg_type = response.get('message')
        if msg_type == 'camera_list' or msg_type == 'subscription_confirmed':
            if msg_type == 'camera_list':
                self.camera_list = response.get('cameras', [])
            self.response_queue.put(response)
        elif msg_type == 'unsubscribed':
            logger.info("Successfully unsubscribed.")
        else:
            logger.info(f"Received server message: {response}")

    def _send_packet(self, data: Dict[str, Any]):
        """发送匹配新服务器协议的数据包"""
        try:
            payload = {'timestamp': time.time(), 'data': data}
            payload_bytes = json.dumps(payload, ensure_ascii=False).encode('utf-8')

            # Empty JSON header is fine for now
            header_bytes = b'{}'
            header_len_packed = struct.pack('!H', len(header_bytes))

            full_packet = header_len_packed + header_bytes + payload_bytes
            
            self.socket.sendto(full_packet, self.server_addr)
        except Exception as e:
            logger.error(f"Failed to send packet: {e}")

    async def get_camera_list(self) -> List[Dict[str, Any]]:
        """获取摄像头列表"""
        while not self.response_queue.empty(): self.response_queue.get_nowait()
        self._send_packet({'request_type': 'get_camera_list'})
        try:
            response = self.response_queue.get(timeout=5.0)
            if response.get('message') == 'camera_list':
                return response.get('cameras', [])
        except Empty:
            logger.error("Timeout waiting for camera list.")
        return []

    async def subscribe_cameras(self, camera_ids: List[int]) -> bool:
        """订阅摄像头"""
        self.session_id = self.session_id or uuid.uuid4().hex
        request = {
            'request_type': 'subscribe',
            'camera_ids': camera_ids,
            'session_id': self.session_id
        }
        self._send_packet(request)
        try:
            response = self.response_queue.get(timeout=5.0)
            if response.get('message') == 'subscription_confirmed':
                self.subscribed_cameras = response.get('camera_ids', [])
                logger.info(f"Subscribed to {self.subscribed_cameras}")
                return True
        except Empty:
            logger.error("Timeout waiting for subscription confirmation.")
        return False
    
    def get_latest_frame(self) -> Optional[CameraFrame]:
        """获取最新帧"""
        try:
            return self.frame_queue.get_nowait()
        except Empty:
            return None
    
    def disconnect(self):
        """断开连接"""
        if not self.is_running: return
        logger.info("Disconnecting...")
        self.is_running = False
        if self.subscribed_cameras:
            self._send_packet({'request_type': 'unsubscribe', 'session_id': self.session_id})
        
        if self.receive_thread and self.receive_thread.is_alive():
            self.receive_thread.join(timeout=1)
        if self.socket:
            self.socket.close()
        logger.info("Disconnected.")

class CameraViewer:
    """摄像头查看器"""
    
    def __init__(self):
        self.client = CameraClient()
        self.is_viewing = False
    
    async def start_viewer(self):
        """启动查看器"""
        if not await self.client.connect():
            logger.error("Could not connect to gateway.")
            return

        cameras = self.client.camera_list
        if not cameras:
            logger.error("No cameras found on server.")
            return
        
        print("\nAvailable Cameras:")
        for i, cam in enumerate(cameras):
             print(f"  {i}: ID {cam['camera_id']} - {cam['name']} ({cam['resolution'][0]}x{cam['resolution'][1]})")

        try:
            choice_str = input(f"\nSelect camera index to view (0-{len(cameras)-1}), default 0: ").strip()
            choice = int(choice_str) if choice_str else 0
            cam_info = cameras[choice]
        except (ValueError, IndexError):
            print("Invalid choice, using default (0).")
            cam_info = cameras[0]
            
        await self._start_video_stream(cam_info['camera_id'], cam_info['name'])

    async def _start_video_stream(self, camera_id: int, camera_name: str):
        """启动视频流"""
        if not await self.client.subscribe_cameras([camera_id]):
            logger.error("Failed to subscribe to camera.")
            return

        self.is_viewing = True
        window_name = f"Camera {camera_id} - {camera_name} (Press 'q' to quit)"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        
        while self.is_viewing:
            frame = self.client.get_latest_frame()
            if frame and frame.camera_id == camera_id:
                try:
                    nparr = np.frombuffer(frame.frame_data, np.uint8)
                    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                    if img is not None:
                        cv2.imshow(window_name, img)
                except Exception as e:
                    logger.error(f"Error processing image: {e}")
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                self.is_viewing = False

            await asyncio.sleep(0.001) # Yield to event loop
        
        cv2.destroyAllWindows()
    
    async def stop(self):
        """停止查看器"""
        self.is_viewing = False
        await asyncio.sleep(0.1)
        self.client.disconnect()

async def main():
    viewer = CameraViewer()
    try:
        await viewer.start_viewer()
    except Exception as e:
        logger.critical(f"Viewer encountered a fatal error: {e}", exc_info=True)
    finally:
        await viewer.stop()

if __name__ == "__main__":
    print("Camera Gateway Client - v4 (Fixed)")
    print(f"Connecting to: {SERVER_HOST}:{SERVER_PORT}")
    print("="*50)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProgram interrupted by user.")
