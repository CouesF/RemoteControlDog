import sounddevice as sd
import soundfile as sf  # 正确的写法

fs = 16000  # 你的麦克风支持的采样率
seconds = 10

sd.default.device = (0, None)  # hw:0,0

print("开始录音...")
recording = sd.rec(int(seconds * fs), samplerate=fs, channels=1, dtype='int16')
sd.wait()
print("录音完成，保存中...")

sf.write('dog_microphone.wav', recording, fs)  # ✅ 正确调用
print("保存成功：dog_microphone.wav")
