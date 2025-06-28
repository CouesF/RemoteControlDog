#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# @FileName: dds_stop_test.py
# @Description: DDS语音合成与停止功能测试
# @Author: OpenAI
# @Date: 2023-10-26

import os
import sys
import time
import threading
import asyncio
import unittest
from datetime import datetime

# ==== DDS相关导入 ====
from unitree_sdk2py.core.channel import ChannelPublisher, ChannelSubscriber, ChannelFactoryInitialize
current_script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_script_dir)
communication_dir_path = os.path.join(parent_dir, 'communication')
sys.path.append(communication_dir_path)
from dds_data_structure import SpeechControl

def test_tts():
    # 初始化DDS
    ChannelFactoryInitialize(networkInterface="enP8p1s0")
    
    # 创建发布器
    pub = ChannelPublisher("SpeechControl", SpeechControl)
    pub.Init()
    
    # 发送合成命令
    synth_cmd = SpeechControl()
    synth_cmd.text_to_speak = "这是一段测试语音，将在2秒后被停止"
    pub.Write(synth_cmd)
    print("✅ 已发送合成命令")
    
    # 等待5秒
    time.sleep(3.0)
    
    # 发送停止命令
    stop_cmd = SpeechControl()
    stop_cmd.stop_speaking = True
    pub.Write(stop_cmd)
    print("⏹️ 已发送停止命令")
    
    print("👂 请确认语音是否停止")

if __name__ == "__main__":
    test_tts()