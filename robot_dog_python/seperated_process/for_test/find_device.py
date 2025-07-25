import pyaudio

# --- Settings to Test ---
DEVICE_INDEX = 24
RATES_TO_TEST = [48000, 44100, 32000, 22050, 16000, 8000]
CHANNELS = 1
FORMAT = pyaudio.paInt16
# ------------------------

audio = pyaudio.PyAudio()

print(f"🔍 Testing microphone at Index {DEVICE_INDEX}...")
print("---------------------------------------")

device_info = audio.get_device_info_by_index(DEVICE_INDEX)
print(f"Device Name: {device_info.get('name')}")

for rate in RATES_TO_TEST:
    try:
        is_supported = audio.is_format_supported(
            rate=rate,
            input_device=DEVICE_INDEX,
            input_channels=CHANNELS,
            input_format=FORMAT
        )
        if is_supported:
            print(f"✅ SUCCESS: {rate} Hz is supported.")
        else:
            print(f"❌ FAILED:  {rate} Hz is NOT supported.")
    except ValueError:
        print(f"❌ FAILED:  {rate} Hz is NOT supported (ValueError).")

print("---------------------------------------")

audio.terminate()