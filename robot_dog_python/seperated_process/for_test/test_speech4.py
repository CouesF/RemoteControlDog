import pyaudio
import wave
import numpy as np
import os
import _thread as thread
import base64
import hashlib
import hmac
import json
import ssl
from datetime import datetime
from urllib.parse import urlencode
import websocket
import numpy as np
import time

# 可以发声，声音大了一点
# ====== 科大讯飞TTS配置 ======
APPID = '5a5d1cf3'
API_KEY = '303dc3d3e0d3dca28c3708c77bdeecad'
API_SECRET = 'YWZlMjZmY2VlNDk1NmQ2MjNmZmZhNTNh'
DOG_DEVICE_INDEX = 0  # 根据机器狗连接的音频设备调整
TARGET_SAMPLE_RATE = 48000  # 强制使用48000Hz采样率

class TTSPlayer:
    def __init__(self, appid, api_key, api_secret, device_index=0):
        self.appid = appid
        self.api_key = api_key
        self.api_secret = api_secret
        self.device_index = device_index
        self.p = pyaudio.PyAudio()
        self.stream = None
        self.websocket = None
        self.running = False
        self.audio_queue = []

        # 打印可用音频设备
        print("可用音频设备:")
        for i in range(self.p.get_device_count()):
            try:
                info = self.p.get_device_info_by_index(i)
                if info['maxOutputChannels'] > 0:
                    print(f"  设备 {i}: {info['name']} (最大采样率: {int(info['defaultSampleRate'])} Hz)")
            except:
                continue
    
    def resample_audio(self, data, original_rate):
        """将音频重采样到目标采样率"""
        if not data or len(data) == 0:
            return b""
            
        if original_rate == TARGET_SAMPLE_RATE:
            return data
        
        try:
            # 计算重采样比例
            ratio = TARGET_SAMPLE_RATE / original_rate
            
            # 将字节数据转换为numpy数组
            audio_array = np.frombuffer(data, dtype=np.int16)
            
            # 避免空数组
            if len(audio_array) == 0:
                return b""
            
            # 计算新长度
            new_length = int(len(audio_array) * ratio)
            
            # 线性插值重采样
            resampled = np.interp(
                np.linspace(0, len(audio_array) - 1, new_length),
                np.arange(len(audio_array)),
                audio_array
            ).astype(np.int16)
            
            return resampled.tobytes()
        except Exception as e:
            print(f"重采样失败: {e}")
            return data  # 返回原始数据作为回退
        
    def amplify_audio(self, audio_data, gain_factor=5.5):
        """放大音频音量"""
        if not audio_data or len(audio_data) < 2:  # 确保有足够的音频数据
            return audio_data
        
        try:
           # 将字节数据转换为numpy数组
            audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)
            
            # 第一级：基础增益放大
            VOLUME_BOOST_1 = 4.0  # 基础放大倍数
            amplified = audio_array * VOLUME_BOOST_1
            
            # 第二级：硬限幅处理
            MAX_AMPLITUDE = 32767 * 0.95  # 保留2%余量防止削波
            compressed = np.where(np.abs(amplified) > MAX_AMPLITUDE, 
                                  np.sign(amplified) * MAX_AMPLITUDE, 
                                  amplified)
            
            # 第三级：二次增益提升
            VOLUME_BOOST_2 = 2.0  # 二次放大倍数
            boosted = compressed * VOLUME_BOOST_2
            
            # 最终限幅保证不削波
            final_audio = np.clip(boosted, -32768, 32767).astype(np.int16)
            
            return final_audio.tobytes()
        except Exception as e:
            print(f"多级音量放大失败: {e}")
            return audio_data  # 出错时返回原始数据

    def on_message(self, ws, message):
        try:
            message = json.loads(message)
            code = message.get("code")
            if code != 0:
                print(f"TTS错误: {message.get('message')}, 代码: {code}")
                return

            # 安全获取音频数据
            data_section = message.get("data", {})
            audio_str = data_section.get("audio")
            
            # 检查音频数据是否有效
            if not audio_str:
                print("警告: 没有接收到音频数据")
                # 即使没有音频数据也要检查状态
                if data_section.get("status") == 2:
                    print("语音合成完成")
                    self.close()
                return
            
            try:
                audio_data = base64.b64decode(audio_str)
            except:
                print("警告: 无法解码音频数据")
                return
                
            # 确保是有效的字节数据
            if not isinstance(audio_data, bytes) or len(audio_data) == 0:
                print("警告: 无效的音频数据 (长度为零或类型错误)")
                return
            
            # 如果流不可用，尝试创建
            if not self.stream:
                self.try_create_audio_stream()
            
            # 音量放大 - 核心位置!!!
            VOLUME_BOOST = 2.9  # 可调整值：1.5-3.0
            audio_data = self.amplify_audio(audio_data, VOLUME_BOOST)
            
            # 播放音频数据
            if self.stream and self.stream.is_active():
                try:
                    # 重采样到48000Hz
                    resampled_data = self.resample_audio(audio_data, 16000)
                    self.stream.write(resampled_data)
                except Exception as e:
                    print(f"音频播放失败: {e}")
            else:
                # 缓存音频数据，直到成功创建流
                self.audio_queue.append(audio_data)
                self.try_create_audio_stream()
                print("音频流不可用，缓存数据...")

            # 检查合成是否完成
            if data_section.get("status") == 2:
                print("语音合成完成")
                self.close()
                
        except Exception as e:
            print(f"处理消息时出错: {e}")
            # 尝试关闭当前流，下次重新打开
            if self.stream:
                try:
                    self.stream.close()
                except:
                    pass
                self.stream = None
                print("关闭音频流以重试")

    def on_error(self, ws, error):
        print(f"WebSocket错误: {error}")
        self.close()

    def on_close(self, ws, close_status_code, close_msg):
        print(f"WebSocket关闭, 状态码: {close_status_code}")
        self.close()

    def try_create_audio_stream(self, retries=5, delay=0.3):
        """尝试创建音频流"""
        for i in range(retries):
            try:
                if self.stream:
                    try:
                        self.stream.close()
                    except:
                        pass
                    self.stream = None
                    
                # 使用机器狗专用音频设备
                self.stream = self.p.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=TARGET_SAMPLE_RATE,
                    output=True,
                    output_device_index=self.device_index,
                    frames_per_buffer=2048
                )
                
                print(f"▶ 成功打开音频设备: {self.device_index} (采样率: {TARGET_SAMPLE_RATE} Hz)")
                
                # 播放缓存的音频
                while self.audio_queue:
                    audio_data = self.audio_queue.pop(0)
                    resampled_data = self.resample_audio(audio_data, 16000)
                    try:
                        self.stream.write(resampled_data)
                    except:
                        print("播放缓存音频失败")
                    
                return True
            except Exception as e:
                print(f"创建音频流失败 (尝试 {i+1}/{retries}): {str(e)}")
                time.sleep(delay)
        
        print(f"❌ 无法打开音频设备: {self.device_index} (采样率: {TARGET_SAMPLE_RATE} Hz)")
        return False

    def on_open(self, ws):
        def run():
            # 尝试使用48000Hz采样率
            data = {
                "common": {"app_id": self.appid},
                "business": {
                    "aue": "raw",
                    "auf": f"audio/L16;rate={TARGET_SAMPLE_RATE}",
                    "vcn": "x4_yezi",
                    "tte": "utf8"
                },
                "data": {
                    "status": 2,
                    "text": str(base64.b64encode(self.text.encode('utf-8')), "UTF8")
                }
            }
            ws.send(json.dumps(data))
            print(f"开始语音合成: {self.text[:20]}... (采样率: {TARGET_SAMPLE_RATE} Hz)")

        thread.start_new_thread(run, ())

    def play(self, text):
        """播放指定文本的语音"""
        self.text = text
        self.running = True
        print(f"请求TTS服务: {text[:20]}...")
        self.audio_queue = []  # 清空缓存
        
        # 创建WebSocket连接
        ws_url = self._create_url()
        self.websocket = websocket.WebSocketApp(
            ws_url,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )
        
        # 启动WebSocket连接
        self.websocket.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})

    def _create_url(self):
        """创建带有签名的WebSocket URL"""
        url = 'wss://tts-api.xfyun.cn/v2/tts'
        date = datetime.now().strftime("%a, %d %b %Y %H:%M:%S GMT")
        
        signature_origin = f"host: ws-api.xfyun.cn\ndate: {date}\nGET /v2/tts HTTP/1.1"
        signature_sha = hmac.new(
            self.api_secret.encode('utf-8'),
            signature_origin.encode('utf-8'),
            hashlib.sha256
        ).digest()
        
        signature_sha_base64 = base64.b64encode(signature_sha).decode()
        authorization_origin = (
            f'api_key="{self.api_key}", algorithm="hmac-sha256", '
            f'headers="host date request-line", signature="{signature_sha_base64}"'
        )
        authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode()
        
        params = {"authorization": authorization, "date": date, "host": "ws-api.xfyun.cn"}
        return f"{url}?{urlencode(params)}"

    def close(self):
        """关闭所有资源"""
        self.running = False
        
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
                print("音频流已关闭")
            except:
                print("关闭音频流时出错")
            
        if self.websocket:
            try:
                self.websocket.close()
                print("WebSocket连接已关闭")
            except:
                print("关闭WebSocket时出错")
        
        # 终止PyAudio实例
        try:
            self.p.terminate()
            print("PyAudio已终止")
        except:
            print("终止PyAudio时出错")

# ====== 主程序 ======
if __name__ == "__main__":
    # 创建TTS播放器实例
    tts_player = TTSPlayer(
        appid=APPID, 
        api_key=API_KEY, 
        api_secret=API_SECRET, 
        device_index=DOG_DEVICE_INDEX
    )
    
    # 示例文本
    text = "我是一只机器狗"
    
    # 播放语音
    try:
        tts_player.play(text)
    except Exception as e:
        print(f"播放过程中发生错误: {e}")
    finally:
        tts_player.close()