#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# @FileName: speech_main_fixed.py
# @Description: 修复版语音合成主程序（已修复反馈机制和声音问题）
# @Author: OpenAI
# @Date: 2023-10-27

import asyncio
import json
import uuid
import aiofiles
import websockets
import pyaudio
import os
import sys
import time
import threading
import queue
import numpy as np
import traceback
import signal
import struct
from datetime import datetime
from urllib.parse import urlencode
from unitree_sdk2py.core.channel import ChannelPublisher, ChannelSubscriber, ChannelFactoryInitialize

# ==== 自定义配置 ====
DDS_NETWORK_INTERFACE = "enP8p1s0"  # 请修改为您的网络接口
DDS_SLEEP_INTERVAL = 0.01  # DDS读取间隔
TARGET_SAMPLE_RATE = 48000  # 目标采样率
APP_ID = "2657638375"       # 您的TTS应用ID
TOKEN = "NHt65iYV2xQ-0Uv6VfO97BletTaOMtAn"  # 您的TTS访问令牌

# ==== 路径设置 ====
current_script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_script_dir)
communication_dir_path = os.path.join(parent_dir, 'communication')
sys.path.append(communication_dir_path)

# ==== 确保导入正确的DDS数据结构 ====
try:
    from dds_data_structure import SpeechControl
    print("✅ 成功导入DDS数据结构")
except Exception as e:
    # 如果导入失败，创建最小化数据结构
    print(f"⚠️ 导入DDS数据结构失败: {e}")
    print("🛠️ 创建替代SpeechControl类")
    class SpeechControl:
        def __init__(self):
            self.text_to_speak: str = ""
            self.stop_speaking: bool = False
            self.volume: int = 0
            self.synthesis_started: bool = False
            self.audio_playing: bool = False
            self.audio_stopped: bool = False
            self.error_message: str = ""

# ==== 全局反馈发布器 ====
FEEDBACK_PUB = None

def send_feedback(**kwargs):
    """发送反馈消息"""
    global FEEDBACK_PUB
    if FEEDBACK_PUB is None:
        return
    
    try:
        # 创建反馈消息
        feedback_msg = SpeechControl()
        
        # 设置属性
        for key, value in kwargs.items():
            if hasattr(feedback_msg, key):
                setattr(feedback_msg, key, value)
        
        # 发送反馈
        FEEDBACK_PUB.Write(feedback_msg)
        print(f"📤 发送反馈: {kwargs}")
    except Exception as e:
        print(f"发送反馈失败: {e}")

# ==== TTS协议常量 ====
PROTOCOL_VERSION = 0b0001
DEFAULT_HEADER_SIZE = 0b0001
FULL_CLIENT_REQUEST = 0b0001
AUDIO_ONLY_RESPONSE = 0b1011
FULL_SERVER_RESPONSE = 0b1001
ERROR_INFORMATION = 0b1111
MsgTypeFlagNoSeq = 0b0000
MsgTypeFlagPositiveSeq = 0b1
MsgTypeFlagLastNoSeq = 0b10
MsgTypeFlagNegativeSeq = 0b11
MsgTypeFlagWithEvent = 0b100
NO_SERIALIZATION = 0b0000
JSON = 0b0001
COMPRESSION_NO = 0b0000
COMPRESSION_GZIP = 0b0001
EVENT_NONE = 0
EVENT_Start_Connection = 1
EVENT_FinishConnection = 2
EVENT_ConnectionStarted = 50
EVENT_ConnectionFailed = 51
EVENT_ConnectionFinished = 52
EVENT_StartSession = 100
EVENT_FinishSession = 102
EVENT_SessionStarted = 150
EVENT_SessionFinished = 152
EVENT_SessionFailed = 153
EVENT_TaskRequest = 200
EVENT_TTSSentenceStart = 350
EVENT_TTSSentenceEnd = 351
EVENT_TTSResponse = 352

# ==== 音频播放器类 ====
class AudioPlayer:
    def __init__(self, device_index=0):
        self.p = pyaudio.PyAudio()
        self.stream = None
        self.device_index = device_index
        self.TARGET_SAMPLE_RATE = TARGET_SAMPLE_RATE
        
        # 打印音频设备信息
        self._print_audio_devices()
        
        # 创建音频流
        self._create_stream()
        
        # 播放控制
        self.stop_requested = threading.Event()
        self.stream_lock = threading.Lock()
        self.queue_lock = threading.Lock()
        self.audio_queue = queue.Queue()
        self.current_volume = 70
        self.set_system_volume(self.current_volume)
        
        # 启动播放线程
        self.playback_thread = threading.Thread(target=self._playback_worker, daemon=True)
        self.playback_thread.start()
        print("🔊 音频播放线程已启动")
    
    def _print_audio_devices(self):
        """打印可用音频设备"""
        print("\n===== 可用的音频输出设备 =====")
        for i in range(self.p.get_device_count()):
            try:
                info = self.p.get_device_info_by_index(i)
                if info['maxOutputChannels'] > 0:
                    print(f"  设备 {i}: {info['name']}")
                    print(f"    采样率: {int(info['defaultSampleRate'])} Hz")
                    print(f"    输出通道: {info['maxOutputChannels']}")
                    if 'defaultSampleRate' in info and int(info['defaultSampleRate']) == self.TARGET_SAMPLE_RATE:
                        print("    ✅ 支持目标采样率")
                    else:
                        print("    ⚠️ 不支持目标采样率")
            except:
                continue
        print("============================")
    
    def set_system_volume(self, volume_percent: int):
        """设置系统音量（通过ALSA）"""
        volume = max(0, min(100, volume_percent))
        self.current_volume = volume
        cmd = f"amixer -D hw:0 sset 'PCM' {volume}% >/dev/null 2>&1"
        os.system(cmd)
        print(f"🔈 设置系统音量: {volume}%")
    
    def _create_stream(self):
        """创建音频流"""
        try:
            self.stream = self.p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.TARGET_SAMPLE_RATE,
                output=True,
                output_device_index=self.device_index,
                frames_per_buffer=2048
            )
            print(f"🔊 已打开音频设备: 索引 {self.device_index}")
        except Exception as e:
            print(f"打开音频设备失败: {e}")
            self.stream = None
    
    def _playback_worker(self):
        """音频播放工作线程"""
        print("🎵 音频播放工作线程启动")
        while True:
            try:
                # 获取音频数据
                audio_data = self.audio_queue.get(timeout=0.5)
                
                # 检查停止请求
                if self.stop_requested.is_set():
                    print("⏹️ 播放被跳过（停止请求中）")
                    continue
                
                # 确保音频流就绪
                if not self._ensure_stream_ready():
                    print("⚠️ 音频流未准备好，跳过播放")
                    continue
                
                # 音量放大
                amplified_audio = self.amplify_audio(audio_data)
                
                # 播放当前块
                with self.stream_lock:
                    if self.stream and self.stream.is_active():
                        self.stream.write(amplified_audio)
            
            except queue.Empty:
                if self.stop_requested.is_set():
                    print("🎵 播放线程收到停止请求，准备退出")
                    break
                continue
            except Exception as e:
                print(f"播放线程错误: {e}")
                self._recover_stream()
    
    def _ensure_stream_ready(self):
        """确保音频流准备好接收新音频"""
        if not self.stream or not self.stream.is_active():
            return self._recover_stream()
        return True
    
    def _recover_stream(self):
        """尝试恢复音频流"""
        try:
            if self.stream:
                self.stream.stop_stream()
                self.stream.close()
        except:
            pass
            
        try:
            self._create_stream()
            if self.stream:
                print("🔄 音频流恢复成功")
                return True
            return False
        except Exception as e:
            print(f"恢复音频流失败: {e}")
            return False
    
    def stop_immediately(self):
        """立即停止播放"""
        print("⏹️ 执行立即停止操作")
        # 设置停止标志
        self.stop_requested.set()
        
        # 清空音频队列
        with self.queue_lock:
            while not self.audio_queue.empty():
                try:
                    self.audio_queue.get_nowait()
                except queue.Empty:
                    break
        
        # 强制关闭当前流
        with self.stream_lock:
            if self.stream and self.stream.is_active():
                try:
                    self.stream.stop_stream()
                    self.stream.close()
                    print("⏹️ 音频流已强制停止")
                except Exception as e:
                    print(f"停止音频流时出错: {e}")
                finally:
                    time.sleep(0.05)
                    self._recover_stream()
        
        # 重置停止标志
        self.stop_requested.clear()
        print("⏹️ 停止操作完成，准备接收新音频")
        
        # 发送停止反馈
        send_feedback(audio_stopped=True)
    
    def play_audio(self, audio_data):
        """添加音频到播放队列（线程安全）"""
        if not audio_data:
            return
        
        try:
            with self.queue_lock:
                self.audio_queue.put(audio_data, block=False)
        except queue.Full:
            print("⚠️ 音频队列已满，丢弃数据")
    
    def amplify_audio(self, audio_data):
        """放大音频音量"""
        if len(audio_data) < 2:
            return audio_data
        
        try:
            # 转换为numpy数组处理
            audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)
            
            # 根据当前音量调整增益
            volume_factor = self.current_volume / 100.0 * 1.5 + 0.5
            
            # 基础放大
            amplified = audio_array * 2.8 * volume_factor
            
            # 限幅处理
            MAX_AMPLITUDE = 32767 * 0.98
            compressed = np.where(np.abs(amplified) > MAX_AMPLITUDE, 
                                  np.sign(amplified) * MAX_AMPLITUDE, 
                                  amplified)
            
            # 二次增益提升
            boosted = compressed * 1.5
            
            # 转换为字节
            final_audio = np.clip(boosted, -32768, 32767).astype(np.int16).tobytes()
            return final_audio
        except Exception as e:
            print(f"音量放大失败: {e}")
            return audio_data
    
    def close(self):
        """释放音频资源"""
        self.stop_immediately()
        
        if self.playback_thread.is_alive():
            self.playback_thread.join(timeout=1.0)
        
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except:
                pass
        if self.p:
            self.p.terminate()
        print("🔇 音频资源已释放")

# ==== 语音控制处理器 ====
class SpeechControlHandler:
    def __init__(self, audio_player):
        self.audio_player = audio_player
        self.command_queue = queue.Queue()
        self.running = True
        self.last_stop_time = 0
        
        # 启动处理线程
        self.handler_thread = threading.Thread(target=self._process_queue, daemon=True)
        self.handler_thread.start()
        print("📡 语音控制处理器已启动")
    
    def add_command(self, control_msg):
        """添加控制命令到队列"""
        self.command_queue.put(control_msg)
    
    def _process_queue(self):
        """处理命令队列"""
        while self.running:
            try:
                control_msg = self.command_queue.get(timeout=0.5)
                
                # 处理停止命令
                if hasattr(control_msg, 'stop_speaking') and control_msg.stop_speaking:
                    current_time = time.time()
                    # 防高频停止
                    if current_time - self.last_stop_time > 0.2:
                        print("⏹️ 收到停止语音命令，执行立即停止")
                        self.audio_player.stop_immediately()
                        self.last_stop_time = current_time
                    else:
                        print(f"⚠️ 收到高频停止请求，已忽略 ({current_time - self.last_stop_time:.2f}秒内)")
                    continue
                
                # 处理音量设置
                if hasattr(control_msg, 'volume') and control_msg.volume is not None:
                    print(f"🔈 设置系统音量: {control_msg.volume}%")
                    self.audio_player.set_system_volume(control_msg.volume)
                
                # 处理语音播放
                if hasattr(control_msg, 'text_to_speak') and control_msg.text_to_speak and control_msg.text_to_speak.strip():
                    print(f"📢 收到语音合成请求: {control_msg.text_to_speak[:30]}...")
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"处理命令时出错: {e}")
                send_feedback(error_message=f"语音控制处理错误: {str(e)}")
    
    def stop(self):
        """停止处理器"""
        self.running = False
        if self.handler_thread.is_alive():
            self.handler_thread.join(timeout=1.0)
        print("📡 语音控制处理器已停止")

# ==== TTS协议辅助类 ====
class Header:
    def __init__(self, 
                 protocol_version=PROTOCOL_VERSION,
                 header_size=DEFAULT_HEADER_SIZE,
                 message_type: int = 0,
                 message_type_specific_flags: int = 0,
                 serial_method: int = NO_SERIALIZATION,
                 compression_type: int = COMPRESSION_NO,
                 reserved_data=0):
        self.header_size = header_size
        self.protocol_version = protocol_version
        self.message_type = message_type
        self.message_type_specific_flags = message_type_specific_flags
        self.serial_method = serial_method
        self.compression_type = compression_type
        self.reserved_data = reserved_data

    def as_bytes(self) -> bytes:
        byte1 = (self.protocol_version << 4) | self.header_size
        byte2 = (self.message_type << 4) | self.message_type_specific_flags
        byte3 = (self.serial_method << 4) | self.compression_type
        byte4 = self.reserved_data
        return bytes([byte1, byte2, byte3, byte4])

class Optional:
    def __init__(self, event: int = EVENT_NONE, sessionId: str = None, sequence: int = None):
        self.event = event
        self.sessionId = sessionId
        self.sequence = sequence
        self.errorCode: int = 0
        self.connectionId: str | None = None
        self.response_meta_json: str | None = None

    def as_bytes(self) -> bytes:
        option_bytes = bytearray()
        if self.event != EVENT_NONE:
            option_bytes.extend(self.event.to_bytes(4, "big", signed=True))
        if self.sessionId is not None:
            session_id_bytes = str.encode(self.sessionId)
            size = len(session_id_bytes)
            option_bytes.extend(size.to_bytes(4, "big", signed=True))
            option_bytes.extend(session_id_bytes)
        if self.sequence is not None:
            option_bytes.extend(self.sequence.to_bytes(4, "big", signed=True))
        return bytes(option_bytes)

class Response:
    def __init__(self, header: Header, optional: Optional):
        self.header = header
        self.optional = optional
        self.payload: bytes | None = None
        self.payload_json: str | None = None

    def __str__(self):
        return f"Response(Header={self.header.__dict__}, Optional={self.optional.__dict__}, Payload_len={len(self.payload or b'')}, Payload_json={self.payload_json})"

# ==== TTS功能函数 ====
def get_payload_bytes(uid='1234', event=EVENT_NONE, text='', speaker='', 
                     audio_format='pcm', audio_sample_rate=48000) -> bytes:
    payload_dict = {
        "user": {"uid": uid},
        "event": event,
        "namespace": "BidirectionalTTS",
        "req_params": {
            "text": text,
            "speaker": speaker,
            "audio_params": {
                "format": audio_format,
                "sample_rate": audio_sample_rate
            }
        }
    }
    return json.dumps(payload_dict).encode('utf-8')

async def send_event(ws, 
                    header: bytes, 
                    optional: bytes | None = None,
                    payload: bytes | None = None):
    """修改后的发送事件函数，移除了类型检查"""
    full_client_request = bytearray(header)
    if optional is not None:
        full_client_request.extend(optional)
    if payload is not None:
        payload_size = len(payload)
        full_client_request.extend(payload_size.to_bytes(4, 'big', signed=True))
        full_client_request.extend(payload)
    await ws.send(full_client_request)

def read_res_content(res: bytes, offset: int) -> tuple[str, int]:
    content_size = int.from_bytes(res[offset: offset + 4], 'big')
    offset += 4
    content_bytes = res[offset: offset + content_size]
    content = str(content_bytes, encoding='utf8')
    offset += content_size
    return content, offset

def read_res_payload(res: bytes, offset: int) -> tuple[bytes, int]:
    payload_size = int.from_bytes(res[offset: offset + 4], 'big')
    offset += 4
    payload = res[offset: offset + payload_size]
    offset += payload_size
    return payload, offset

def parser_response(res) -> Response:
    if isinstance(res, str):
        res = res.encode('utf-8')
    if len(res) < 4:
        raise ValueError(f"Response too short to contain a header. Length: {len(res)}")
    
    response = Response(Header(), Optional())
    header = response.header
    num_mask = 0b00001111
    
    header.protocol_version = (res[0] >> 4) & num_mask
    header.header_size = res[0] & num_mask
    header.message_type = (res[1] >> 4) & num_mask
    header.message_type_specific_flags = res[1] & num_mask
    header.serial_method = (res[2] >> 4) & num_mask
    header.compression_type = res[2] & num_mask
    header.reserved_data = res[3]
    
    offset = 4
    optional = response.optional

    if header.message_type in [FULL_SERVER_RESPONSE, AUDIO_ONLY_RESPONSE]:
        if header.message_type_specific_flags & MsgTypeFlagWithEvent:
            if offset + 4 > len(res):
                return response
            optional.event = int.from_bytes(res[offset:offset + 4], "big", signed=True)
            offset += 4

            if optional.event == EVENT_NONE:
                pass
            elif optional.event == EVENT_ConnectionStarted:
                optional.connectionId, offset = read_res_content(res, offset)
            elif optional.event == EVENT_ConnectionFailed:
                optional.response_meta_json, offset = read_res_content(res, offset)
            elif optional.event in [EVENT_SessionStarted, EVENT_SessionFailed, EVENT_SessionFinished]:
                optional.sessionId, offset = read_res_content(res, offset)
                optional.response_meta_json, offset = read_res_content(res, offset)
            elif optional.event == EVENT_TTSResponse:
                optional.sessionId, offset = read_res_content(res, offset)
                response.payload, offset = read_res_payload(res, offset)
            elif optional.event in [EVENT_TTSSentenceStart, EVENT_TTSSentenceEnd]:
                optional.sessionId, offset = read_res_content(res, offset)
                payload_bytes, offset = read_res_payload(res, offset)
                try:
                    response.payload_json = payload_bytes.decode('utf-8')
                except UnicodeDecodeError:
                    response.payload_json = repr(payload_bytes)

        if offset + 4 <= len(res):
            if response.payload is None and response.payload_json is None:
                if header.message_type == AUDIO_ONLY_RESPONSE:
                    response.payload, offset = read_res_payload(res, offset)
                elif header.message_type == FULL_SERVER_RESPONSE:
                    if len(res) > offset + 4:
                        try:
                            if header.serial_method == JSON:
                                payload_bytes, temp_offset = read_res_payload(res, offset)
                                try:
                                    response.payload_json = payload_bytes.decode('utf-8')
                                    offset = temp_offset
                                except UnicodeDecodeError:
                                    pass
                            elif header.serial_method == NO_SERIALIZATION:
                                response.payload, offset = read_res_payload(res, offset)
                        except Exception:
                            pass

    elif header.message_type == ERROR_INFORMATION:
        if offset + 4 > len(res):
            return response
        optional.errorCode = int.from_bytes(res[offset:offset + 4], "big", signed=True)
        offset += 4
        response.payload, offset = read_res_payload(res, offset)
        try:
            response.payload_json = response.payload.decode('utf-8')
        except (UnicodeDecodeError, TypeError):
            pass

    return response

def print_response(res: Response, tag: str):
    print(f'===> {tag} 头部: {res.header.__dict__}')
    print(f'===> {tag} 选项: {res.optional.__dict__}')
    payload_len = 0 if res.payload is None else len(res.payload)
    print(f'===> {tag} 负载长度: {payload_len}字节')
    if res.payload_json:
        print(f'===> {tag} JSON负载: {res.payload_json[:100]}...')

async def start_connection(ws):
    header = Header(message_type=FULL_CLIENT_REQUEST,
                   message_type_specific_flags=MsgTypeFlagWithEvent).as_bytes()
    optional = Optional(event=EVENT_Start_Connection).as_bytes()
    payload = str.encode("{}")
    await send_event(ws, header, optional, payload)
    print("===> 发送开始连接事件")

async def start_session(ws, speaker: str, session_id: str, audio_format='pcm', audio_sample_rate=48000):
    header = Header(message_type=FULL_CLIENT_REQUEST,
                   message_type_specific_flags=MsgTypeFlagWithEvent,
                   serial_method=JSON).as_bytes()
    optional = Optional(event=EVENT_StartSession, sessionId=session_id).as_bytes()
    payload = get_payload_bytes(event=EVENT_StartSession, speaker=speaker,
                               audio_format=audio_format, audio_sample_rate=audio_sample_rate)
    await send_event(ws, header, optional, payload)
    print(f"===> 发送开始会话事件 (会话ID: {session_id})")

async def send_text(ws, speaker: str, text: str, 
                   session_id: str, audio_format='pcm', audio_sample_rate=48000):
    header = Header(message_type=FULL_CLIENT_REQUEST,
                   message_type_specific_flags=MsgTypeFlagWithEvent,
                   serial_method=JSON).as_bytes()
    optional = Optional(event=EVENT_TaskRequest, sessionId=session_id).as_bytes()
    payload = get_payload_bytes(event=EVENT_TaskRequest, text=text, speaker=speaker,
                              audio_format=audio_format, audio_sample_rate=audio_sample_rate)
    await send_event(ws, header, optional, payload)
    print(f"===> 发送文本任务请求 (文本: '{text[:20]}...')")

async def finish_session(ws, session_id: str):
    header = Header(message_type=FULL_CLIENT_REQUEST,
                   message_type_specific_flags=MsgTypeFlagWithEvent,
                   serial_method=JSON).as_bytes()
    optional = Optional(event=EVENT_FinishSession, sessionId=session_id).as_bytes()
    payload = str.encode('{}')
    await send_event(ws, header, optional, payload)
    print(f"===> 发送结束会话事件 (会话ID: {session_id})")

async def finish_connection(ws):
    header = Header(message_type=FULL_CLIENT_REQUEST,
                   message_type_specific_flags=MsgTypeFlagWithEvent,
                   serial_method=JSON).as_bytes()
    optional = Optional(event=EVENT_FinishConnection).as_bytes()
    payload = str.encode('{}')
    await send_event(ws, header, optional, payload)
    print("===> 发送结束连接事件")

# ==== TTS合成函数（完整集成反馈）====
async def run_tts(appId: str, token: str, speaker: str, text: str, 
                 output_path: str, audio_player: AudioPlayer):
    """运行TTS合成服务"""
    # 发送合成开始反馈
    send_feedback(synthesis_started=True)
    
    url = 'wss://openspeech.bytedance.com/api/v3/tts/bidirection'
    ws_header = {
        "X-Api-App-Key": appId,
        "X-Api-Access-Key": token,
        "X-Api-Resource-Id": 'volc.service_type.10029',
        "X-Api-Connect-Id": str(uuid.uuid4()),
    }
    
    first_audio_chunk = True
    
    try:
        async with websockets.connect(url, additional_headers=ws_header, max_size=1000000000) as ws:
            print("🌐 WebSocket连接已建立")
            await start_connection(ws)
            
            # 接收连接响应
            res_bytes = await ws.recv()
            res = parser_response(res_bytes)
            print_response(res, '开始连接响应')
            
            if res.optional.event != EVENT_ConnectionStarted:
                error_msg = f"开始连接失败: {res.optional.response_meta_json or res.payload_json or '未知错误'}"
                send_feedback(error_message=error_msg)
                raise RuntimeError(error_msg)
                
            print("✅ 连接成功建立")
            
            session_id = str(uuid.uuid4()).replace('-', '')
        
            await start_session(ws, speaker, session_id, 
                               audio_format='pcm', audio_sample_rate=audio_player.TARGET_SAMPLE_RATE)
        
            res = parser_response(await ws.recv())
            print_response(res, '开始会话响应')
            
            if res.optional.event != EVENT_SessionStarted:
                error_msg = f"开始会话失败: {res.optional.response_meta_json or res.payload_json or '未知错误'}"
                send_feedback(error_message=error_msg)
                raise RuntimeError(error_msg)
                
            print(f"✅ 会话成功开始 (会话ID: {session_id})")

            await send_text(ws, speaker, text, session_id, 
                          audio_format='pcm', audio_sample_rate=audio_player.TARGET_SAMPLE_RATE)
            await finish_session(ws, session_id)
        
            async with aiofiles.open(output_path, mode="wb") as output_file:
                while True:
                    try:
                        res_bytes = await ws.recv()
                    except websockets.exceptions.ConnectionClosed:
                        print("🛑 WebSocket连接已关闭")
                        break
                        
                    res = parser_response(res_bytes)
                
                    # 处理音频片段
                    if res.optional.event == EVENT_TTSResponse and res.header.message_type == AUDIO_ONLY_RESPONSE:
                        if res.payload:
                            # 保存到文件
                            await output_file.write(res.payload)
                            
                            # 播放音频
                            audio_player.play_audio(res.payload)
                            
                            # 第一次收到音频时发送播放反馈
                            if first_audio_chunk:
                                send_feedback(audio_playing=True)
                                first_audio_chunk = False
                    
                    # 处理其他事件
                    elif res.optional.event in [EVENT_TTSSentenceStart, EVENT_TTSSentenceEnd]:
                        print(f"ℹ️ 收到事件: {'句开始' if res.optional.event == EVENT_TTSSentenceStart else '句结束'}")
                    
                    elif res.optional.event == EVENT_SessionFinished:
                        print("✅ 会话已完成")
                        print_response(res, '会话完成响应')
                        break
                    
                    elif res.optional.event == EVENT_SessionFailed:
                        error_msg = f"会话失败: {res.optional.response_meta_json or res.payload_json or '未知错误'}"
                        print_response(res, '会话失败响应')
                        send_feedback(error_message=error_msg)
                        raise RuntimeError(error_msg)
                    
                    else:
                        print(f"⚠️ 收到未知类型事件: {res.optional.event}")

            print(f"💾 音频保存到 {output_path}")

            await finish_connection(ws)
            try:
                res = parser_response(await ws.recv())
                print_response(res, '结束连接响应')
            except websockets.exceptions.ConnectionClosed:
                print("连接已关闭")
                
            print('✅ TTS合成成功完成')
    
    except Exception as e:
        error_msg = f"TTS发生错误: {str(e)}"
        print(error_msg)
        traceback.print_exc()
        send_feedback(error_message=error_msg)

# ==== 主函数 ====
async def main():
    """主功能函数"""
    # 信号处理
    exit_requested = False
    
    def signal_handler(signal, frame):
        nonlocal exit_requested
        print("\n🛑 收到 Ctrl+C 信号，准备退出...")
        exit_requested = True
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 初始化DDS通信
    print(f"🔧 初始化DDS通信，网络接口: {DDS_NETWORK_INTERFACE}")
    ChannelFactoryInitialize(networkInterface=DDS_NETWORK_INTERFACE)
    
    # 创建反馈发布器
    global FEEDBACK_PUB
    FEEDBACK_PUB = ChannelPublisher("TestFeedback", SpeechControl)
    FEEDBACK_PUB.Init()
    print("📤 反馈发布器已创建")
    
    # 创建语音控制订阅器
    speech_control_sub = ChannelSubscriber("SpeechControl", SpeechControl)
    speech_control_sub.Init()
    print("📡 语音控制订阅器已创建")
    
    # 创建音频播放器和语音处理器
    audio_player = AudioPlayer(device_index=0)
    speech_handler = SpeechControlHandler(audio_player)
    
    print("\n" + "="*60)
    print("🌟 语音系统已启动，等待指令...(Ctrl+C退出)")
    print("="*60 + "\n")
    
    try:
        while not exit_requested:
            try:
                # 读取DDS消息
                control_msg = speech_control_sub.Read(1)
                if control_msg is not None:
                    # 打印接收到的DDS消息
                    msg_info = ""
                    if hasattr(control_msg, 'text_to_speak') and control_msg.text_to_speak:
                        msg_info = f"文本: '{control_msg.text_to_speak[:20]}...'"
                    if hasattr(control_msg, 'stop_speaking') and control_msg.stop_speaking:
                        msg_info = "停止命令: 是"
                    if hasattr(control_msg, 'volume'):
                        msg_info += f", 音量: {control_msg.volume}%"
                    
                    print(f"📩 收到DDS消息: {msg_info}")
                    
                    # 将消息添加到处理器队列
                    speech_handler.add_command(control_msg)
                    
                    # 如果有文本需要合成
                    if hasattr(control_msg, 'text_to_speak') and control_msg.text_to_speak.strip():
                        print(f"🔊 启动语音合成: '{control_msg.text_to_speak[:20]}...'")
                        timestamp = int(time.time())
                        output_path = f"./tts_output_{timestamp}.pcm"
                        
                        # 启动语音合成任务
                        await run_tts(
                            appId=APP_ID,
                            token=TOKEN,
                            speaker="zh_female_shuangkuaisisi_moon_bigtts", 
                            text=control_msg.text_to_speak,
                            output_path=output_path,
                            audio_player=audio_player
                        )
                    
                # 短暂休眠
                await asyncio.sleep(DDS_SLEEP_INTERVAL)
                
            except Exception as e:
                error_msg = f"主循环错误: {str(e)}"
                print(error_msg)
                send_feedback(error_message=error_msg)
                if "take sample error" not in str(e) and "SampleState" not in str(e):
                    traceback.print_exc()
    
    finally:
        print("\n🧹 清理资源...")
        speech_handler.stop()
        audio_player.close()
        speech_control_sub.Close()
        print("✅ 程序已正常关闭")

if __name__ == "__main__":
    # 确保事件循环正确运行
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("\n🛑 主程序被Ctrl+C中断")
    finally:
        if not loop.is_closed():
            loop.close()
        print("⭕ 事件循环已关闭")