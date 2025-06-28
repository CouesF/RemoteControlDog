# -*- coding: utf-8 -*-
# @FileName: dds_stop_test.py
# @Time: 2025/6/27
# @Author: Stop Test

import sys
import os
import time
import signal
import random

# ==== DDS 相关导入 ====
# 添加父目录到系统路径，以便导入通信模块
current_script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_script_dir)
sys.path.append(parent_dir)

from communication.dds_data_structure import SpeechControl
from unitree_sdk2py.core.channel import ChannelPublisher, ChannelFactoryInitialize

# ==== DDS 通信配置 ====
DDS_NETWORK_INTERFACE = "enP8p1s0"  # 根据实际网络接口修改
DDS_TOPIC_NAME = "SpeechControl"
DDS_PUBLISH_INTERVAL = 3.0  # 命令发布间隔（秒）

# 退出标志
exit_requested = False

def signal_handler(sig, frame):
    """处理 Ctrl+C 信号"""
    global exit_requested
    print("\n收到 Ctrl+C 信号，准备退出测试...")
    exit_requested = True

def send_stop_command(publisher, volume=70):
    """发送停止播放命令"""
    control_msg = SpeechControl()
    control_msg.stop_speaking = True
    control_msg.text_to_speak = ""
    control_msg.volume = volume
    
    publisher.Write(control_msg)
    print(f"✋ 发送停止指令 | 停止标志=True | 音量={volume}%")

def send_text_command(publisher, text="基础测试文本", volume=70):
    """发送文本播放命令"""
    control_msg = SpeechControl()
    control_msg.stop_speaking = False
    control_msg.text_to_speak = text
    control_msg.volume = volume
    
    publisher.Write(control_msg)
    print(f"📢 发送文本指令 | 文本='{text[:30]}...' | 停止标志=False | 音量={volume}%")

def run_stop_test():
    """主测试循环：专注于停止功能"""
    global exit_requested
    
    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("=== DDS 停止功能专项测试 ===")
    print("按 Ctrl+C 退出测试")
    print("正在初始化 DDS 通信...")
    
    try:
        # 初始化 DDS
        ChannelFactoryInitialize(networkInterface=DDS_NETWORK_INTERFACE)
        
        # 创建 DDS 发布者
        publisher = ChannelPublisher(DDS_TOPIC_NAME, SpeechControl)
        publisher.Init()
        print(f"✅ DDS 发布者初始化成功，主题: {DDS_TOPIC_NAME}")
        
        # 场景1：发送长时间播放请求后立即停止
        print("\n===== 场景1：长文本立即停止 =====")
        long_text = "这是一段用于测试停止功能的长文本，设计持续时间为10秒。语音合成系统应该在接收到停止命令后立即中断当前播放。" * 3
        send_text_command(publisher, long_text)
        print("...立即发送停止命令")
        send_stop_command(publisher)
        time.sleep(DDS_PUBLISH_INTERVAL)
        
        # 场景2：多次快速发送停止命令
        print("\n===== 场景2：连续多次停止命令 =====")
        print("发送短文本后连续发送5次停止命令")
        send_text_command(publisher, "测试文本，应只能听到这句话的开头部分")
        for i in range(5):
            print(f"停止命令 #{i+1}")
            send_stop_command(publisher)
            time.sleep(0.3)  # 非常短的间隔，模拟快速连按
        
        time.sleep(DDS_PUBLISH_INTERVAL)
        
        # 场景3：在停止后立即发送新请求
        print("\n===== 场景3：停止后立即发新请求 =====")
        send_text_command(publisher, "这是停止前的文本")
        print("...发送停止命令")
        send_stop_command(publisher)
        print("...立即发送新文本请求")
        send_text_command(publisher, "这是停止后的文本")
        time.sleep(DDS_PUBLISH_INTERVAL)
        
        # 场景4：在播放过程中停止
        print("\n===== 场景4：中途停止播放 =====")
        send_text_command(publisher, "这是测试中途停止功能的文本，您应该无法听到这句话的结尾部分")
        print("等待2秒后发送停止命令")
        time.sleep(2.0)
        send_stop_command(publisher)
        time.sleep(DDS_PUBLISH_INTERVAL)
        
        # 场景5：仅停止命令无播放状态
        print("\n===== 场景5：无播放状态时发送停止命令 =====")
        print("无任何文本播放时发送停止命令")
        send_stop_command(publisher)
        time.sleep(DDS_PUBLISH_INTERVAL)
        
        # 场景6：停止命令附带音量修改
        print("\n===== 场景6：停止命令修改音量 =====")
        send_text_command(publisher, "测试停止命令能否修改系统音量，文本长度10秒" * 2, volume=30)
        print("...立即发送停止命令并将音量改为80%")
        send_stop_command(publisher, volume=80)
        time.sleep(DDS_PUBLISH_INTERVAL)
        
        # 场景7：验证停止后音量是否改变
        print("\n===== 场景7：验证停止后音量改变 =====")
        print("发送测试文本，检查音量是否在停止命令中修改为80%")
        send_text_command(publisher, "如果听到这句话时音量为80%，说明停止命令中的音量设置生效了")
        time.sleep(DDS_PUBLISH_INTERVAL)
        
        print("\n✅✅✅ 所有停止功能测试完成 ✅✅✅")
    
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {e}")
    finally:
        # 清理资源
        if 'publisher' in locals():
            publisher.Close()
        print("✅ DDS 资源已清理")
        print("=== 测试脚本结束 ===")

if __name__ == "__main__":
    run_stop_test()