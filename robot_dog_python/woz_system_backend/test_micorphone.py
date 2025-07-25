import sounddevice as sd
import soundfile as sf

def test_microphone(device_index=None, output_file="你倒是说句话啊6.wav", duration=5):
    # 获取设备列表并打印
    devices = sd.query_devices()
    print("可用设备：")
    for i, dev in enumerate(devices):
        print(f"{i}: {dev['name']}")
    
    # 选择设备或使用默认
    if device_index is None:
        device_index = int(input("输入设备序号："))
    fs = int(devices[device_index]['default_samplerate'])  # 设备支持采样率
    
    print("开始录音...")
    recording = sd.rec(int(duration * fs), samplerate=fs, channels=1, device=device_index)
    sd.wait()  # 等待录制完成
    sf.write(output_file, recording, fs)
    print(f"已保存：{output_file}，请用播放器检查声音")

test_microphone()