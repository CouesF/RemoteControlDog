#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# @Time    : 2025/5/1
# @Author  : TTS Tester
# @FileName: test_tts.py
# @Software: PyCharm

import sys
import time
import threading
import traceback
import os
current_script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_script_dir)
communication_dir_path = os.path.join(parent_dir, 'communication')
sys.path.append(communication_dir_path)
# --- END OF FIX ---

from dds_data_structure import SpeechControl
from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelPublisher
import argparse

# DDS 配置
DEFAULT_NETWORK_INTERFACE = "enP8p1s0"  # 默认网络接口
DEFAULT_TEST_TEXT = "语音合成服务。"  # 默认测试文本
DEFAULT_VOLUME = 25  # 默认音量百分比
DEFAULT_TEST_COUNT = 3  # 默认测试次数

class TTSTester:
    def __init__(self, network_interface):
        print(f"初始化DDS通信，网络接口: {network_interface}")
        try:
            ChannelFactoryInitialize(networkInterface=network_interface)
            self.publisher = ChannelPublisher("SpeechControl", SpeechControl)
            self.publisher.Init()
            print("✅ DDS发布者初始化成功")
        except Exception as e:
            print(f"❌ DDS初始化失败: {e}")
            traceback.print_exc()
            raise
            
        self.active = True
        self.running = False
        self.thread = threading.Thread(target=self._run)
        self.thread.daemon = True
        self.queue = []
        
    def _run(self):
        """后台线程发送消息"""
        print("消息发布线程启动")
        while self.active:
            if not self.running:
                time.sleep(0.1)
                continue
                
            try:
                if self.queue:
                    speech_control = self.queue.pop(0)
                    print(f"发布消息: {speech_control.text_to_speak}")
                    self.publisher.Write(speech_control)
                    
                time.sleep(0.1)  # 短暂睡眠
                
            except Exception as e:
                print(f"发布线程错误: {e}")
                traceback.print_exc()
                
        print("消息发布线程退出")
        
    def start(self):
        """启动测试"""
        if not self.running:
            self.running = True
            self.thread.start()
            print("测试已启动")
            
    def stop(self):
        """停止测试"""
        self.active = False
        self.running = False
        if self.thread.is_alive():
            self.thread.join(timeout=1.0)
        self.publisher.Close()
        print("测试已停止")
        
    def send_tts_command(self, text, volume):
        """发送语音合成指令"""
        speech_control = SpeechControl()
        speech_control.text_to_speak = text
        speech_control.volume = volume
        self.queue.append(speech_control)
        
    def send_stop_command(self):
        """发送停止语音命令"""
        speech_control = SpeechControl()
        speech_control.stop_speaking = True
        self.queue.append(speech_control)
        
    def send_volume_command(self, volume):
        """设置音量"""
        speech_control = SpeechControl()
        speech_control.volume = volume
        self.queue.append(speech_control)

def run_automated_test(test_text, volume, test_count, network_interface):
    """自动化测试模式"""
    print("\n" + "="*60)
    print("DDS语音合成测试 - 自动化模式")
    print("="*60)
    print(f"  测试文本: {test_text}")
    print(f"  音量设置: {volume}%")
    print(f"  测试次数: {test_count}")
    print(f"  网络接口: {network_interface}")
    print("="*60)
    
    tester = TTSTester(network_interface)
    tester.start()
    
    try:
        # 初始音量设置
        print(f"设置初始音量: {volume}%")
        tester.send_volume_command(volume)
        time.sleep(0.5)  # 等待音量设置生效
        
        # 测试序列
        for i in range(test_count):
            print(f"\n=== 测试 #{i+1}/{test_count} ===")
            
            # 发送文本
            print(f"发送文本: '{test_text}'")
            tester.send_tts_command(test_text, volume)
            
            # 等待语音播放
            wait_time = max(3, len(test_text) / 10)  # 根据文本长度计算等待时间
            print(f"等待 {wait_time:.1f} 秒让语音播放...")
            time.sleep(wait_time)
            
            # 测试停止功能（每隔2次测试）
            if (i+1) % 2 == 0:
                print("测试停止功能...")
                tester.send_tts_command("这将被中断的语音", volume)
                time.sleep(0.5)  # 稍微播放一会儿
                tester.send_stop_command()
                print("已发送停止命令")
                time.sleep(1)  # 等待停止生效
        
        # 最终测试
        print("\n=== 最终测试 ===")
        final_text = "所有测试已完成，感谢参与。"
        print(f"发送最终文本: '{final_text}'")
        tester.send_tts_command(final_text, volume)
        time.sleep(3)  # 等待最终语音播放
        
        print("\n✅ 自动化测试完成")
        
    except Exception as e:
        print(f"❌ 测试发生错误: {e}")
        traceback.print_exc()
    finally:
        tester.stop()
        print("✅ 测试已停止")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='DDS TTS 自动化测试工具')
    parser.add_argument('--text', default=DEFAULT_TEST_TEXT,
                        help=f'要测试的文本内容（默认: "{DEFAULT_TEST_TEXT}"）')
    parser.add_argument('--volume', type=int, default=DEFAULT_VOLUME,
                        help=f'音量百分比 (0-100，默认: {DEFAULT_VOLUME})')
    parser.add_argument('--count', type=int, default=DEFAULT_TEST_COUNT,
                        help=f'测试次数 (默认: {DEFAULT_TEST_COUNT})')
    parser.add_argument('--interface', default=DEFAULT_NETWORK_INTERFACE,
                        help=f'DDS网络接口（默认: {DEFAULT_NETWORK_INTERFACE}）')
    args = parser.parse_args()
    
    # 验证参数
    if args.volume < 0 or args.volume > 100:
        print(f"错误: 音量必须在0-100之间，当前值: {args.volume}")
        sys.exit(1)
        
    if args.count < 1:
        print(f"错误: 测试次数必须大于0，当前值: {args.count}")
        sys.exit(1)
    
    try:
        run_automated_test(
            test_text=args.text,
            volume=args.volume,
            test_count=args.count,
            network_interface=args.interface
        )
    except KeyboardInterrupt:
        print("\n测试被用户中断")
    except Exception as e:
        print(f"测试发生错误: {e}")
        traceback.print_exc()
    finally:
        print("✅ 测试结束")