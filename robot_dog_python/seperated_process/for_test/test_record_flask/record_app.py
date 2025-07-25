import pyaudio
import time
import wave
import io
import json
import queue
from flask import Flask, Response, render_template, jsonify

# --- Audio Settings ---
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 1024

# --- Flask App & Stats Queue ---
app = Flask(__name__)
stats_queue = queue.Queue() # Thread-safe queue for stats

# --- State Control ---
streaming_active = False

def generate_wav_header(sample_rate, channels, sample_width):
    with io.BytesIO() as f:
        with wave.open(f, 'wb') as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(sample_width)
            wf.setframerate(sample_rate)
            wf.writeframes(b'')
        return f.getvalue()

def generate_stats():
    """A generator that yields server stats in SSE format."""
    while True:
        try:
            stats = stats_queue.get(timeout=1)
            # SSE format is "data: {json_string}\n\n"
            yield f"data: {json.dumps(stats)}\n\n"
        except queue.Empty:
            # Send a keep-alive comment to prevent the connection from closing
            yield ": keep-alive\n\n"

def generate_audio_stream():
    """Initializes PyAudio and streams microphone data."""
    audio = pyaudio.PyAudio()
    sample_width = audio.get_sample_size(FORMAT)
    header = generate_wav_header(RATE, CHANNELS, sample_width)
    yield header

    stream = None
    try:
        stream = audio.open(format=FORMAT, channels=CHANNELS, rate=RATE,
                            input=True, frames_per_buffer=CHUNK, input_device_index=0)
        print("✅ Microphone stream opened successfully.")

        while streaming_active: # Check the flag more directly
            try:
                # Measure capture time
                start_time = time.monotonic()
                data = stream.read(CHUNK, exception_on_overflow=False)
                end_time = time.monotonic()

                # Calculate stats and put them in the queue
                capture_duration_ms = (end_time - start_time) * 1000
                server_timestamp_ms = time.time() * 1000
                stats_queue.put({
                    "capture_ms": round(capture_duration_ms, 2),
                    "server_timestamp": server_timestamp_ms,
                    "chunk_size_bytes": len(data)
                })
                yield data
            except IOError as e:
                print(f"🎤 Stream read error: {e}")
                break
        
    except Exception as e:
        print(f"❌ FAILED to open stream: {e}")
    finally:
        if stream:
            stream.stop_stream()
            stream.close()
            print("⏹️ Microphone stream closed.")
        audio.terminate()
        print("🎤 PyAudio instance terminated.")


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/stats')
def stats_feed():
    """Route to stream server stats."""
    return Response(generate_stats(), mimetype='text/event-stream')

@app.route('/audio')
def audio_feed():
    return Response(generate_audio_stream(), mimetype='audio/wav')

@app.route('/start', methods=['POST'])
def start_streaming():
    global streaming_active
    streaming_active = True
    print("▶️ Streaming toggled to ON")
    return jsonify(success=True)

@app.route('/stop', methods=['POST'])
def stop_streaming():
    global streaming_active
    streaming_active = False
    print("⏹️ Streaming toggled to OFF")
    return jsonify(success=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, threaded=True)