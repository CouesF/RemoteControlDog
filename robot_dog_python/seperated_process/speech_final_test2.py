# test_tts_stop.py
import time
from speech import TTSPlayer

# 配置（保持和 speech.py 一致）
APPID = '5a5d1cf3'
API_KEY = '303dc3d3e0d3dca28c3708c77bdeecad'
API_SECRET = 'YWZlMjZmY2VlNDk1NmQ2MjNmZmZhNTNh'
DEVICE_INDEX = 0

if __name__ == "__main__":
    print("🔊 正在测试语音停止功能...")

    tts = TTSPlayer(
        appid=APPID,
        api_key=API_KEY,
        api_secret=API_SECRET,
        device_index=DEVICE_INDEX
    )

    long_text = (
        "这是一个测试语音中断功能的测试语句。"
        "它的长度略微长一些，用于确保在播放过程中"
        "我们可以通过程序控制语音停止。如果你现在听到了这些文字，"
        "说明语音播放正常。稍后它将被手动中断。"
    )

    tts.play(long_text)

    # 等待 5 秒，再停止播放
    time.sleep(5)

    print("⛔ 正在手动调用 tts.stop() 来中断语音播放...")
    tts.stop()

    print("✅ 语音停止测试完成")
