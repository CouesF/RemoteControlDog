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
import queue
import argparse
import signal

current_script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_script_dir)
communication_dir_path = os.path.join(parent_dir, 'communication')
sys.path.append(communication_dir_path)

from dds_data_structure import SpeechControl
from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelPublisher

# DDS 配置
DEFAULT_NETWORK_INTERFACE = "enP8p1s0"  # 默认网络接口
DEFAULT_TEST_TEXT = "语音合成服务。"  # 默认测试文本
DEFAULT_VOLUME = 40  # 默认音量百分比
DEFAULT_TEST_COUNT = 3  # 默认测试次数
DDS_SLEEP_INTERVAL = 0.1  # DDS消息发送间隔

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
        self.queue = queue.Queue()
        self.stop_requested = False
        self.playing_long_text = False  # 标记是否在播放长文本
        
    def _run(self):
        """后台线程发送消息"""
        print("消息发布线程启动")
        while self.active:
            if not self.running:
                time.sleep(0.1)
                continue
                
            try:
                if not self.queue.empty():
                    speech_control = self.queue.get()
                    
                    # 打印消息详情
                    if speech_control.stop_speaking:
                        print(f"发布消息: [停止指令]")
                    elif speech_control.text_to_speak:
                        text_length = len(speech_control.text_to_speak)
                        print(f"发布消息: 文本='{speech_control.text_to_speak[:20]}...' (长度:{text_length}), 音量={speech_control.volume}%")
                        # 标记是否为长文本
                        self.playing_long_text = text_length > 50
                    else:
                        print(f"发布消息: 音量={speech_control.volume}%")
                    
                    self.publisher.Write(speech_control)
                    
                time.sleep(DDS_SLEEP_INTERVAL)  # 短暂睡眠
                
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
        self.queue.put(speech_control)
        
    def send_stop_command(self):
        """发送停止语音命令"""
        speech_control = SpeechControl()
        speech_control.stop_speaking = True
        self.queue.put(speech_control)
        self.stop_requested = True
        print("🚨 已发送停止语音指令")
        
    def send_volume_command(self, volume):
        """设置音量"""
        speech_control = SpeechControl()
        speech_control.volume = volume
        self.queue.put(speech_control)
    
    def is_stop_requested(self):
        """检查是否已请求停止"""
        return self.stop_requested
    
    def is_playing_long_text(self):
        """检查是否正在播放长文本"""
        return self.playing_long_text

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
        time.sleep(1.0)  # 等待音量设置生效
        
        # 记录测试开始时间
        total_start_time = time.time()
        stop_test_results = []
        
        # 测试序列
        for i in range(test_count):
            if tester.is_stop_requested():
                print("测试已被停止请求中断")
                break
                
            print(f"\n=== 测试 #{i+1}/{test_count} ===")
            
            # 发送文本
            print(f"发送文本: '{test_text}'")
            tester.send_tts_command(test_text, volume)
            
            # 等待语音播放
            wait_time = max(3, len(test_text) / 5)  # 增加等待时间因子
            print(f"等待 {wait_time:.1f} 秒让语音播放...")
            time.sleep(wait_time)
            
            # 测试停止功能（每隔2次测试）
            if (i+1) % 2 == 0 and not tester.is_stop_requested():
                print("\n=== 测试停止功能 ===")
                
                # 发送长文本（300字）
                long_text = ("这是一段较长的测试文本，用于测试停止功能是否能够及时中断语音播放。" * 15).strip()
                print(f"发送长文本: 长度={len(long_text)} 字符")
                start_time = time.time()
                tester.send_tts_command(long_text, volume)
                
                # 等待较短时间后发送停止命令
                stop_wait_time = 1.0  # 等待1.0秒后发送停止
                time.sleep(stop_wait_time)
                print(f"发送停止命令，当前播放时长: {time.time()-start_time:.1f}秒")
                tester.send_stop_command()
                
                # 确保停止命令被处理
                print("等待停止命令被处理...")
                stop_handling_time = time.time()
                time.sleep(1.5)  # 等待停止处理
                
                # 检查是否中断了长文本
                if tester.is_playing_long_text():
                    print("❌ 停止功能未生效：系统仍在播放长文本")
                    test_result = "失败"
                else:
                    print("✅ 停止功能生效：长文本被正确中断")
                    test_result = "成功"
                
                # 记录测试结果
                stop_test_results.append({
                    "test_index": i+1,
                    "result": test_result,
                    "long_text_length": len(long_text),
                    "stop_time": time.time() - start_time,
                    "expected_full_time": len(long_text) / 5
                })
                
                # 检查停止效果 - 发送短文本确认系统响应
                print("检查停止效果 - 发送短文本确认系统响应")
                tester.send_tts_command("停止功能测试完成", volume)
                
                # 等待短文本播放
                time.sleep(2.0)
                
                # 重置停止标志
                tester.stop_requested = False
                print("停止标志已重置")
        
        # 最终测试（如果没有被停止）
        if not tester.is_stop_requested():
            print("\n=== 最终测试 ===")
            final_text = "所有测试已完成，感谢参与。"
            print(f"发送最终文本: '{final_text}'")
            tester.send_tts_command(final_text, volume)
            
            # 等待最终语音播放
            time.sleep(3.0)
        
        total_duration = time.time() - total_start_time
        
        # 打印停止功能测试结果摘要
        print("\n" + "="*60)
        print("停止功能测试结果摘要：")
        print("="*60)
        success_count = sum(1 for r in stop_test_results if r["result"] == "成功")
        failure_count = len(stop_test_results) - success_count
        
        for result in stop_test_results:
            status = "✅ 成功" if result["result"] == "成功" else "❌ 失败"
            print(f"测试 #{result['test_index']}: {status} | 长文本长度: {result['long_text_length']} | "
                  f"实际停止时间: {result['stop_time']:.1f}秒 | 预期完整时间: {result['expected_full_time']:.1f}秒")
        
        print("\n" + "="*60)
        print(f"停止功能测试总结：成功 {success_count}次，失败 {failure_count}次")
        print(f"总测试时长: {total_duration:.1f}秒")
        print("="*60)
        
        if failure_count > 0:
            print("\n‼️ 停止功能存在问题！请检查语音服务实现")
        else:
            print("\n✅ 停止功能正常工作！")
        
    except Exception as e:
        print(f"❌ 测试发生错误: {e}")
        traceback.print_exc()
    finally:
        tester.stop()
        print("✅ 测试已停止")

def run_interactive_test(network_interface):
    """交互式测试模式"""
    print("\n" + "="*60)
    print("DDS语音合成测试 - 交互模式")
    print("="*60)
    print("  输入命令:")
    print("    text [内容] - 发送文本")
    print("    volume [值] - 设置音量 (0-100)")
    print("    stop        - 发送停止指令")
    print("    quit        - 退出测试")
    print("="*60)
    
    tester = TTSTester(network_interface)
    tester.start()
    
    try:
        while True:
            command = input("\n> 请输入命令: ").strip().split()
            if not command:
                continue
                
            cmd_type = command[0].lower()
            
            if cmd_type == "text" and len(command) > 1:
                text = " ".join(command[1:])
                print(f"发送文本: '{text}' (长度: {len(text)})")
                tester.send_tts_command(text, DEFAULT_VOLUME)
                
            elif cmd_type == "volume" and len(command) > 1:
                try:
                    volume = int(command[1])
                    if 0 <= volume <= 100:
                        print(f"设置音量: {volume}%")
                        tester.send_volume_command(volume)
                    else:
                        print("❌ 音量值必须在0-100之间")
                except ValueError:
                    print("❌ 无效的音量值")
                    
            elif cmd_type == "stop":
                print("发送停止指令")
                tester.send_stop_command()
                print("等待停止命令被处理...")
                time.sleep(1.0)  # 增加等待时间
                
            elif cmd_type == "quit":
                print("退出测试")
                break
                
            else:
                print("❌ 未知命令")
                
    except KeyboardInterrupt:
        print("\n测试被用户中断")
    except Exception as e:
        print(f"❌ 测试发生错误: {e}")
        traceback.print_exc()
    finally:
        tester.stop()
        print("✅ 测试已停止")

def signal_handler(sig, frame):
    """处理Ctrl+C信号"""
    print("\n收到Ctrl+C信号，准备退出...")
    sys.exit(0)

if __name__ == "__main__":
    # 注册Ctrl+C信号处理
    signal.signal(signal.SIGINT, signal_handler)
    
    parser = argparse.ArgumentParser(description='DDS TTS 自动化测试工具')
    parser.add_argument('--text', default=DEFAULT_TEST_TEXT,
                        help=f'要测试的文本内容（默认: "{DEFAULT_TEST_TEXT}"）')
    parser.add_argument('--volume', type=int, default=DEFAULT_VOLUME,
                        help=f'音量百分比 (0-100，默认: {DEFAULT_VOLUME})')
    parser.add_argument('--count', type=int, default=DEFAULT_TEST_COUNT,
                        help=f'测试次数 (默认: {DEFAULT_TEST_COUNT})')
    parser.add_argument('--interface', default=DEFAULT_NETWORK_INTERFACE,
                        help=f'DDS网络接口（默认: {DEFAULT_NETWORK_INTERFACE}）')
    parser.add_argument('--interactive', action='store_true',
                        help='进入交互式测试模式')
    parser.add_argument('--verbose', action='store_true',
                        help='详细输出模式')
    args = parser.parse_args()
    
    # 验证参数
    if args.volume < 0 or args.volume > 100:
        print(f"错误: 音量必须在0-100之间，当前值: {args.volume}")
        sys.exit(1)
        
    if args.count < 1 and not args.interactive:
        print(f"错误: 测试次数必须大于0，当前值: {args.count}")
        sys.exit(1)
    
    try:
        if args.interactive:
            run_interactive_test(args.interface)
        else:
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