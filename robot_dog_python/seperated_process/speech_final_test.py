# test_tts.py

import time
from main_speech_synthesis import TTSPlayer

# ✅ 路径根据你的项目结构调整
# 配置参数（建议放入 speech.py 同步使用的配置）
APPID = '5a5d1cf3'
API_KEY = '303dc3d3e0d3dca28c3708c77bdeecad'
API_SECRET = 'YWZlMjZmY2VlNDk1NmQ2MjNmZmZhNTNh'
DEVICE_INDEX = 0  # 替换成你需要测试的音频设备索引

if __name__ == "__main__":
    print("🔊 正在测试语音合成功能...")
    
    tts = TTSPlayer(
        appid=APPID,
        api_key=API_KEY,
        api_secret=API_SECRET,
        device_index=0
    )
    
    test_text = "这是一次语音合成功能的测试。请确认是否可以听到声音,它的长度略微长一些，用于检查在播放过程中的麦克风。"
    
    # 启动播放
    tts.play(test_text)
    
    # 等待一段时间保证播放完成（因为是线程播放）
    time.sleep(8)

    # 停止播放并清理资源
    tts.stop()
    
    print("✅ 语音合成测试完成")
