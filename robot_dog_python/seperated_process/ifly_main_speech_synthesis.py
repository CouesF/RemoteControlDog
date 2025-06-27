import sys
import pyaudio
import wave
import numpy as np
import os
import threading
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
import queue
from dataclasses import dataclass

# --- FIX FOR CROSS-DIRECTORY IMPORT ---
current_script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_script_dir)
communication_dir_path = os.path.join(parent_dir, 'communication')
sys.path.append(communication_dir_path)
# --- END OF FIX ---

from dds_data_structure import SpeechControl
from unitree_sdk2py.core.channel import ChannelPublisher, ChannelSubscriber, ChannelFactoryInitialize

# ====== 科大讯飞TTS配置 ======
APPID = '5a5d1cf3'
API_KEY = '303dc3d3e0d3dca28c3708c77bdeecad'
API_SECRET = 'YWZlMjZmY2VlNDk1NmQ2MjNmZmZhNTNh'
DOG_DEVICE_INDEX = 0  # 根据机器狗连接的音频设备调整
TARGET_SAMPLE_RATE = 48000  # 强制使用48000Hz采样率
DDS_NETWORK_INTERFACE = "enP8p1s0"  # 根据您的实际网络接口修改

def set_system_volume(volume_percent: int):
    """设置 USB 声卡的系统音量（通过 ALSA）"""
    volume = max(0, min(100, volume_percent))  # 限制在 0-100 之间
    cmd = f"amixer -D hw:0 sset 'PCM' {volume}%"
    print(f"[系统音量控制] 执行命令: {cmd}")
    os.system(cmd)

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
        self.stop_requested = False
        self.current_volume = 70  # 默认音量设置为70%

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
            ratio = TARGET_SAMPLE_RATE / original_rate
            audio_array = np.frombuffer(data, dtype=np.int16)
            
            if len(audio_array) == 0:
                return b""
            
            new_length = int(len(audio_array) * ratio)
            resampled = np.interp(
                np.linspace(0, len(audio_array) - 1, new_length),
                np.arange(len(audio_array)),
                audio_array
            ).astype(np.int16)
            
            return resampled.tobytes()
        except Exception as e:
            print(f"重采样失败: {e}")
            return data
        
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

    def on_message(self, ws, message):
        try:
            if self.stop_requested:
                print("停止请求收到，终止语音合成")
                self.close()
                return
            
            message = json.loads(message)
            code = message.get("code")
            if code != 0:
                print(f"TTS错误: {message.get('message')}, 代码: {code}")
                return

            data_section = message.get("data", {})
            audio_str = data_section.get("audio")
            
            if not audio_str:
                print("警告: 没有接收到音频数据")
                if data_section.get("status") == 2:
                    print("语音合成完成")
                    self.close()
                return
            
            try:
                audio_data = base64.b64decode(audio_str)
            except:
                print("警告: 无法解码音频数据")
                return
                
            if not isinstance(audio_data, bytes) or len(audio_data) == 0:
                print("警告: 无效的音频数据 (长度为零或类型错误)")
                return
            
            if not self.stream:
                self.try_create_audio_stream()
            
            # 音量放大
            audio_data = self.amplify_audio(audio_data)
            
            if self.stream and self.stream.is_active():
                try:
                    resampled_data = self.resample_audio(audio_data, 16000)
                    self.stream.write(resampled_data)
                except Exception as e:
                    print(f"音频播放失败: {e}")
            else:
                self.audio_queue.append(audio_data)
                self.try_create_audio_stream()
                print("音频流不可用，缓存数据...")

            if data_section.get("status") == 2:
                print("语音合成完成")
                self.close()
                
        except Exception as e:
            print(f"处理消息时出错: {e}")
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
        for i in range(retries):
            try:
                if self.stream:
                    try:
                        self.stream.close()
                    except:
                        pass
                    self.stream = None
                    
                self.stream = self.p.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=TARGET_SAMPLE_RATE,
                    output=True,
                    output_device_index=self.device_index,
                    frames_per_buffer=2048
                )
                
                print(f"▶ 成功打开音频设备: {self.device_index} (采样率: {TARGET_SAMPLE_RATE} Hz)")
                
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
            data = {
                "common": {"app_id": self.appid},
                "business": {
                    "aue": "raw",
                    "auf": f"audio/L16;rate={TARGET_SAMPLE_RATE}",
                    "vcn": "aisbabyxu",
                    "tte": "utf8"
                },
                "data": {
                    "status": 2,
                    "text": str(base64.b64encode(self.text.encode('utf-8')), "UTF8")
                }
            }
            ws.send(json.dumps(data))
            print(f"开始语音合成: {self.text[:20]}... (采样率: {TARGET_SAMPLE_RATE} Hz)")

        thread = threading.Thread(target=run)
        thread.daemon = True
        thread.start()

    def play(self, text):
        self.text = text
        self.running = True
        print(f"请求TTS服务: {text[:20]}...")
        self.audio_queue = []
        
        ws_url = self._create_url()
        self.websocket = websocket.WebSocketApp(
            ws_url,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )
        
        ws_thread = threading.Thread(
            target=self.websocket.run_forever,
            kwargs={"sslopt": {"cert_reqs": ssl.CERT_NONE}},
            daemon=True
        )
        ws_thread.start()

    def stop(self):
        self.stop_requested = True
        if self.websocket:
            try:
                self.websocket.close()
            except:
                pass
        self.close()

    def set_volume(self, volume_percent: int):
        """设置音量并更新当前音量值"""
        self.current_volume = max(0, min(100, volume_percent))
        set_system_volume(self.current_volume)
        print(f"[音量控制] 设置系统音量为: {self.current_volume}%")

    def _create_url(self):
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
        self.running = False
        self.stop_requested = True
        
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
                print("音频流已关闭")
            except:
                print("关闭音频流时出错")
            
        if self.websocket:
            try:
                print("尝试关闭 WebSocket")
                self.websocket.keep_running = False
                self.websocket.close()
                print("WebSocket连接已关闭")
            except:
                print("关闭WebSocket时出错")
        
        try:
            self.p.terminate()
            print("PyAudio已终止")
        except:
            print("终止PyAudio时出错")

class SpeechControlHandler:
    def __init__(self, tts_player):
        self.tts_player = tts_player
        self.current_task = None
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
                    self.tts_player.set_volume(control_msg.volume)

                # 处理停止命令
                if control_msg.stop_speaking:
                    print("收到停止语音命令")
                    self.tts_player.stop()
                    
                # 处理语音播放
                elif control_msg.text_to_speak and control_msg.text_to_speak.strip():
                    print(f"收到语音命令: {control_msg.text_to_speak[:20]}...")
                    
                    if self.tts_player.running:
                        self.tts_player.stop()
                        time.sleep(0.3)
                        
                    threading.Thread(
                        target=self.tts_player.play,
                        args=(control_msg.text_to_speak,),
                        daemon=True
                    ).start()

            except queue.Empty:
                continue
            except Exception as e:
                print(f"处理命令时出错: {e}")

    def stop(self):
        self.running = False
        self.handler_thread.join(timeout=1.0)

# ====== 主程序 ======
import signal

if __name__ == "__main__":
    exit_requested = threading.Event()

    def signal_handler(sig, frame):
        print("\n收到 Ctrl+C 信号，准备退出程序...")
        exit_requested.set()

    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        print(f"正在初始化DDS通信，网络接口: {DDS_NETWORK_INTERFACE}")
        ChannelFactoryInitialize(networkInterface=DDS_NETWORK_INTERFACE)

        # 创建语音控制订阅器
        speech_control_sub = ChannelSubscriber("SpeechControl", SpeechControl)
        speech_control_sub.Init()

        print("DDS初始化完成，准备接收语音控制命令")
    except Exception as e:
        print(f"DDS初始化失败: {e}")
        sys.exit(1)

    # 创建TTS播放器并设置默认音量
    tts_player = TTSPlayer(
        appid=APPID, 
        api_key=API_KEY, 
        api_secret=API_SECRET, 
        device_index=DOG_DEVICE_INDEX
    )
    
    # 设置初始音量
    tts_player.set_volume(30)  # 默认音量设为70%

    # 创建语音控制处理器
    speech_handler = SpeechControlHandler(tts_player)
    
    try:
        print("等待语音控制指令...(输入Ctrl+C退出)")
        while not exit_requested.is_set():
            try:
                control_msg = speech_control_sub.Read(1)
                if control_msg is not None:
                    speech_handler.add_command(control_msg)
            except Exception as e:
                if "take sample error" not in str(e) and "SampleState" not in str(e):
                    print(f"DDS读取失败: {e}")
                    
            time.sleep(0.01)

    except Exception as e:
        print(f"主程序发生错误: {e}")
    finally:
        print("正在关闭所有资源...")
        speech_handler.stop()
        tts_player.close()
        speech_control_sub.Close()
        print("程序已关闭")