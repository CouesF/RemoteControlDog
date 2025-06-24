import pyaudio
import wave
import numpy as np
import os

#可以发biiiiiiiiii的声音

# ====== 核心参数配置 ======
SAMPLE_RATE = 48000
DURATION = 3  # 3秒音频
BASE_FREQ = 2000  # 人耳敏感频段
VOLUME_BOOST = 1.2  # 音量提升至120%（安全阈值内）

# ====== 无依赖音频生成函数 ======
def generate_enhanced_audio(filename, channels=1):
    # 生成时间序列
    t = np.linspace(0, DURATION, int(SAMPLE_RATE * DURATION), endpoint=False)
    
    # 生成主频率（2000Hz）并添加高次谐波增强穿透力
    main_wave = np.sin(2 * np.pi * BASE_FREQ * t)
    
    # 添加高音增强（8kHz泛音）
    high_harmonic = 0.3 * np.sin(2 * np.pi * 8000 * t)
    
    # 合成波形并限幅防爆音
    audio = VOLUME_BOOST * (main_wave + high_harmonic)
    audio = np.clip(audio, -0.95, 0.95)  # 保留动态范围
    
    # 应用淡入淡出
    fade_samples = int(SAMPLE_RATE * 0.1)
    audio[:fade_samples] *= np.linspace(0, 1, fade_samples)
    audio[-fade_samples:] *= np.linspace(1, 0, fade_samples)
    
    # 转换格式
    audio_pcm = (audio * 32767).astype(np.int16)
    
    # 写入文件
    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio_pcm.tobytes())

# ====== 设备自适应播放函数 ======
def enhanced_playback(filename):
    try:
        # 获取默认音频设备索引
        p = pyaudio.PyAudio()
        default_device = p.get_default_output_device_info()
        
        # 直接选择设备 0 (Yundea A31-1: USB Audio)
        dog_device = 0  # 手动选择设备 0
        
        # 输出当前选择的设备信息
        print(f"▶ 强效音频输出到: {p.get_device_info_by_index(dog_device)['name']}")

        with wave.open(filename, 'rb') as wf:
            stream = p.open(
                format=p.get_format_from_width(wf.getsampwidth()),
                channels=wf.getnchannels(),
                rate=wf.getframerate(),
                output=True,
                output_device_index=dog_device,  # 使用手动选择的设备 0
                frames_per_buffer=4096
            )
            
            # 播放音频
            chunk_size = 4096
            data = wf.readframes(chunk_size)
            while data:
                stream.write(data)
                data = wf.readframes(chunk_size)
                
            stream.stop_stream()
            stream.close()
            
        p.terminate()
        print("✅ 增强版音频播放成功")
    except Exception as e:
        print(f"❌ 播放失败: {str(e)}")

# ====== 执行测试 ======
if __name__ == "__main__":
    # 生成增强音频并测试
    generate_enhanced_audio("dog_boosted.wav", channels=1)
    enhanced_playback("dog_boosted.wav")