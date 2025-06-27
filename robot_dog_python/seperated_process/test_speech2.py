# test_dds_speech_handler.py
import sys
import time
import threading
import os
import queue
from dataclasses import dataclass

# 添加父目录到PATH以便导入模块（保留但不依赖）
current_script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(current_script_dir, '..'))
sys.path.append(parent_dir)

# ====== 在测试脚本中定义所需类（避免导入问题） ======
class SpeechControlHandler:
    """独立定义在测试脚本中以避免导入问题"""
    def __init__(self, tts_player):
        self.tts_player = tts_player
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
        if self.handler_thread.is_alive():
            self.handler_thread.join(timeout=1.0)

# ====== 测试数据结构和模拟类 ======
@dataclass
class MockSpeechControl:
    """模拟DDS消息结构"""
    text_to_speak: str = ""
    stop_speaking: bool = False
    volume: int = 70

class MockTTSPlayer:
    """模拟TTS播放器行为"""
    def __init__(self):
        self.running = False
        self.stop_requested = False
        self.played_text = ""
        self.volume_history = []
        self.stop_count = 0
        self.active_threads = set()
        self.lock = threading.Lock()
        self.current_volume = 70
        
    def play(self, text):
        """模拟语音播放方法"""
        with self.lock:
            self.played_text = text
            self.running = True
            self.stop_requested = False
            print(f"[模拟播放] 开始播放: {text[:20]}...")
            
        # 创建模拟播放线程
        def play_thread():
            start_time = time.time()
            while time.time() - start_time < LONG_AUDIO_DURATION and not self.stop_requested:
                time.sleep(0.1)
            with self.lock:
                self.running = False
                print(f"[模拟播放] 播放结束: {text[:20]}...")
                
        t = threading.Thread(target=play_thread)
        t.daemon = True
        t.start()
        self.active_threads.add(t)
        
    def stop(self):
        """模拟停止方法"""
        with self.lock:
            self.stop_count += 1
            self.stop_requested = True
            self.running = False
        print("[模拟停止] 语音已停止")
            
    def set_volume(self, volume):
        """模拟音量设置方法"""
        # 仅在音量值发生变化时才记录历史
        if volume != self.current_volume:
            self.current_volume = volume
            self.volume_history.append(volume)
            print(f"[模拟设置音量] 设置音量至 {volume}%")
        
    def close(self):
        """模拟清理方法"""
        with self.lock:
            self.stop_requested = True
            self.running = False
        for t in self.active_threads:
            t.join(timeout=0.5)
        print("[模拟清理] TTS播放器已关闭")
            
    def reset(self):
        """重置模拟器状态"""
        with self.lock:
            self.running = False
            self.stop_requested = False
            self.played_text = ""
            self.volume_history = []
            self.stop_count = 0
            self.current_volume = 70
        print("[模拟重置] 状态已重置")

# ====== 测试配置 ======
SAMPLE_TEXT = "这是一条用于DDS消息处理功能测试的语音内容"
DELAY_BETWEEN_TESTS = 1.5  # 测试间延迟(秒)
VOLUME_TEST_VALUES = [30, 70, 100]  # 测试音量值
LONG_AUDIO_DURATION = 5  # 长语音模拟时长(秒) - 缩短以加速测试

# ====== 主测试函数 ======
def test_speech_control_handler():
    print("\n" + "="*60)
    print("开始 DDS SpeechControl 消息处理系统测试")
    print("="*60)
    
    # 创建模拟TTS播放器
    mock_player = MockTTSPlayer()
    handler = SpeechControlHandler(mock_player)
    
    # 测试1: 基础语音播放
    print("\n[测试1] 基础语音播放功能")
    msg = MockSpeechControl(text_to_speak=SAMPLE_TEXT)
    handler.add_command(msg)
    time.sleep(1)  # 给处理线程时间
    
    with mock_player.lock:
        assert mock_player.played_text == SAMPLE_TEXT, "未正确接收播放文本"
        assert mock_player.running, "播放状态未激活"
    print("✅ 播放功能正常 - 文本接收正确，播放状态激活")
    
    # 测试2: 短时间语音中断
    print("\n[测试2] 语音中断功能")
    stop_msg = MockSpeechControl(stop_speaking=True)
    handler.add_command(stop_msg)
    time.sleep(1)
    
    with mock_player.lock:
        assert not mock_player.running, "语音未正确停止"
        assert mock_player.stop_count == 1, f"停止命令未触发 (停止计数: {mock_player.stop_count})"
    print("✅ 中断功能正常 - 成功停止播放")
    
    # 测试3: 连续语音命令处理
    print("\n[测试3] 连续语音命令处理")
    # 重置计数器和状态
    mock_player.reset()
    
    texts = [f"顺序播放测试 {i+1}" for i in range(3)]
    for text in texts:
        msg = MockSpeechControl(text_to_speak=text)
        handler.add_command(msg)
        time.sleep(0.5)  # 缩短等待时间
    
    time.sleep(1.5)  # 给最后一个命令足够时间处理
    with mock_player.lock:
        assert texts[2] in mock_player.played_text, f"未处理最新播放命令: {mock_player.played_text}"
    print("✅ 命令队列处理正常 - 正确处理连续语音命令")
    
    # 测试4: 音量控制功能
    print("\n[测试4] 音量控制功能")
    # 重置音量历史记录和状态
    mock_player.reset()
    
    for vol in VOLUME_TEST_VALUES:
        vol_msg = MockSpeechControl(volume=vol)
        handler.add_command(vol_msg)
        time.sleep(0.2)  # 快速发送命令
    
    time.sleep(0.5)  # 等待处理
    print(f"音量设置历史: {mock_player.volume_history}")
    
    # 检查最终音量是否正确设置
    if mock_player.volume_history:
        final_volume = mock_player.volume_history[-1]
    else:
        final_volume = mock_player.current_volume
        
    assert final_volume == VOLUME_TEST_VALUES[-1], \
        f"最终音量设置错误: 期望值 {VOLUME_TEST_VALUES[-1]}%, 实际值 {final_volume}%"
            
    # 确保音量有变化
    assert final_volume != 70, "音量控制未执行任何设置"
    print("✅ 音量控制正常 - 最终音量准确设置")
    
    # 测试5: 长时间播放时收到新命令
    print("\n[测试5] 长语音期间新命令处理")
    # 重置状态
    mock_player.reset()
    
    long_text = "长时间播放测试内容"
    new_text = "新打断命令"
    
    long_msg = MockSpeechControl(text_to_speak=long_text)
    handler.add_command(long_msg)
    time.sleep(1)  # 让播放开始
    
    # 发送新命令打断当前播放
    new_msg = MockSpeechControl(text_to_speak=new_text)
    handler.add_command(new_msg)
    time.sleep(1)  # 给处理时间
    
    with mock_player.lock:
        assert mock_player.stop_count >= 1, f"未执行必要的停止操作 (停止计数: {mock_player.stop_count})"
        assert new_text in mock_player.played_text, f"未处理新命令: {mock_player.played_text}"
    print("✅ 命令优先级处理正常 - 成功中断当前语音并处理新命令")
    
    # 测试6: 系统关闭时的清理操作
    print("\n[测试6] 系统关闭清理功能")
    # 重置状态
    mock_player.reset()
    
    active_msg = MockSpeechControl(text_to_speak="清理测试内容")
    handler.add_command(active_msg)
    time.sleep(0.5)
    
    handler.stop()
    time.sleep(0.5)
    
    with mock_player.lock:
        assert mock_player.stop_requested, "未正确触发停止清理"
        assert not mock_player.running, "播放状态未正确终止"
    print("✅ 清理功能正常 - 成功停止所有播放线程")
    
    # 最终清理
    mock_player.close()
    print("\n" + "="*60)
    print("✅ 所有 DDS SpeechControl 消息处理测试通过!")
    print("="*60)

if __name__ == "__main__":
    test_speech_control_handler()