# -*- coding: utf-8 -*-
# @Time    : 2025/4/22 10:28
# @Author  : Mark White
# @FileName: vocal_notation.py
# @Software: PyCharm

import asyncio
import json
import uuid
import aiofiles
import websockets
from websockets.asyncio.client import ClientConnection
import pyaudio
import io
import os
import sys
import time
import threading
import struct
import traceback
import wave
import numpy as np
import base64
import hashlib
import hmac
import ssl
from datetime import datetime
from urllib.parse import urlencode
import websocket
import queue
from dataclasses import dataclass

# ==== 添加DDS相关导入和数据结构 ====
# --- FIX FOR CROSS-DIRECTORY IMPORT ---
current_script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_script_dir)
communication_dir_path = os.path.join(parent_dir, 'communication')
sys.path.append(communication_dir_path)
# --- END OF FIX ---

from dds_data_structure import SpeechControl
from unitree_sdk2py.core.channel import ChannelPublisher, ChannelSubscriber, ChannelFactoryInitialize

# ==== DDS通信配置 ====
DDS_NETWORK_INTERFACE = "enP8p1s0"  # 根据您的实际网络接口修改
DDS_SLEEP_INTERVAL = 0.01  # DDS读取间隔

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

# 音频播放器类
class AudioPlayer:
    def __init__(self, device_index=0):
        self.p = pyaudio.PyAudio()
        self.stream = None
        self.device_index = device_index
        self.TARGET_SAMPLE_RATE = 48000
        
        # 打印可用音频设备（调试信息）
        print("可用音频设备:")
        for i in range(self.p.get_device_count()):
            try:
                info = self.p.get_device_info_by_index(i)
                if info['maxOutputChannels'] > 0:
                    print(f"  设备 {i}: {info['name']} (最大采样率: {int(info['defaultSampleRate'])} Hz)")
            except:
                continue
        
        # 打开音频流
        self.stream = self.p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self.TARGET_SAMPLE_RATE,
            output=True,
            output_device_index=self.device_index,
            frames_per_buffer=2048
        )
        print(f"▶ 已打开音频设备: 索引 {self.device_index}")
        
        # 当前音量 (0-100)
        self.current_volume = 70
        self.set_system_volume(self.current_volume)
    
    def set_system_volume(self, volume_percent: int):
        """设置 USB 声卡的系统音量（通过 ALSA）"""
        volume = max(0, min(100, volume_percent))  # 限制在 0-100 之间
        self.current_volume = volume
        cmd = f"amixer -D hw:0 sset 'PCM' {volume}%"
        print(f"[系统音量控制] 执行命令: {cmd}")
        os.system(cmd)
    
    def amplify_audio(self, audio_data):
        """放大音频音量"""
        if not audio_data or len(audio_data) < 2:
            return audio_data
        
        try:
            audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)
            
            # 根据当前音量调整增益
            volume_factor = self.current_volume / 100.0 * 1.5 + 0.5  # 音量越大，增益越大
            
            # 基础放大倍数
            VOLUME_BOOST_1 = 2.8 * volume_factor
            amplified = audio_array * VOLUME_BOOST_1
            
            # 硬限幅处理
            MAX_AMPLITUDE = 32767 * 0.98
            compressed = np.where(np.abs(amplified) > MAX_AMPLITUDE, 
                                  np.sign(amplified) * MAX_AMPLITUDE, 
                                  amplified)
            
            # 二次增益提升
            VOLUME_BOOST_2 = 1.5
            boosted = compressed * VOLUME_BOOST_2
            
            # 最终限幅保证不削波
            final_audio = np.clip(boosted, -32768, 32767).astype(np.int16)
            
            return final_audio.tobytes()
        except Exception as e:
            print(f"多级音量放大失败: {e}")
            return audio_data
    
    def play_audio(self, audio_data):
        """播放音频数据"""
        if self.stream and self.stream.is_active():
            try:
                # 音量放大
                amplified_audio = self.amplify_audio(audio_data)
                self.stream.write(amplified_audio)
            except Exception as e:
                print(f"PyAudio 播放错误: {e}")
        else:
            print("音频流未准备好，无法播放")
    
    def close(self):
        """释放音频资源"""
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            print("音频流已关闭")
        self.p.terminate()
        print("PyAudio 资源已释放")

# 语音控制处理器类
class SpeechControlHandler:
    def __init__(self, audio_player):
        self.audio_player = audio_player
        self.command_queue = queue.Queue()
        self.running = True
        self.handler_thread = threading.Thread(target=self._process_queue, daemon=True)
        self.handler_thread.start()
    
    def add_command(self, control_msg):
        self.command_queue.put(control_msg)
    
    def _process_queue(self):
        while self.running:
            try:
                control_msg = self.command_queue.get(timeout=0.5)
                
                # 处理音量设置
                if hasattr(control_msg, 'volume'):
                    print(f"收到音量设置请求: {control_msg.volume}%")
                    self.audio_player.set_system_volume(control_msg.volume)
                
                # 处理语音播放
                if control_msg.text_to_speak and control_msg.text_to_speak.strip():
                    print(f"收到语音命令: {control_msg.text_to_speak[:20]}...")
                    # 在实际应用中，这里应该触发语音合成
                    # 但在本程序中，实际合成在run_tts函数中完成
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"处理命令时出错: {e}")
    
    def stop(self):
        self.running = False
        self.handler_thread.join(timeout=1.0)

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

def get_payload_bytes(uid='1234', event=EVENT_NONE, text='', speaker='', audio_format='pcm',
                      audio_sample_rate=48000) -> bytes:
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
    return str.encode(json.dumps(payload_dict))

async def send_event(ws: ClientConnection, header: bytes, optional: bytes | None = None,
                     payload: bytes | None = None):
    if not isinstance(ws, ClientConnection):
        raise TypeError(f"Expected websockets.asyncio.client.ClientConnection, got {type(ws)}")

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
        raise RuntimeError(f"Received string message, expected bytes. Message: {res}")
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
                 raise ValueError(f"Response too short for Event field. Offset: {offset}, Length: {len(res)}")
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
             raise ValueError(f"Response too short for ErrorCode field. Offset: {offset}, Length: {len(res)}")
        optional.errorCode = int.from_bytes(res[offset:offset + 4], "big", signed=True)
        offset += 4
        response.payload, offset = read_res_payload(res, offset)
        try:
            response.payload_json = response.payload.decode('utf-8')
        except (UnicodeDecodeError, TypeError):
            pass

    return response

def print_response(res: Response, tag: str):
    print(f'===>{tag} header:{res.header.__dict__}')
    print(f'===>{tag} optional:{res.optional.__dict__}')
    payload_len = 0 if res.payload is None else len(res.payload)
    print(f'===>{tag} payload len:{payload_len}')
    print(f'===>{tag} payload_json:{res.payload_json}')

async def start_connection(ws: ClientConnection):
    header = Header(message_type=FULL_CLIENT_REQUEST,
                    message_type_specific_flags=MsgTypeFlagWithEvent).as_bytes()
    optional = Optional(event=EVENT_Start_Connection).as_bytes()
    payload = str.encode("{}")
    await send_event(ws, header, optional, payload)
    print("===> Sent Start Connection event")

async def start_session(ws: ClientConnection, speaker: str, session_id: str,audio_format='pcm', audio_sample_rate=48000):
    header = Header(message_type=FULL_CLIENT_REQUEST,
                    message_type_specific_flags=MsgTypeFlagWithEvent,
                    serial_method=JSON).as_bytes()
    optional = Optional(event=EVENT_StartSession, sessionId=session_id).as_bytes()
    payload = get_payload_bytes(event=EVENT_StartSession, speaker=speaker)
    await send_event(ws, header, optional, payload)
    print(f"===> Sent Start Session event (Session ID: {session_id})")

async def send_text(ws: ClientConnection, speaker: str, text: str, session_id: str,audio_format='pcm', audio_sample_rate=48000):
    header = Header(message_type=FULL_CLIENT_REQUEST,
                    message_type_specific_flags=MsgTypeFlagWithEvent,
                    serial_method=JSON).as_bytes()
    optional = Optional(event=EVENT_TaskRequest, sessionId=session_id).as_bytes()
    payload = get_payload_bytes(event=EVENT_TaskRequest, text=text, speaker=speaker)
    await send_event(ws, header, optional, payload)
    print(f"===> Sent Task Request event (Text: '{text[:20]}...')")

async def finish_session(ws: ClientConnection, session_id: str):
    header = Header(message_type=FULL_CLIENT_REQUEST,
                    message_type_specific_flags=MsgTypeFlagWithEvent,
                    serial_method=JSON).as_bytes()
    optional = Optional(event=EVENT_FinishSession, sessionId=session_id).as_bytes()
    payload = str.encode('{}')
    await send_event(ws, header, optional, payload)
    print(f"===> Sent Finish Session event (Session ID: {session_id})")

async def finish_connection(ws: ClientConnection):
    header = Header(message_type=FULL_CLIENT_REQUEST,
                    message_type_specific_flags=MsgTypeFlagWithEvent,
                    serial_method=JSON).as_bytes()
    optional = Optional(event=EVENT_FinishConnection).as_bytes()
    payload = str.encode('{}')
    await send_event(ws, header, optional, payload)
    print("===> Sent Finish Connection event")

async def run_tts(appId: str, token: str, speaker: str, text: str, output_path: str, audio_player: AudioPlayer):
    url = 'wss://openspeech.bytedance.com/api/v3/tts/bidirection'
    ws_header = {
        "X-Api-App-Key": appId,
        "X-Api-Access-Key": token,
        "X-Api-Resource-Id": 'volc.service_type.10029',
        "X-Api-Connect-Id": str(uuid.uuid4()),
    }
   
    async with websockets.connect(url, additional_headers=ws_header, max_size=1000000000) as ws:
            print("WebSocket connection established.")
            await start_connection(ws)
            res_bytes = await ws.recv()
            res = parser_response(res_bytes)
            print_response(res, 'start_connection response:')
            if res.optional.event != EVENT_ConnectionStarted:
                raise RuntimeError(f"Start connection failed. Response: {res.optional.response_meta_json or res.payload_json or 'Unknown error'}")
            print("Connection started successfully.")
            
            session_id = uuid.uuid4().__str__().replace('-', '')
        
            await start_session(ws, speaker, session_id, audio_format='pcm', audio_sample_rate=audio_player.TARGET_SAMPLE_RATE)
        
            res = parser_response(await ws.recv())
            print_response(res, 'start_session response:')
            if res.optional.event != EVENT_SessionStarted:
                    raise RuntimeError(f"Start session failed! Response: {res.optional.response_meta_json or res.payload_json or 'Unknown error'}")
            print(f"Session started successfully (Session ID: {session_id}).")

            await send_text(ws, speaker, text, session_id, audio_format='pcm', audio_sample_rate=audio_player.TARGET_SAMPLE_RATE)
            await finish_session(ws, session_id)
        
            async with aiofiles.open(output_path, mode="wb") as output_file:
                    while True:
                        res_bytes = await ws.recv()
                        res = parser_response(res_bytes)
                
                # 处理音频片段
                        if res.optional.event == EVENT_TTSResponse and res.header.message_type == AUDIO_ONLY_RESPONSE:
                            if res.payload:
                        # 保存到文件
                                await output_file.write(res.payload)
                                audio_player.play_audio(res.payload)
                    
                            else:
                                print("Warning: Received EVENT_TTSResponse with empty payload.")
                        elif res.optional.event in [EVENT_TTSSentenceStart, EVENT_TTSSentenceEnd]:
                            print(f"Received event: {'Sentence Start' if res.optional.event == EVENT_TTSSentenceStart else 'Sentence End'}. Info: {res.payload_json}")
                            continue
                        elif res.optional.event == EVENT_SessionFinished:
                            print("Received Session Finished event. Audio stream ended.")
                            print_response(res, 'session_finished response:')
                            break
                        elif res.optional.event == EVENT_SessionFailed:
                             print_response(res, 'session_failed response:')
                             raise RuntimeError(f"Session failed during audio receive. Info: {res.optional.response_meta_json or res.payload_json}")
                        else:
                            print(f"Warning: Received unexpected event or message type during audio receive.")
                            print_response(res, 'unexpected_response:')

            print(f"Audio saved to {output_path}")

            await finish_connection(ws)
            res = parser_response(await ws.recv())
            print_response(res, 'finish_connection response:')
            print('===> TTS finished successfully.')

# 主功能
async def main():
    appId = "2657638375"
    token = "NHt65iYV2xQ-0Uv6VfO97BletTaOMtAn"
    
    if not appId or not token:
        print("错误：请在代码中设置您的 appId 和 token。")
        print("请访问 https://console.volcengine.com/iam/keymanage/ 获取。")
        return
    
    # ==== 初始化DDS通信 ====
    print(f"正在初始化DDS通信，网络接口: {DDS_NETWORK_INTERFACE}")
    ChannelFactoryInitialize(networkInterface=DDS_NETWORK_INTERFACE)
    
    # 创建语音控制订阅器
    speech_control_sub = ChannelSubscriber("SpeechControl", SpeechControl)
    speech_control_sub.Init()
    print("DDS初始化完成，准备接收语音控制命令")
    
    # 创建音频播放器和语音处理器
    audio_player = AudioPlayer()
    speech_handler = SpeechControlHandler(audio_player)
    
    try:
        # 主循环：监听DDS消息并处理
        exit_requested = False
        print("等待语音控制指令... (输入Ctrl+C退出)")
        
        while not exit_requested:
            try:
                # 读取DDS消息
                control_msg = speech_control_sub.Read(1)
                if control_msg is not None:
                    # 打印接收到的DDS消息详情
                    print(f"收到DDS语音控制消息: "
                          f"text_to_speak='{control_msg.text_to_speak[:20]}...', "
                          f"stop_speaking={control_msg.stop_speaking}, "
                          f"volume={control_msg.volume}%")
                          
                    # 将消息添加到处理器队列
                    speech_handler.add_command(control_msg)
                    
                    # 如果有文本需要合成
                    if control_msg.text_to_speak and control_msg.text_to_speak.strip():
                        print(f"合成文本: '{control_msg.text_to_speak[:20]}...'")
                        output_path = f"./tts_output_{int(time.time())}.pcm"
                        
                        # 启动语音合成任务
                        await run_tts(
                            appId, token, "zh_female_shuangkuaisisi_moon_bigtts", 
                            control_msg.text_to_speak, output_path, audio_player
                        )
                    
                # 短暂休眠避免CPU占用过高
                await asyncio.sleep(DDS_SLEEP_INTERVAL)
                
            except Exception as e:
                if "take sample error" not in str(e) and "SampleState" not in str(e):
                    print(f"DDS读取失败: {e}")
                elif "Operation not permitted" in str(e):
                    continue  # 临时跳过权限错误
                else:
                    print(f"主循环错误: {e}")
                    exit_requested = True
    
    except KeyboardInterrupt:
        print("收到 Ctrl+C 信号，准备退出程序...")
    
    except Exception as e:
        print(f"主程序发生错误: {e}")
        traceback.print_exc()
    
    finally:
        # 清理资源
        print("正在关闭所有资源...")
        speech_handler.stop()
        audio_player.close()
        speech_control_sub.Close()
        print("程序已关闭")

if __name__ == "__main__":
    asyncio.run(main())