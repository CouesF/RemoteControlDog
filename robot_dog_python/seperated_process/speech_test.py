#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# @FileName: dds_volume_test_fixed.py
# @Description: 最终修复音量控制问题的测试脚本
# @Author: OpenAI
# @Date: 2023-10-27

import os
import sys
import time
from unitree_sdk2py.core.channel import ChannelPublisher, ChannelFactoryInitialize

# ==== DDS相关导入 ====
current_script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_script_dir)
communication_dir_path = os.path.join(parent_dir, 'communication')
sys.path.append(communication_dir_path)
from dds_data_structure import SpeechControl

def test_tts():
    # 初始化DDS
    ChannelFactoryInitialize(networkInterface="enP8p1s0")
    pub = ChannelPublisher("SpeechControl", SpeechControl)
    pub.Init()
    
    # 1. 发送音量设置命令
    vol_cmd = SpeechControl()
    vol_cmd.volume = 100  # 70%音量
    pub.Write(vol_cmd)
    print("🔊 已发送音量设置命令 (70%)")
    
    # 等待足够时间让音量设置生效
    print("🕒 等待1秒让音量设置生效...")
    time.sleep(1.0)
    
    # 2. 发送合成命令 (使用独立消息，不包含音量属性)
    synth_cmd = SpeechControl()
    synth_cmd.text_to_speak = "我是一只机器狗，我可以说话，动来动去，并且做出可爱的表情！"
    synth_cmd.volume = vol_cmd.volume
    # 注意: 不设置volume属性
    pub.Write(synth_cmd)
    print("✅ 已发送合成命令")
    
    # 3. 等待后发送停止命令
    time.sleep(10.0)
    stop_cmd = SpeechControl()
    stop_cmd.stop_speaking = True
    pub.Write(stop_cmd)
    print("⏹️ 已发送停止命令")

if __name__ == "__main__":
    test_tts()