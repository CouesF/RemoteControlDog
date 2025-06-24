import time
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
import numpy as np
import time
import queue
from dataclasses import dataclass

current_script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_script_dir)
communication_dir_path = os.path.join(parent_dir, 'communication')
sys.path.append(communication_dir_path)
from unitree_sdk2py.core.channel import ChannelPublisher, ChannelSubscriber, ChannelFactoryInitialize
from dds_data_structure import SpeechControl

DDS_INTERFACE = "enP8p1s0"  # 你的主程序中使用的接口必须一致！

def main():
    print("正在初始化 DDS 发布器...")
    ChannelFactoryInitialize(networkInterface=DDS_INTERFACE)

    # 创建 SpeechControl 的 Publisher
    publisher = ChannelPublisher("SpeechControl", SpeechControl)
    publisher.Init()

    # 构造并发送一条带有音量信息的语音控制消息
    msg = SpeechControl(
        text_to_speak="你好，我是机器狗。",
        stop_speaking=False,
        volume= 30 # 可调试为 30、60、100 等，看音量是否生效
    )

    print(f"发送语音指令：'{msg.text_to_speak}'，音量: {msg.volume}%")
    publisher.Write(msg)

    # 稍等几秒，让接收方播放完成
    time.sleep(3)

    print("测试完成，请确认是否成功播放且音量变化明显。")

if __name__ == "__main__":
    main()
