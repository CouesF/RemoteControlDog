# coding=utf-8
import asyncio
import base64
import gzip
import hmac
import json
import uuid
import pyaudio
import numpy as np
from enum import Enum
from hashlib import sha256
from urllib.parse import urlparse
from websockets.client import connect
import warnings

# 配置参数（替换为实际值）
appid = "2657638375"
token = "NHt65iYV2xQ-0Uv6VfO97BletTaOMtAn"
cluster = "volcengine_streaming_common"

# 协议头定义
PROTOCOL_VERSION = 0b0001
DEFAULT_HEADER_SIZE = 0b0001

# 消息类型
CLIENT_FULL_REQUEST = 0b0001
CLIENT_AUDIO_ONLY_REQUEST = 0b0010
SERVER_FULL_RESPONSE = 0b1001
SERVER_ACK = 0b1011
SERVER_ERROR_RESPONSE = 0b1111

# 序列类型
NO_SEQUENCE = 0b0000
POS_SEQUENCE = 0b0001
NEG_SEQUENCE = 0b0010
NEG_SEQUENCE_1 = 0b0011

# 序列化方法
NO_SERIALIZATION = 0b0000
JSON = 0b0001
THRIFT = 0b0011
CUSTOM_TYPE = 0b1111

# 压缩方法
NO_COMPRESSION = 0b0000
GZIP = 0b0001
CUSTOM_COMPRESSION = 0b1111

def generate_header(
    version=PROTOCOL_VERSION,
    message_type=CLIENT_FULL_REQUEST,
    message_type_specific_flags=NO_SEQUENCE,
    serial_method=JSON,
    compression_type=GZIP,
    reserved_data=0x00,
    extension_header=bytes()
):
    """生成协议头"""
    header = bytearray()
    header_size = int(len(extension_header) / 4) + 1
    header.append((version << 4) | header_size)
    header.append((message_type << 4) | message_type_specific_flags)
    header.append((serial_method << 4) | compression_type)
    header.append(reserved_data)
    header.extend(extension_header)
    return header

def generate_full_default_header():
    """生成完整请求头"""
    return generate_header()

def generate_audio_default_header():
    """生成音频请求头"""
    return generate_header(message_type=CLIENT_AUDIO_ONLY_REQUEST)

def generate_last_audio_default_header():
    """生成结束音频请求头"""
    return generate_header(
        message_type=CLIENT_AUDIO_ONLY_REQUEST,
        message_type_specific_flags=NEG_SEQUENCE
    )

def parse_response(res):
    """解析服务器响应"""
    protocol_version = res[0] >> 4
    header_size = res[0] & 0x0f
    message_type = res[1] >> 4
    message_type_specific_flags = res[1] & 0x0f
    serialization_method = res[2] >> 4
    message_compression = res[2] & 0x0f
    reserved = res[3]
    header_extensions = res[4:header_size * 4]
    payload = res[header_size * 4:]
    
    result = {}
    payload_msg = None
    payload_size = 0
    
    if message_type == SERVER_FULL_RESPONSE:
        payload_size = int.from_bytes(payload[:4], "big", signed=True)
        payload_msg = payload[4:]
    elif message_type == SERVER_ACK:
        seq = int.from_bytes(payload[:4], "big", signed=True)
        result['seq'] = seq
        if len(payload) >= 8:
            payload_size = int.from_bytes(payload[4:8], "big", signed=False)
            payload_msg = payload[8:]
    elif message_type == SERVER_ERROR_RESPONSE:
        code = int.from_bytes(payload[:4], "big", signed=False)
        result['code'] = code
        payload_size = int.from_bytes(payload[4:8], "big", signed=False)
        payload_msg = payload[8:]
    
    if payload_msg is None:
        return result
    
    if message_compression == GZIP:
        payload_msg = gzip.decompress(payload_msg)
    
    if serialization_method == JSON:
        payload_msg = json.loads(str(payload_msg, "utf-8"))
    elif serialization_method != NO_SERIALIZATION:
        payload_msg = str(payload_msg, "utf-8")
    
    result['payload_msg'] = payload_msg
    result['payload_size'] = payload_size
    return result

class AudioType(Enum):
    MICROPHONE = 2

class AsrWsClient:
    def __init__(self, cluster, **kwargs):
        self.cluster = cluster
        self.success_code = 1000
        self.seg_duration = int(kwargs.get("seg_duration", 200))
        self.nbest = int(kwargs.get("nbest", 1))
        self.appid = kwargs.get("appid", "")
        self.token = kwargs.get("token", "")
        self.ws_url = kwargs.get("ws_url", "wss://openspeech.bytedance.com/api/v2/asr")
        self.uid = kwargs.get("uid", "streaming_asr_demo")
        self.workflow = kwargs.get("workflow", "audio_in,resample,partition,vad,fe,decode,itn,nlu_punctuate")
        self.show_language = kwargs.get("show_language", False)
        self.show_utterances = kwargs.get("show_utterances", False)
        self.result_type = kwargs.get("result_type", "full")
        self.format = kwargs.get("format", "raw")
        self.rate = kwargs.get("sample_rate", 16000)
        self.language = kwargs.get("language", "zh-CN")
        self.bits = kwargs.get("bits", 16)
        self.channel = kwargs.get("channel", 1)
        self.codec = kwargs.get("codec", "pcm")
        self.audio_type = kwargs.get("audio_type", AudioType.MICROPHONE)
        self.secret = kwargs.get("secret", "access_secret")
        self.auth_method = kwargs.get("auth_method", "token")
        self.mic_device_index = kwargs.get("mic_device_index", None)
        self.mic_device_name = kwargs.get("mic_device_name", "USB Audio Device")
        self.stop_event = asyncio.Event()

    def construct_request(self, reqid):
        """构建请求参数"""
        # 固定使用16000Hz采样率，因为音频已重采样
        req = {
            'app': {
                'appid': self.appid,
                'cluster': self.cluster,
                'token': self.token,
            },
            'user': {
                'uid': self.uid
            },
            'request': {
                'reqid': reqid,
                'nbest': self.nbest,
                'workflow': self.workflow,
                'show_language': self.show_language,
                'show_utterances': self.show_utterances,
                'result_type': self.result_type,
                "sequence": 1
            },
            'audio': {
                'format': self.format,
                'rate': 16000,  # 固定为16000Hz
                'language': self.language,
                'bits': self.bits,
                'channel': self.channel,
                'codec': self.codec
            }
        }
        return req

    def token_auth(self):
        """Token认证方式"""
        return [('Authorization', f'Bearer; {self.token}')]

    def signature_auth(self, data):
        """签名认证方式"""
        header_dicts = {
            'Custom': 'auth_custom',
        }

        url_parse = urlparse(self.ws_url)
        input_str = f'GET {url_parse.path} HTTP/1.1\n'
        auth_headers = 'Custom'
        
        for header in auth_headers.split(','):
            input_str += f'{header_dicts[header]}\n'
        
        input_data = bytearray(input_str, 'utf-8')
        input_data += data
        mac = base64.urlsafe_b64encode(
            hmac.new(self.secret.encode('utf-8'), input_data, digestmod=sha256).digest())
        header_dicts['Authorization'] = f'HMAC256; access_token="{self.token}"; mac="{str(mac, "utf-8")}"; h="{auth_headers}"'
        
        return [(key, value) for key, value in header_dicts.items()]

    async def segment_data_processor(self, audio_generator):
        """处理音频分段并发送到服务器"""
        reqid = str(uuid.uuid4())
        request_params = self.construct_request(reqid)
        payload_bytes = json.dumps(request_params).encode()
        payload_bytes = gzip.compress(payload_bytes)
        
        full_client_request = bytearray(generate_full_default_header())
        full_client_request.extend(len(payload_bytes).to_bytes(4, 'big'))
        full_client_request.extend(payload_bytes)
        
        header = None
        if self.auth_method == "token":
            header = self.token_auth()
        elif self.auth_method == "signature":
            header = self.signature_auth(full_client_request)
            
        results = []
        
        try:
            async with connect(self.ws_url, extra_headers=header, max_size=1000000000) as ws:
                await ws.send(full_client_request)
                res = await ws.recv()
                result = parse_response(res)
                
                if 'payload_msg' in result and result['payload_msg']['code'] != self.success_code:
                    return result
                
                seq = 1
                try:
                    async for chunk, last in audio_generator:
                        if self.stop_event.is_set():
                            break
                            
                        payload_bytes = gzip.compress(chunk)
                        if last:
                            audio_header = generate_last_audio_default_header()
                        else:
                            audio_header = generate_audio_default_header()
                            
                        audio_request = bytearray(audio_header)
                        audio_request.extend(len(payload_bytes).to_bytes(4, 'big'))
                        audio_request.extend(payload_bytes)
                        
                        await ws.send(audio_request)
                        res = await ws.recv()
                        parsed = parse_response(res)
                        
                        if 'payload_msg' in parsed:
                            print("[Partial]", parsed['payload_msg'])
                            results.append(parsed['payload_msg'])
                            
                        seq += 1
                        
                except KeyboardInterrupt:
                    print("\n检测到用户中断，发送结束帧...")
                    # 发送结束帧通知服务器
                    last_header = generate_last_audio_default_header()
                    empty_payload = gzip.compress(b"")
                    end_request = bytearray(last_header)
                    end_request.extend(len(empty_payload).to_bytes(4, 'big'))
                    end_request.extend(empty_payload)
                    await ws.send(end_request)
                    
                    # 等待最终响应
                    try:
                        res = await asyncio.wait_for(ws.recv(), timeout=1.0)
                        parsed = parse_response(res)
                        if 'payload_msg' in parsed:
                            print("[Final]", parsed['payload_msg'])
                            results.append(parsed['payload_msg'])
                    except asyncio.TimeoutError:
                        print("等待最终响应超时")
                        
        except asyncio.CancelledError:
            print("任务被取消")
            
        return {"all_results": results}
    
    def resample_audio(self, data, original_rate, target_rate=16000):
        """
        实时音频重采样
        :param data: 原始音频数据 (bytes)
        :param original_rate: 原始采样率 (Hz)
        :param target_rate: 目标采样率 (Hz) 默认16000
        :return: 重采样后的音频数据 (bytes)
        """
        try:
            # 将字节数据转换为numpy数组
            audio_array = np.frombuffer(data, dtype=np.int16)
            
            # 计算重采样比例
            ratio = target_rate / original_rate
            target_length = int(len(audio_array) * ratio)
            
            # 线性插值重采样
            x_old = np.linspace(0, len(audio_array)-1, num=len(audio_array))
            x_new = np.linspace(0, len(audio_array)-1, num=target_length)
            
            resampled = np.interp(x_new, x_old, audio_array)
            resampled = resampled.astype(np.int16)
            
            return resampled.tobytes()
        except Exception as e:
            print(f"重采样错误: {e}")
            return data  # 出错时返回原始数据

    async def mic_audio_generator(self):
        """生成麦克风音频数据的异步生成器"""
        p = pyaudio.PyAudio()
        device_index = None
        
        try:
            # 打印所有可用设备信息
            print("可用音频设备:")
            for i in range(p.get_device_count()):
                dev_info = p.get_device_info_by_index(i)
                print(f"设备 {i}: {dev_info['name']}, 最大输入通道: {dev_info['maxInputChannels']}")
                if self.mic_device_name in dev_info['name']:
                    device_index = i
                    print(f"找到设备: {dev_info['name']} 索引 {i}")
            
            # 如果没找到指定设备，使用默认输入设备
            if device_index is None:
                default_device = p.get_default_input_device_info()
                device_index = default_device['index']
                print(f"使用默认输入设备: {default_device['name']}")
            
            # 获取设备详细信息
            device_info = p.get_device_info_by_index(device_index)
            print(f"选择设备: {device_info['name']}")
            print(f"最大输入通道: {device_info['maxInputChannels']}")
            print(f"默认采样率: {device_info['defaultSampleRate']}")
            
            # 尝试使用设备支持的采样率
            supported_rates = [8000, 16000, 44100, 48000]
            best_rate = None
            
            for rate in supported_rates:
                try:
                    if p.is_format_supported(
                        rate=rate,
                        input_device=device_index,
                        input_channels=self.channel,
                        input_format=pyaudio.paInt16
                    ):
                        best_rate = rate
                        print(f"设备支持采样率: {rate}Hz")
                        if rate == self.rate:
                            break
                except Exception as e:
                    print(f"采样率 {rate}Hz 不支持: {str(e)}")
            
            # 调整采样率
            if best_rate is None:
                default_rate = int(device_info['defaultSampleRate'])
                print(f"使用设备默认采样率: {default_rate}Hz")
                self.rate = default_rate
            elif best_rate != self.rate:
                print(f"使用支持的采样率 {best_rate}Hz 替代 {self.rate}Hz")
                self.rate = best_rate
            
            # 计算块大小
            bytes_per_second = self.rate * self.channel * (self.bits // 8)
            chunk_size_bytes = int(bytes_per_second * self.seg_duration / 1000)
            print(f"块大小: {chunk_size_bytes} 字节, 采样率: {self.rate}Hz")
            
            # 打开音频流
            stream = p.open(
                format=pyaudio.paInt16,
                channels=self.channel,
                rate=self.rate,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=chunk_size_bytes
            )
            
            print("开始录音... 按 Ctrl+C 停止")
            try:
                while not self.stop_event.is_set():
                    data = stream.read(chunk_size_bytes, exception_on_overflow=False)
                    
                    # 关键修复：实时重采样至16000Hz
                    if self.rate != 16000:
                        resampled_data = self.resample_audio(data, self.rate, 16000)
                    else:
                        resampled_data = data
                    
                    yield resampled_data, False
            except KeyboardInterrupt:
                print("\n停止录音")
                yield b"", True  # 发送结束信号
            finally:
                if stream.is_active():
                    stream.stop_stream()
                stream.close()
                
        finally:
            p.terminate()

    async def execute(self):
        """执行语音识别"""
        try:
            if self.audio_type == AudioType.MICROPHONE:
                return await self.segment_data_processor(self.mic_audio_generator())
            else:
                raise ValueError("不支持的音频类型")
        except asyncio.CancelledError:
            self.stop_event.set()
            return {"error": "Cancelled"}

def execute_microphone(cluster, **kwargs):
    """执行麦克风语音识别"""
    asr_client = AsrWsClient(
        cluster=cluster,
        audio_type=AudioType.MICROPHONE,
        **kwargs
    )
    try:
        return asyncio.run(asr_client.execute())
    except KeyboardInterrupt:
        print("程序被用户中断")
        return {"status": "Interrupted"}

def test_microphone():
    """测试麦克风语音识别"""
    print("启动麦克风测试，按Ctrl+C退出")
    result = execute_microphone(
        cluster=cluster,
        appid=appid,
        token=token,
        format="raw",
        codec="pcm",
        auth_method="token",
        result_type="single",       
        show_utterances=True,  
        sample_rate=16000,  # 初始尝试16000，但会自动调整
        bits=16,
        channel=1,
        mic_device_name="PnP Audio Device"
    )
    print("最终结果:", result)

if __name__ == '__main__':
    # 忽略Numpy的精度警告
    warnings.filterwarnings("ignore", message="numpy.ufunc size changed")
    test_microphone()