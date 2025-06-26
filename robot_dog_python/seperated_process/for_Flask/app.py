# app.py
from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import threading
import time
import sys
import os

# --- Real DDS Imports ---
# This path needs to be correct on the robot executing this script.
COMMUNICATION_DIR = "/home/d3lab/Projects/RemoteControlDog/robot_dog_python/communication"
if COMMUNICATION_DIR not in sys.path:
    sys.path.append(COMMUNICATION_DIR)

try:
    # MODIFIED: Import HeadControl and HeadCommand alongside other structures
    from dds_data_structure import DogStatus, SpeechControl, HeadControl, HeadCommand
except ImportError as e:
    print(f"Error: Could not import DDS data structures. Please ensure 'dds_data_structure.py' "
          f"is located at '{COMMUNICATION_DIR}/dds_data_structure.py'.")
    print(f"ImportError details: {e}")
    sys.exit(1)

try:
    from unitree_sdk2py.core.channel import ChannelSubscriber, ChannelPublisher, ChannelFactoryInitialize
except ImportError as e:
    print(f"Error: Could not import Unitree SDK components. Please ensure 'unitree_sdk2py' "
          f"is installed and accessible in your Python environment.")
    print(f"ImportError details: {e}")
    sys.exit(1)
# --- End of Real DDS Imports ---

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_super_secret_key_here_please_change_this_for_production'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# --- Global DDS Publishers ---
speech_control_pub = None
head_control_pub = None # NEW: Publisher for head control

# --- Motor Error Decoding ---
MOTOR_ERROR_MAP = {
    0: "Over-current", 1: "Over-voltage", 2: "Under-voltage", 3: "Over-temperature (MOS)",
    4: "Encoder error", 5: "Reserved", 6: "Reserved", 7: "Communication Lost", 8: "Over-temperature (Motor)"
}

def decode_motor_errors(reserve0_val):
    if reserve0_val == 0:
        return "OK"
    errors = [MOTOR_ERROR_MAP[bit] for bit, error_str in MOTOR_ERROR_MAP.items() if (reserve0_val >> bit) & 1]
    return ", ".join(errors) if errors else "OK"

# --- Attribute Helper ---
def get_nested_attr(obj, attrs, default=0.0):
    # ... (function remains the same)
    current_obj = obj
    for attr in attrs:
        if hasattr(current_obj, attr):
            current_obj = getattr(current_obj, attr)
        else:
            return default
    return current_obj

# --- Global Status Dictionary ---
latest_dog_status = {
    # ... (dictionary remains the same)
    "battery_percent": 0.0, "cpu_usage_percent": 0.0, "gpu_usage_percent": 0.0,
    "memory_usage_percent": 0.0, "latency_ms": 0.0, "robot_mode_form": "N/A",
    "robot_mode_name": "N/A", "temp_cpu": 0.0, "temp_gpu": 0.0, "temp_tj": 0.0,
    "temp_soc0": 0.0, "temp_soc1": 0.0, "temp_soc2": 0.0, "temp_cv0": 0.0,
    "temp_cv1": 0.0, "temp_cv2": 0.0, "power_cpu_gpu_cv": 0.0, "power_soc": 0.0,
    "power_nv_power_total": 0.0, "power_vdd_inn": 0.0, "hardware_uptime_seconds": 0.0,
    "hardware_jetson_clocks_on": False, "hardware_fan_speed_percent": 0.0,
    "hardware_emc_usage_percent": 0.0, "hardware_disk_usage_percent": 0.0,
    "status_message": "Initializing...", "data_received": False, "motors": []
}

# --- DDS Configuration ---
DOG_STATUS_TOPIC = "DogStatus"
SPEECH_CONTROL_TOPIC = "SpeechControl"
HEAD_CONTROL_TOPIC = "HeadControl" # NEW: Topic for head control commands
DDS_NETWORK_INTERFACE = "enP8p1s0"

def dds_subscriber_thread():
    # ... (function remains the same)
    global latest_dog_status
    sub = None
    try:
        sub = ChannelSubscriber(DOG_STATUS_TOPIC, DogStatus)
        sub.Init()
    except Exception as e:
        print(f"DDS Subscriber setup failed: {e}")
        latest_dog_status["status_message"] = f"DDS Setup Error: {e}"
        socketio.emit('dog_status_update', latest_dog_status)
        if sub and sub.is_initialized(): sub.Close()
        return
    # ... (rest of the function is unchanged) ...
    print(f"DDS subscriber thread listening on topic: '{DOG_STATUS_TOPIC}'...")
    try:
        while True:
            msg = sub.Read(100)
            if msg:
                latency_ms = (time.time_ns() - msg.timestamp_ns) / 1_000_000.0
                try:
                    latest_dog_status.update({
                        "battery_percent": float(msg.battery_percent),
                        "cpu_usage_percent": float(msg.cpu_usage_percent),
                        # ... all other fields
                        "status_message": "Data received successfully.",
                        "data_received": True,
                        "motors": [{
                            'mode': getattr(msg, f'm{i}_mode', 0), 'q': getattr(msg, f'm{i}_q', 0.0),
                            'dq': getattr(msg, f'm{i}_dq', 0.0), 'ddq': getattr(msg, f'm{i}_ddq', 0.0),
                            'tau_est': getattr(msg, f'm{i}_tau_est', 0.0), 'temperature': getattr(msg, f'm{i}_temperature', 0),
                            'lost': getattr(msg, f'm{i}_lost', 0), 'reserve0': getattr(msg, f'm{i}_reserve0', 0),
                            'error_str': decode_motor_errors(getattr(msg, f'm{i}_reserve0', 0))
                        } for i in range(12)]
                    })
                except Exception as attr_e:
                    latest_dog_status["status_message"] = f"DDS Data Format Error: {attr_e}"
                    latest_dog_status["data_received"] = False
                socketio.emit('dog_status_update', latest_dog_status)
            else:
                if not latest_dog_status["data_received"]:
                    latest_dog_status["status_message"] = "Waiting for data from robot..."
                latest_dog_status["data_received"] = False
                socketio.emit('dog_status_update', latest_dog_status)
                time.sleep(0.1)
    except Exception as e:
        print(f"DDS subscriber thread error: {e}")
    finally:
        if sub and sub.is_initialized(): sub.Close()
        print("DDS subscriber thread stopped.")


@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    print('Client connected')
    emit('dog_status_update', latest_dog_status)

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

@socketio.on('speech_command')
def handle_speech_command(data):
    # ... (function remains the same)
    global speech_control_pub
    if speech_control_pub is None:
        emit('speech_response', {'status': 'error', 'message': 'Backend DDS publisher not ready.'})
        return
    # ... (rest of the function is unchanged) ...
    command_msg = SpeechControl()
    command_msg.text_to_speak = data.get('text', '')
    command_msg.stop_speaking = data.get('stop', False)
    if 'volume' in data:
        command_msg.volume = int(data['volume'])
    speech_control_pub.Write(command_msg)
    emit('speech_response', {'status': 'success', 'message': 'Command sent.'})

# --- NEW: Function to handle head control commands from the web UI ---
@socketio.on('head_control_command')
def handle_head_command(data):
    """Handles head control commands from the web UI and publishes them via DDS."""
    global head_control_pub
    
    if head_control_pub is None:
        print("Error: Head control DDS publisher is not initialized.")
        emit('head_response', {'status': 'error', 'message': 'Backend DDS publisher not ready.'})
        return

    print(f"Received head control command from web UI: {data}")
    
    command = data.get('command')
    if not command:
        emit('head_response', {'status': 'error', 'message': 'Invalid command format.'})
        return
        
    msg = HeadControl()
    msg.timestamp_ns = time.time_ns()
    
    try:
        if command == 'nod':
            msg.command = HeadCommand.NOD
        elif command == 'shake':
            msg.command = HeadCommand.SHAKE
        elif command == 'move':
            msg.command = HeadCommand.MOVE_ABSOLUTE
            msg.target_angles_deg = [
                float(data.get('pos1', 0.0)),
                float(data.get('pos2', 0.0))
            ]
            # Ensure expression is a single character, default to 'c'
            msg.expression_char = (data.get('expr') or 'c')[:1]
        else:
            emit('head_response', {'status': 'error', 'message': f'Unknown command: {command}'})
            return
            
        head_control_pub.Write(msg)
        print(f"Published HeadControl command '{command}' to DDS topic '{HEAD_CONTROL_TOPIC}'.")
        # Send a success response back to the client UI.
        emit('head_response', {'status': 'success', 'message': f'Command "{command}" sent.'})

    except Exception as e:
        print(f"Error processing or publishing head command: {e}")
        emit('head_response', {'status': 'error', 'message': f'Backend error: {e}'})


if __name__ == '__main__':
    # try:
    print(f"Initializing DDS factory on network interface: {DDS_NETWORK_INTERFACE}")
    ChannelFactoryInitialize(networkInterface=DDS_NETWORK_INTERFACE)
        
        # Initialize Speech Publisher
        # speech_control_pub = ChannelPublisher(SPEECH_CONTROL_TOPIC, SpeechControl)
        # speech_control_pub.Init()
        # print(f"DDS Publisher for '{SPEECH_CONTROL_TOPIC}' initialized.")

        # NEW: Initialize Head Control Publisher
    head_control_pub = ChannelPublisher(HEAD_CONTROL_TOPIC, HeadControl)
    head_control_pub.Init()
    print(f"DDS Publisher for '{HEAD_CONTROL_TOPIC}' initialized.")

    # except Exception as e:
    #    print(f"FATAL: DDS initialization failed: {e}. The application cannot start.")
    #    sys.exit(1)
        
    subscriber_thread = threading.Thread(target=dds_subscriber_thread, daemon=True)
    subscriber_thread.start()

    socketio.run(app, host='0.0.0.0', port=5001, debug=True, allow_unsafe_werkzeug=True)