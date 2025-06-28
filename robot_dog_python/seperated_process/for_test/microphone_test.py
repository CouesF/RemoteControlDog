import sounddevice as sd
import soundfile as sf
import numpy as np

fs = 16000  # 采样率，请根据你的麦克风支持的频率设置
duration = 10  # 录音时长（秒）

# 确保选择正确的输入和输出设备。
# 可以使用 sd.query_devices() 来查看可用设备。
# sd.default.device = (input_device_index, output_device_index)
sd.default.device = None  # 使用默认设备

print("开始实时监听和录音...")

# 用于存储录音数据的列表
q = []

def callback(indata, frames, time, status):
    """This is called (from a separate thread) for each audio block."""
    if status:
        print(status)
    q.append(indata.copy())
    sd.play(indata, samplerate=fs, blocking=False) # 实时播放输入音频

try:
    with sd.InputStream(samplerate=fs, channels=1, dtype='int16', callback=callback) as sd_input_stream:
        print(f"正在录音并实时播放，时长 {duration} 秒...")
        sd.sleep(int(duration * 1000)) # 等待录音结束

except Exception as e:
    print(f"发生错误: {e}")

print("录音完成，正在保存...")

# 将列表中的音频数据连接起来
recording = np.concatenate(q, axis=0)

sf.write('dog_microphone_realtime.wav', recording, fs)
print("保存成功：dog_microphone_realtime.wav")