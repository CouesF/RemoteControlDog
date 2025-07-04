# app.py
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
import threading
import time
import sys
import os
import queue
import uuid

# --- Real DDS Imports ---
COMMUNICATION_DIR = "/home/d3lab/Projects/RemoteControlDog/robot_dog_python/communication"
if COMMUNICATION_DIR not in sys.path:
    sys.path.append(COMMUNICATION_DIR)

try:
    from dds_data_structure import DogStatus, SpeechControl, HeadCommand, HeadAction, PowerControl
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

# --- Authentication Configuration (Hardcoded for simplicity) ---
USERS = {
    "robotdog": "password123", # Example username and password
    "d3lab": "d3lab" # Example username and password
}
# A set to keep track of authenticated session IDs
authenticated_sids = set()

# --- Global DDS Publishers ---
speech_control_pub = None
head_command_pub = None
power_control_pub = None

# --- Speech Command Queue and Thread Control ---
speech_command_queue = queue.Queue()
speech_publisher_active = True

# --- Motor Error Decoding ---
MOTOR_ERROR_MAP = {
    0: "Over-current", 1: "Over-voltage", 2: "Under-voltage", 3: "Over-temperature (MOS)",
    4: "Encoder error", 5: "Reserved", 6: "Reserved", 7: "Communication Lost", 8: "Over-temperature (Motor)"
}

def decode_motor_errors(reserve0_val):
    """Decodes motor error bits into a human-readable string."""
    if reserve0_val == 0:
        return "OK"
    errors = [MOTOR_ERROR_MAP[bit] for bit, error_str in MOTOR_ERROR_MAP.items() if (reserve0_val >> bit) & 1]
    return ", ".join(errors) if errors else "OK"

# --- Attribute Helper ---
def get_nested_attr(obj, attrs, default=0.0):
    """Safely gets nested attributes from an object, returning a default if not found."""
    current_obj = obj
    for attr in attrs:
        if hasattr(current_obj, attr):
            current_obj = getattr(current_obj, attr)
        else:
            return default
    return current_obj

# --- Global Status Dictionary ---
latest_dog_status = {
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
HEAD_COMMAND_TOPIC = "HeadCommand"
POWER_CONTROL_TOPIC = "PowerControl"
DDS_NETWORK_INTERFACE = "enP8p1s0"

def dds_subscriber_thread():
    """Thread function for subscribing to DogStatus DDS topic."""
    global latest_dog_status
    sub = None
    try:
        sub = ChannelSubscriber(DOG_STATUS_TOPIC, DogStatus)
        sub.Init()
    except Exception as e:
        print(f"DDS Subscriber setup failed: {e}")
        latest_dog_status["status_message"] = f"DDS Setup Error: {e}. Check network interface & SDK."
        socketio.emit('dog_status_update', latest_dog_status)
        if sub and sub.is_initialized(): sub.Close()
        return

    print(f"DDS subscriber thread listening on topic: '{DOG_STATUS_TOPIC}'...")
    try:
        while True:
            msg = sub.Read(100)
            if msg:
                raw_timestamp_ns = getattr(msg, 'timestamp_ns', None)
                timestamp_ns_val = 0
                if raw_timestamp_ns is not None:
                    try:
                        timestamp_ns_val = int(raw_timestamp_ns)
                    except (ValueError, TypeError):
                        print(f"Warning: Could not convert timestamp_ns '{raw_timestamp_ns}' to int. Using 0.")
                
                latency_ms = (time.time_ns() - timestamp_ns_val) / 1_000_000.0 if timestamp_ns_val else 0.0

                try:
                    raw_battery = getattr(msg, 'battery_percent', None)
                    raw_cpu = getattr(msg, 'cpu_usage_percent', None)
                    raw_gpu = getattr(msg, 'gpu_usage_percent', None)
                    raw_memory = getattr(msg, 'memory_usage_percent', None)

                    battery_percent_val = 0.0
                    if raw_battery is not None:
                        try:
                            battery_percent_val = float(raw_battery)
                        except (ValueError, TypeError):
                            print(f"Warning: Could not convert battery_percent '{raw_battery}' to float. Using 0.0.")

                    cpu_usage_percent_val = 0.0
                    if raw_cpu is not None:
                        try:
                            cpu_usage_percent_val = float(raw_cpu)
                        except (ValueError, TypeError):
                            print(f"Warning: Could not convert cpu_usage_percent '{raw_cpu}' to float. Using 0.0.")

                    gpu_usage_percent_val = 0.0
                    if raw_gpu is not None:
                        try:
                            gpu_usage_percent_val = float(raw_gpu)
                        except (ValueError, TypeError):
                            print(f"Warning: Could not convert gpu_usage_percent '{raw_gpu}' to float. Using 0.0.")

                    memory_usage_percent_val = 0.0
                    if raw_memory is not None:
                        try:
                            memory_usage_percent_val = float(raw_memory)
                        except (ValueError, TypeError):
                            print(f"Warning: Could not convert memory_usage_percent '{raw_memory}' to float. Using 0.0.")


                    latest_dog_status.update({
                        "battery_percent": battery_percent_val,
                        "cpu_usage_percent": cpu_usage_percent_val,
                        "gpu_usage_percent": gpu_usage_percent_val,
                        "memory_usage_percent": memory_usage_percent_val,
                        "latency_ms": latency_ms,
                        "robot_mode_form": get_nested_attr(msg, ['robot_mode_form'], "N/A"),
                        "robot_mode_name": get_nested_attr(msg, ['robot_mode_name'], "N/A"),
                        "temp_cpu": get_nested_attr(msg, ['temperatures', 'cpu']),
                        "temp_gpu": get_nested_attr(msg, ['temperatures', 'gpu']),
                        "temp_tj": get_nested_attr(msg, ['temperatures', 'tj']),
                        "temp_soc0": get_nested_attr(msg, ['temperatures', 'soc0']),
                        "temp_soc1": get_nested_attr(msg, ['temperatures', 'soc1']),
                        "temp_soc2": get_nested_attr(msg, ['temperatures', 'soc2']),
                        "temp_cv0": get_nested_attr(msg, ['temperatures', 'cv0']),
                        "temp_cv1": get_nested_attr(msg, ['temperatures', 'cv1']),
                        "temp_cv2": get_nested_attr(msg, ['temperatures', 'cv2']),
                        "power_cpu_gpu_cv": get_nested_attr(msg, ['power', 'cpu_gpu_cv']),
                        "power_soc": get_nested_attr(msg, ['power', 'soc']),
                        "power_nv_power_total": get_nested_attr(msg, ['power', 'nv_power_total']),
                        "power_vdd_inn": get_nested_attr(msg, ['power', 'vdd_inn']),
                        "hardware_uptime_seconds": get_nested_attr(msg, ['hardware', 'uptime_seconds']),
                        "hardware_jetson_clocks_on": get_nested_attr(msg, ['hardware', 'jetson_clocks_on'], False),
                        "hardware_fan_speed_percent": get_nested_attr(msg, ['hardware', 'fan_speed_percent']),
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
                    print(f"DDS Data Format Error: {attr_e}")
                
                socketio.emit('dog_status_update', latest_dog_status)
            else:
                if not latest_dog_status["data_received"]:
                    latest_dog_status["status_message"] = "Waiting for data from robot..."
                latest_dog_status["data_received"] = False
                socketio.emit('dog_status_update', latest_dog_status)
                time.sleep(0.1)
    except Exception as e:
        print(f"DDS subscriber thread error: {e}")
        latest_dog_status["status_message"] = f"Critical DDS Stream Error: {e}"
        socketio.emit('dog_status_update', latest_dog_status, {"data_received": False})
    finally:
        if sub and sub.is_initialized(): sub.Close()
        print("DDS subscriber thread stopped.")

def _speech_publisher_thread():
    """
    Dedicated thread for publishing SpeechControl messages from the queue.
    This helps ensure non-blocking behavior for the SocketIO event handler.
    """
    global speech_control_pub, speech_publisher_active

    print("Speech publisher thread started.")
    while speech_publisher_active:
        try:
            command_msg = speech_command_queue.get(timeout=0.1)
            
            if speech_control_pub is None:
                print("Error: Speech control DDS publisher is not initialized in publisher thread.")
                continue

            try:
                speech_control_pub.Write(command_msg)
                print(f"Published SpeechControl command from queue to DDS topic '{SPEECH_CONTROL_TOPIC}'.")
            except Exception as e:
                print(f"Error publishing queued SpeechControl to DDS: {e}")
            finally:
                speech_command_queue.task_done()

        except queue.Empty:
            pass
        except Exception as e:
            print(f"Speech publisher thread error: {e}")
            time.sleep(0.1)
            
    print("Speech publisher thread stopped.")

@app.route('/')
def index():
    """Renders the main control panel HTML page."""
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    """Handles new client connections. Initially, clients are not authenticated."""
    print(f'Client connected: {request.sid}. Awaiting authentication.')
    # Do not add to authenticated_sids here. Authentication happens via 'authenticate' event.
    emit('authentication_required') # Inform the client it needs to log in

@socketio.on('disconnect')
def handle_disconnect():
    """Handles client disconnections and removes from authenticated sessions."""
    print(f'Client disconnected: {request.sid}')
    if request.sid in authenticated_sids:
        authenticated_sids.remove(request.sid)
        print(f"Removed authenticated SID: {request.sid}")

@socketio.on('authenticate')
def authenticate_client(data):
    """Handles authentication requests from clients."""
    username = data.get('username')
    password = data.get('password')
    sid = request.sid

    if USERS.get(username) == password:
        authenticated_sids.add(sid)
        print(f"Client {sid} authenticated successfully as '{username}'.")
        emit('login_response', {'status': 'success', 'message': 'Authentication successful.'})
    else:
        print(f"Client {sid} failed authentication for user '{username}'.")
        emit('login_response', {'status': 'error', 'message': 'Invalid username or password.'})

# --- Protected SocketIO Event Handlers ---
def check_authentication():
    """Decorator to check if a client is authenticated."""
    def decorator(f):
        def wrapped(*args, **kwargs):
            if request.sid not in authenticated_sids:
                print(f"Unauthorized access attempt by {request.sid} to {f.__name__}.")
                emit('unauthorized', {'message': 'Authentication required.'})
                return
            return f(*args, **kwargs)
        return wrapped
    return decorator

@socketio.on('speech_command')
@check_authentication()
def handle_speech_command(data):
    """Handles speech commands from the web UI and adds them to a queue for DDS publishing."""
    print(f"Received speech command from authenticated client {request.sid}: {data}")
    
    command_msg = SpeechControl()
    command_msg.text_to_speak = data.get('text', '')
    command_msg.stop_speaking = data.get('stop', False)
    
    action = 'stop' if command_msg.stop_speaking else 'speak'

    if 'volume' in data:
        try:
            command_msg.volume = int(data['volume'])
            if not command_msg.text_to_speak and not command_msg.stop_speaking:
                action = 'volume_change'
        except (ValueError, TypeError):
            print(f"Warning: Could not parse volume '{data['volume']}'. Ignoring.")

    speech_command_queue.put(command_msg)
    print(f"Queued SpeechControl command: text='{command_msg.text_to_speak}', stop={command_msg.stop_speaking}, volume={command_msg.volume}")
    
    emit('speech_response', {'status': 'success', 'action': action, 'message': 'Command queued successfully.'})


@socketio.on('head_control_command')
@check_authentication()
def handle_head_control_command(data):
    """Handles head control commands from the web UI and publishes them via DDS."""
    global head_command_pub

    if head_command_pub is None:
        print("Error: Head control DDS publisher is not initialized.")
        emit('head_response', {'status': 'error', 'message': 'Backend DDS publisher not ready.'})
        return

    print(f"Received head control command from authenticated client {request.sid}: {data}")

    command_msg = HeadCommand()
    command_msg.timestamp = time.time_ns()
    command = data.get('command')
    command_sent_status = 'error'
    command_message = 'Invalid command.'

    try:
        if command == 'move':
            pitch = float(data.get('pos1', 0.0))
            yaw = float(data.get('pos2', 0.0))
            expr = str(data.get('expr', 'c'))

            command_msg.action = HeadAction.MOVE_DIRECT.value
            command_msg.pitch_deg = pitch
            command_msg.yaw_deg = yaw
            command_msg.expression_char = expr
            
            head_command_pub.Write(command_msg)
            command_sent_status = 'success'
            command_message = f"Move command (yaw: {yaw}°, pitch: {pitch}°, expr: '{expr}') sent successfully."

        elif command == 'nod':
            command_msg.action = HeadAction.NOD.value
            head_command_pub.Write(command_msg)
            command_sent_status = 'success'
            command_message = "Nod command sent successfully."

        elif command == 'shake':
            command_msg.action = HeadAction.SHAKE.value
            head_command_pub.Write(command_msg)
            command_sent_status = 'success'
            command_message = "Shake command sent successfully."
            
        print(f"Published '{command}' command to DDS topic '{HEAD_COMMAND_TOPIC}'.")
        emit('head_response', {'status': command_sent_status, 'message': command_message})

    except (ValueError, TypeError) as e:
        print(f"Error parsing head control command data: {e}")
        emit('head_response', {'status': 'error', 'message': f'Invalid data format: {e}'})
    except Exception as e:
        print(f"Error publishing head control command to DDS: {e}")
        emit('head_response', {'status': 'error', 'message': f'DDS publish error: {e}'})


@socketio.on('power_command')
@check_authentication()
def handle_power_command(data):
    """Handles power control commands (shutdown/reboot) from the web UI and publishes them via DDS."""
    global power_control_pub

    if power_control_pub is None:
        print("Error: Power control DDS publisher is not initialized.")
        emit('power_response', {'status': 'error', 'message': 'Backend DDS publisher not ready.'})
        return

    command_type_str = data.get('command')
    command_type = 0
    response_message = "Invalid power command."
    response_status = "error"

    if command_type_str == "shutdown":
        command_type = 1
        response_message = "Shutdown command sent to robot."
        response_status = "success"
    elif command_type_str == "reboot":
        command_type = 2
        response_message = "Reboot command sent to robot."
        response_status = "success"
    else:
        print(f"Received unknown power command: {command_type_str}")
        emit('power_response', {'status': response_status, 'message': response_message})
        return

    power_command_msg = PowerControl()
    power_command_msg.command_type = command_type
    power_command_msg.command_id = uuid.uuid4().int & (2**31 - 1) 
    power_command_msg.message = f"Request to {command_type_str} from web UI."

    try:
        power_control_pub.Write(power_command_msg)
        print(f"Published PowerControl command '{command_type_str}' (ID: {power_command_msg.command_id}) to DDS topic '{POWER_CONTROL_TOPIC}'.")
        time.sleep(0.05) 
    except Exception as e:
        response_message = f"DDS publish error for {command_type_str}: {e}"
        response_status = "error"
        print(f"Error publishing power control command to DDS: {e}")
    finally:
        emit('power_response', {'status': response_status, 'message': response_message})


if __name__ == '__main__':
    try:
        print(f"Initializing DDS factory for main process on network interface: {DDS_NETWORK_INTERFACE}")
        ChannelFactoryInitialize(networkInterface=DDS_NETWORK_INTERFACE)
        
        speech_control_pub = ChannelPublisher(SPEECH_CONTROL_TOPIC, SpeechControl)
        speech_control_pub.Init()
        print(f"DDS Publisher for '{SPEECH_CONTROL_TOPIC}' initialized.")

        head_command_pub = ChannelPublisher(HEAD_COMMAND_TOPIC, HeadCommand)
        head_command_pub.Init()
        print(f"DDS Publisher for '{HEAD_COMMAND_TOPIC}' initialized.")

        power_control_pub = ChannelPublisher(POWER_CONTROL_TOPIC, PowerControl)
        power_control_pub.Init()
        print(f"DDS Publisher for '{POWER_CONTROL_TOPIC}' initialized.")

    except Exception as e:
        print(f"FATAL: DDS initialization failed: {e}. The application cannot start.")
        sys.exit(1)
        
    subscriber_thread = threading.Thread(target=dds_subscriber_thread, daemon=True)
    subscriber_thread.start()

    speech_publisher_thread = threading.Thread(target=_speech_publisher_thread, daemon=True)
    speech_publisher_thread.start()

    try:
        socketio.run(app, host='0.0.0.0', port=5002, debug=True, allow_unsafe_werkzeug=True)
    finally:
        speech_publisher_active = False
        if speech_publisher_thread.is_alive():
            speech_publisher_thread.join(timeout=1.0)
            for _ in range(5):  # Wait a bit for the thread to finish
                if not speech_publisher_thread.is_alive():
                    break
                time.sleep(0.1)
                speech_publisher_thread.join(timeout=1.0)
            if speech_publisher_thread.is_alive():
                print("Warning: Speech publisher thread did not terminate gracefully.")

