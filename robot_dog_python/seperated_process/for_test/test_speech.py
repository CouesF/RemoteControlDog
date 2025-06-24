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

#可以发声音但是咕噜咕噜

# ====== 科大讯飞TTS配置 ======
APPID = '5a5d1cf3'  # 替换为你的APPID
API_KEY = '303dc3d3e0d3dca28c3708c77bdeecad'  # 替换为你的API_KEY
API_SECRET = 'YWZlMjZmY2VlNDk1NmQ2MjNmZmZhNTNh'  # 替换为你的API_SECRET
DOG_DEVICE_INDEX = 0  # 根据机器狗连接的音频设备调整

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

        # 打印可用音频设备
        print("可用音频设备:")
        for i in range(self.p.get_device_count()):
            info = self.p.get_device_info_by_index(i)
            if info['maxOutputChannels'] > 0:
                print(f"  设备 {i}: {info['name']}")

    def on_message(self, ws, message):
        try:
            message = json.loads(message)
            code = message.get("code")
            if code != 0:
                print(f"TTS错误: {message.get('message')}, 代码: {code}")
                return

            audio_data = base64.b64decode(message["data"].get("audio", b""))
            
            # 确保音频流已创建
            if not self.stream or not self.stream.is_active():
                self.create_audio_stream()
            
            # 播放音频数据
            self.stream.write(audio_data)

            if message["data"].get("status") == 2:
                print("语音合成完成")
                self.close()
        except Exception as e:
            print(f"处理音频数据时出错: {e}")

    def on_error(self, ws, error):
        print(f"WebSocket错误: {error}")
        self.close()

    def on_close(self, ws, close_status_code, close_msg):
        print(f"WebSocket关闭, 状态码: {close_status_code}")
        self.close()

    def on_open(self, ws):
        def run():
            data = {
                "common": {"app_id": self.appid},
                "business": {
                    "aue": "raw",
                    "auf": "audio/L16;rate=48000",
                    "vcn": "x4_xiaoyan",
                    "tte": "utf8"
                },
                "data": {
                    "status": 2,
                    "text": str(base64.b64encode(self.text.encode('utf-8')), "UTF8")
                }
            }
            ws.send(json.dumps(data))
            print(f"开始语音合成: {self.text[:20]}...")

        thread.start_new_thread(run, ())

    def create_audio_stream(self):
        """创建PyAudio输出流"""
        if self.stream and self.stream.is_active():
            self.stream.stop_stream()
            self.stream.close()
            
        # 使用机器狗专用音频设备
        self.stream = self.p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=48000,
            output=True,
            output_device_index=self.device_index,
            frames_per_buffer=1024
        )
        print(f"▶ 音频输出到设备: {self.device_index} - {self.p.get_device_info_by_index(self.device_index)['name']}")

    def play(self, text):
        """播放指定文本的语音"""
        self.text = text
        self.running = True
        print(f"请求TTS服务: {text[:20]}...")
        
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
        
        if self.stream and self.stream.is_active():
            self.stream.stop_stream()
            self.stream.close()
            print("音频流已关闭")
            
        if self.websocket:
            self.websocket.close()
            print("WebSocket连接已关闭")
        
        # 保留PyAudio实例以便后续使用
        # self.p.terminate()  # 注意：不要在这里终止，保持PyAudio实例活跃

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
    text = "你好，我是机器狗。我现在可以通过科大讯飞的语音合成技术实时和你交流了！"
    
    # 播放语音
    tts_player.play(text)
    
    # 后续可以继续播放其他文本
    # tts_player.play("这是第二条消息")
    
    # 程序结束时关闭资源
    tts_player.close()
    tts_player.p.terminate()