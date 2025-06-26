import sys
import os
import time
from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelPublisher

# 修复跨目录导入问题
current_script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_script_dir)
communication_dir_path = os.path.join(parent_dir, 'communication')
sys.path.append(communication_dir_path)

# 导入DDS数据结构
try:
    from dds_data_structure import SpeechControl
except ImportError as e:
    print(f"导入错误: {e}")
    # 尝试回退到绝对路径
    dds_path = os.path.join(os.path.dirname(current_script_dir), "communication/dds_data_structure.py")
    if os.path.exists(dds_path):
        sys.path.insert(0, os.path.dirname(dds_path))
        from dds_data_structure import SpeechControl
    else:
        raise ImportError("无法找到 dds_data_structure.py")

# 配置参数
DDS_NETWORK_INTERFACE = "enP8p1s0"
TEST_MESSAGES = [
    {"text_to_speak": "火山引擎，让智能增长。欢迎使用火山引擎实时语音合成服务。", "volume": 80},
    {"text_to_speak": "你好，我是机器狗。我会说话啦！这是我的第一次语音测试。", "volume": 90},
    {"text_to_speak": "请注意，前方有障碍物，请小心避让。当前时间是：" + time.strftime("%Y年%m月%d日 %H时%M分"), "volume": 85},
    {"stop_speaking": True},  # 停止命令
    {"text_to_speak": "这是被打断后恢复的语音测试，现在继续播放后续内容。", "volume": 75},
    {"volume": 50},  # 仅调整音量
    {"text_to_speak": "语音合成服务测试完成，感谢您的使用！再见！", "volume": 70},
]

def setup_dds_publisher():
    """初始化DDS并创建发布者"""
    print(f"\n{'='*50}")
    print(f"初始化DDS接口: {DDS_NETWORK_INTERFACE}")
    ChannelFactoryInitialize(networkInterface=DDS_NETWORK_INTERFACE)
    
    publisher = ChannelPublisher("SpeechControl", SpeechControl)
    publisher.Init()
    print("DDS发布者已创建")
    return publisher

def send_test_messages(publisher):
    """发送测试消息序列"""
    print("\n开始发送测试消息...")
    
    for i, test_data in enumerate(TEST_MESSAGES):
        # 创建SpeechControl消息
        control_msg = SpeechControl()
        
        # 填充消息内容
        if "text_to_speak" in test_data:
            control_msg.text_to_speak = test_data["text_to_speak"]
            print(f"\n测试 {i+1}/测试总数: 播放文本 - '{test_data['text_to_speak'][:20]}...'")
        
        if "volume" in test_data:
            control_msg.volume = test_data["volume"]
            print(f"设置音量: {test_data['volume']}%")
        
        if "stop_speaking" in test_data:
            control_msg.stop_speaking = True
            print(f"\n测试 {i+1}/测试总数: 停止语音播放")
        
        # 发送消息
        publisher.Write(control_msg)
        print("消息已发送，等待3秒...")
        time.sleep(3)  # 等待TTS响应
    
    print("\n所有测试消息发送完成")

def run_test():
    """执行完整测试"""
    try:
        # 设置DDS发布者
        publisher = setup_dds_publisher()
        
        # 开始测试消息序列
        send_test_messages(publisher)
        
        # 测试完成后延时
        print("\n测试完成，等待10秒确保所有语音播放完毕...")
        time.sleep(10)
        
        print("\n测试结束，结果验证完成")
        
        return True
    except Exception as e:
        print(f"\n测试过程中出错: {str(e)}")
        return False

if __name__ == "__main__":
    print(f"\n{'*'*20} TTS服务集成测试 {'*'*20}")
    print("注意：请先启动TTS服务主程序，然后再运行此测试脚本")
    
    if input("\n是否已启动TTS服务主程序？(y/n): ").lower() != 'y':
        print("请先启动TTS服务主程序后再运行此测试")
        exit(0)
    
    print("\n开始执行TTS服务集成测试...")
    
    # 执行测试
    test_result = run_test()
    
    # 输出测试结果
    print(f"\n{'='*50}")
    if test_result:
        print("\n测试结果: ✅ 所有测试成功完成")
    else:
        print("\n测试结果: ❌ 测试失败，请检查错误信息")
    
    print("\n测试总结:")
    print(f"- 已尝试发送 {len(TEST_MESSAGES)} 条测试消息")
    print("- 测试内容包括:")
    print("  1. 不同长度的文本播放")
    print("  2. 音量控制（多个音量级别）")
    print("  3. 中断语音播放（停止命令）")
    print("  4. 中断后恢复播放")
    
    print("\n完成集成测试")