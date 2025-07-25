import sounddevice as sd
import soundfile as sf
import websocket
import json
import time

# --- Configuration ---
FS = 16000  # Your microphone's sample rate
CHANNELS = 1
DTYPE = 'int16'
# Replace with your web server's WebSocket address
WEBSOCKET_SERVER_URL = "ws://your_web_server_ip:5000/ws"

# Global variables for recording state
recording_active = False
current_stream = None

def callback(indata, frames, time, status):
    """This is called (potentially) by a separate thread for each audio block."""
    if status:
        print(status)
    if recording_active and ws_connection and ws_connection.connected:
        # Convert indata to bytes and send over WebSocket
        # You might need to adjust this depending on how you want to send
        # Raw bytes are simplest for quick prototyping.
        ws_connection.send(indata.tobytes(), websocket.ABNF.OPCODE_BINARY)

def on_message(ws, message):
    global recording_active, current_stream
    print(f"Received message: {message}")
    try:
        data = json.loads(message)
        if data.get("command") == "start_record":
            if not recording_active:
                print("Starting recording...")
                current_stream = sd.InputStream(samplerate=FS, channels=CHANNELS, dtype=DTYPE, callback=callback)
                current_stream.start()
                recording_active = True
                ws.send(json.dumps({"status": "recording_started"}))
            else:
                ws.send(json.dumps({"status": "already_recording"}))
        elif data.get("command") == "stop_record":
            if recording_active:
                print("Stopping recording...")
                if current_stream:
                    current_stream.stop()
                    current_stream.close()
                    current_stream = None
                recording_active = False
                ws.send(json.dumps({"status": "recording_stopped"}))
            else:
                ws.send(json.dumps({"status": "not_recording"}))
    except json.JSONDecodeError:
        print(f"Invalid JSON received: {message}")

def on_error(ws, error):
    print(f"### error ### {error}")

def on_close(ws, close_status_code, close_msg):
    global recording_active, current_stream
    print("### closed ###")
    if recording_active and current_stream:
        current_stream.stop()
        current_stream.close()
        recording_active = False

def on_open(ws):
    print("Opened connection")
    # You might want to send an initial status or handshake here

if __name__ == "__main__":
    print(f"Connecting to {WEBSOCKET_SERVER_URL}")
    ws_connection = websocket.WebSocketApp(WEBSOCKET_SERVER_URL,
                                    on_open=on_open,
                                    on_message=on_message,
                                    on_error=on_error,
                                    on_close=on_close)
    ws_connection.run_forever()
    print("Script finished.")