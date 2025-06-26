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
from pydub import AudioSegment
from pydub.playback import play
import io
import pyaudio

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

class RealtimeAudioPlayer:
    def __init__(self):
        self.buffer = b""
        self.buffer_size = 3  # 积累几个片段后播放
        self.is_playing = False
        
    def add_audio(self, audio_bytes):
        """添加音频片段"""
        self.buffer += audio_bytes
        if len(self.buffer) > 1024 * self.buffer_size and not self.is_playing:
            self._play()
    
    def _play(self):
        """在后台线程播放音频"""
        self.is_playing = True
        import threading
        
        def play_background():
            try:
                # 创建临时音频文件
                with io.BytesIO(self.buffer) as audio_file:
                    audio = AudioSegment.from_file(audio_file, format="mp3")
                    play(audio)
            except Exception as e:
                print(f"播放失败: {e}")
            finally:
                self.buffer = b""
                self.is_playing = False
        
        threading.Thread(target=play_background, daemon=True).start()
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

async def run_demo(appId: str, token: str, speaker: str, text: str, output_path: str):
    url = 'wss://openspeech.bytedance.com/api/v3/tts/bidirection'
    ws_header = {
        "X-Api-App-Key": appId,
        "X-Api-Access-Key": token,
        "X-Api-Resource-Id": 'volc.service_type.10029',
        "X-Api-Connect-Id": str(uuid.uuid4()),
    }

    print(f"Connecting to {url}...")
    p = pyaudio.PyAudio()
    # 打印可用音频设备（调试信息）
    print("可用音频设备:")
    for i in range(p.get_device_count()):
        try:
            info = p.get_device_info_by_index(i)
            if info['maxOutputChannels'] > 0:
                print(f"  设备 {i}: {info['name']} (最大采样率: {int(info['defaultSampleRate'])} Hz)")
        except:
            continue
    
    # 使用设备索引0（与科大讯飞代码相同）
    DOG_DEVICE_INDEX = 0
    TARGET_SAMPLE_RATE = 48000  # 与科大讯飞相同的采样率
    
    # 打开音频流
    stream = p.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=TARGET_SAMPLE_RATE,
        output=True,
        output_device_index=DOG_DEVICE_INDEX,
        frames_per_buffer=2048
    )
    
    print(f"▶ 已打开音频设备: 索引 {DOG_DEVICE_INDEX}")
    
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
        
        await start_session(ws, speaker, session_id, audio_format='pcm', audio_sample_rate=TARGET_SAMPLE_RATE)
        
        res = parser_response(await ws.recv())
        print_response(res, 'start_session response:')
        if res.optional.event != EVENT_SessionStarted:
            raise RuntimeError(f"Start session failed! Response: {res.optional.response_meta_json or res.payload_json or 'Unknown error'}")
        print(f"Session started successfully (Session ID: {session_id}).")

        await send_text(ws, speaker, text, session_id, audio_format='pcm', audio_sample_rate=TARGET_SAMPLE_RATE)
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
                        try:
                            stream.write(res.payload)
                        except Exception as e:
                            print(f"PyAudio 播放错误: {e}")
                    
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
        print('===> Demo finished successfully.')
        
    stream.stop_stream()
    stream.close()
    p.terminate()
    print("PyAudio 资源已释放")

if __name__ == "__main__":
    appId = "2657638375"
    token = "NHt65iYV2xQ-0Uv6VfO97BletTaOMtAn"

    if not appId or not token:
        print("错误：请在代码中设置您的 appId 和 token。")
        print("请访问 https://console.volcengine.com/iam/keymanage/ 获取。")
        exit(1)

    text = '火山引擎，让智能增长。欢迎使用火山引擎实时语音合成服务。'
    speaker = 'zh_female_shuangkuaisisi_moon_bigtts'
    output_path = './tts_output.pcm'

    print("Starting TTS demo...")
    print(f"  App ID: {appId[:4]}...")
    print(f"  Speaker: {speaker}")
    print(f"  Text: {text}")
    print(f"  Output Path: {output_path}")

    try:
        asyncio.run(run_demo(appId, token, speaker, text, output_path))
    except RuntimeError as e:
        print(f"\nAn error occurred: {e}")
    except websockets.exceptions.ConnectionClosedError as e:
        print(f"\nWebSocket connection closed unexpectedly: {e}")
    except Exception as e:
        import traceback
        print(f"\nAn unexpected error occurred: {e}")
        traceback.print_exc()