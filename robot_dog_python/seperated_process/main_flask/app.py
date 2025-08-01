# app.py
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
import threading
import time
import sys
import os
import queue
import uuid
import hashlib
import secrets
import subprocess
import signal
import atexit
from cyclonedds.domain import DomainParticipant
from cyclonedds.topic import Topic
from cyclonedds.pub import DataWriter
from cyclonedds.sub import DataReader

process_management_lock = threading.Lock() 
managed_processes = {}
SERVER_SCRIPT_PATH = "/home/d3lab/Projects/RemoteControlDog/robot_dog_python/seperated_process/main_process_manager.py"
PROCESS_MANAGER_BASE_DIR = os.path.dirname(SERVER_SCRIPT_PATH)
LOG_DIR = os.path.join(PROCESS_MANAGER_BASE_DIR, "logs")

# Corrected SCRIPTS_TO_MANAGE with absolute paths
SCRIPTS_TO_MANAGE = {
    "main_camera_gateway.py":     {"field_name": "cam_gateway",   "path": os.path.join(PROCESS_MANAGER_BASE_DIR, "main_camera_gateway.py"), "autostart": False},
    "main_control_gateway.py":    {"field_name": "ctrl_gateway",  "path": os.path.join(PROCESS_MANAGER_BASE_DIR, "main_control_gateway.py"), "autostart": False},
    "main_dog_status.py":         {"field_name": "dog_status",    "path": os.path.join(PROCESS_MANAGER_BASE_DIR, "main_dog_status.py"), "autostart": True},
    "main_jetson_power_server.py":{"field_name": "power_srv",     "path": os.path.join(PROCESS_MANAGER_BASE_DIR, "main_jetson_power_server.py"), "autostart": False},
    "main_dog_body_control.py":   {"field_name": "body_ctrl",     "path": os.path.join(PROCESS_MANAGER_BASE_DIR, "main_dog_body_control.py"), "autostart": False},
    "main_dog_head_control.py":   {"field_name": "head_ctrl",     "path": os.path.join(PROCESS_MANAGER_BASE_DIR, "main_dog_head_control.py"), "autostart": False},
    "main_speech_synthesis.py":   {"field_name": "speech_synth",  "path": os.path.join(PROCESS_MANAGER_BASE_DIR, "main_speech_synthesis.py"), "autostart": False},
    "main_speech_recognition.py": {"field_name": "speech_recog", "path": os.path.join(PROCESS_MANAGER_BASE_DIR, "main_speech_recognition.py"), "autostart": False},
    "start_woz_backend.py": {
        "field_name": "woz_backend",
        # Use the correct absolute path for this specific script
        "path": "/home/d3lab/Projects/RemoteControlDog/robot_dog_python/start_woz_backend.py",
        "autostart": False
    }
}

# --- Real DDS Imports ---
COMMUNICATION_DIR = "/home/d3lab/Projects/RemoteControlDog/robot_dog_python/communication"
if COMMUNICATION_DIR not in sys.path:
    sys.path.append(COMMUNICATION_DIR)

try:
    from dds_data_structure import (DogStatus, SpeechControl, HeadCommand, HeadAction, 
                                    PowerControl, MyMotionCommand, ProcessCommand, 
                                    ProcessAction, ProcessStatus, ScriptStatus)
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

# --- Global Shutdown Control ---
shutdown_event = threading.Event()
process_manager_process = None

# --- Authentication Configuration ---
def hash_password(password):
    """Hash a password with salt for secure storage."""
    salt = secrets.token_hex(16)
    password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
    return f"{salt}:{password_hash}"

def verify_password(password, stored_hash):
    """Verify a password against its hash."""
    try:
        salt, password_hash = stored_hash.split(':')
        return hashlib.sha256((password + salt).encode()).hexdigest() == password_hash
    except ValueError:
        # For backward compatibility with plain text passwords
        return password == stored_hash

# Hashed passwords (generated using hash_password function)
USERS = {
    "robotdog": hash_password("RobotDog2024!"),  # Strong password
    "d3lab": hash_password("D3Lab@Secure123"),    # Strong password
    "d3lab": hash_password("d3lab")
}

# Session management with timestamps for timeout
authenticated_sessions = {}  # {sid: {'username': str, 'login_time': float, 'last_activity': float}}
SESSION_TIMEOUT = 3600*5  # 5 hour timeout

# --- Global DDS Publishers ---
speech_control_pub = None
head_command_pub = None
power_control_pub = None
motion_command_pub = None
process_command_writer = None

dds_participant = None
process_command_writer = None
process_status_reader = None

# --- Global DDS Subscribers ---
dog_status_sub = None
process_status_sub = None

# --- Speech Command Queue and Thread Control ---
speech_command_queue = queue.Queue()
speech_publisher_active = True

# --- Motor Error Decoding ---
MOTOR_ERROR_MAP = {
    0: "Over-current", 1: "Over-voltage", 2: "Under-voltage", 3: "Over-temperature (MOS)",
    4: "Encoder error", 5: "Reserved", 6: "Reserved", 7: "Communication Lost", 8: "Over-temperature (Motor)"
}

# --- Process Manager Configuration ---
PROCESS_COMMAND_TOPIC = "ProcessCommand"
PROCESS_STATUS_TOPIC = "ProcessStatus"
SERVER_SCRIPT_NAME = "main_process_manager.py"

process_statuses = {}
status_lock = threading.Lock()

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
MOTION_COMMAND_TOPIC = "rt/my_motion_command"
DDS_NETWORK_INTERFACE = "enP8p1s0"

def dds_subscriber_thread():
    """Thread function for subscribing to DogStatus DDS topic."""
    global latest_dog_status, dog_status_sub
    
    try:
        dog_status_sub = ChannelSubscriber(DOG_STATUS_TOPIC, DogStatus)
        dog_status_sub.Init()
    except Exception as e:
        print(f"DDS Subscriber setup failed: {e}")
        latest_dog_status["status_message"] = f"DDS Setup Error: {e}. Check network interface & SDK."
        socketio.emit('dog_status_update', latest_dog_status)
        return

    print(f"DDS subscriber thread listening on topic: '{DOG_STATUS_TOPIC}'...")
    try:
        while not shutdown_event.is_set():
            msg = dog_status_sub.Read(100)
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
        print("DDS subscriber thread stopping...")

def _speech_publisher_thread():
    """
    Dedicated thread for publishing SpeechControl messages from the queue.
    This helps ensure non-blocking behavior for the SocketIO event handler.
    """
    global speech_control_pub, speech_publisher_active

    print("Speech publisher thread started.")
    while speech_publisher_active and not shutdown_event.is_set():
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

def launch_script(script_name: str):
    """Launches a script and manages it in-process."""
    with process_management_lock:
        if (script_name in managed_processes) and (managed_processes[script_name].poll() is None):
            print(f"-> Info: Script '{script_name}' is already running.")
            return

        config = SCRIPTS_TO_MANAGE.get(script_name)
        if not config:
            print(f"-> Error: Script '{script_name}' not defined in SCRIPTS_TO_MANAGE.")
            return

        script_path = config["path"] # Path is now absolute

        if not os.path.exists(script_path):
            print(f"-> Error: Script path does not exist: {script_path}")
            return

        os.makedirs(LOG_DIR, exist_ok=True)
        log_file_path = os.path.join(LOG_DIR, f"{script_name}.log")
        log_file = open(log_file_path, "a", buffering=1)
        log_file.write(f"\n--- SESSION STARTED AT {time.ctime()} ---\n")
        
        process = subprocess.Popen([sys.executable, script_path], stdout=log_file, stderr=subprocess.STDOUT)
        managed_processes[script_name] = process
        process.log_file = log_file
        print(f"-> Launched '{script_name}' with PID {process.pid}.")

def terminate_script(script_name: str):
    """Terminates a managed script."""
    with process_management_lock:
        if script_name in managed_processes and managed_processes[script_name].poll() is None:
            process = managed_processes[script_name]
            print(f"-> Terminating '{script_name}' with PID {process.pid}.")
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                print(f"-> Killing '{script_name}' as it did not terminate gracefully.")
                process.kill()
            
            if hasattr(process, 'log_file') and not process.log_file.closed:
                process.log_file.write(f"--- SESSION ENDED AT {time.ctime()} ---\n")
                process.log_file.close()
            
            del managed_processes[script_name]
            print(f"-> Terminated '{script_name}'.")

def build_and_broadcast_status():
    """Builds the process status dictionary and broadcasts it via SocketIO."""
    status_dict = {}
    with process_management_lock:
        for script_name, config in SCRIPTS_TO_MANAGE.items():
            status = "STOPPED"
            pid = 0
            if (script_name in managed_processes) and (managed_processes[script_name].poll() is None):
                status = "RUNNING"
                pid = managed_processes[script_name].pid
            
            status_dict[script_name] = {
                "script_name": script_name,
                "status": status,
                "pid": pid
            }
    
    # Broadcast to all connected clients
    socketio.emit('process_status_update', status_dict)

@socketio.on('connect')
def handle_connect():
    """Handles new client connections. Initially, clients are not authenticated."""
    print(f'Client connected: {request.sid}. Awaiting authentication.')
    # Do not add to authenticated_sids here. Authentication happens via 'authenticate' event.
    emit('authentication_required', {'message': 'Please log in to continue.'}) # Inform the client it needs to log in

def is_session_valid(sid):
    """Check if a session is valid and not expired."""
    if sid not in authenticated_sessions:
        return False
    
    session = authenticated_sessions[sid]
    current_time = time.time()
    
    # Check if session has expired
    if current_time - session['last_activity'] > SESSION_TIMEOUT:
        del authenticated_sessions[sid]
        print(f"Session {sid} expired for user {session['username']}")
        return False
    
    # Update last activity time
    session['last_activity'] = current_time
    return True

@socketio.on('disconnect')
def handle_disconnect():
    """Handles client disconnections and removes from authenticated sessions."""
    print(f'Client disconnected: {request.sid}')
    if request.sid in authenticated_sessions:
        username = authenticated_sessions[request.sid]['username']
        del authenticated_sessions[request.sid]
        print(f"Removed authenticated session for user: {username}")

@socketio.on('authenticate')
def authenticate_client(data):
    """Handles authentication requests from clients."""
    username = data.get('username')
    password = data.get('password')
    sid = request.sid

    if username in USERS and verify_password(password, USERS[username]):
        current_time = time.time()
        authenticated_sessions[sid] = {
            'username': username,
            'login_time': current_time,
            'last_activity': current_time
        }
        print(f"Client {sid} authenticated successfully as '{username}'.")
        emit('login_response', {'status': 'success', 'message': 'Authentication successful.'})
    else:
        print(f"Client {sid} failed authentication for user '{username}'.")
        emit('login_response', {'status': 'error', 'message': 'Invalid username or password.'})

# --- Protected SocketIO Event Handlers ---
def check_authentication(f):
    """Decorator to check if a client is authenticated."""
    def wrapped(*args, **kwargs):
        if not is_session_valid(request.sid):
            print(f"Unauthorized access attempt by {request.sid} to {f.__name__}.")
            emit('unauthorized', {'message': 'Authentication required.'})
            return
        return f(*args, **kwargs)
    wrapped.__name__ = f.__name__
    return wrapped

@socketio.on('speech_command')
@check_authentication
def handle_speech_command(data):
    """
    Handles speech commands from the web UI, inspired by speech_test.py logic.
    - For speaking, it queues a volume-only command, then a command with both text and volume.
    - For volume changes, it queues a volume-only command.
    - For stopping, it queues a stop command.
    """
    print(f"Received speech command from authenticated client {request.sid}: {data}")

    # Command to stop speaking is highest priority
    if data.get('stop', False):
        stop_cmd = SpeechControl()
        stop_cmd.stop_speaking = True
        speech_command_queue.put(stop_cmd)
        print("Queued SpeechControl command: stop=True")
        emit('speech_response', {'status': 'success', 'action': 'stop', 'message': 'Stop command queued.'})
        return

    volume = data.get('volume')
    text_to_speak = data.get('text', '').strip()
    action = 'volume_change'  # Default action if only volume is present

    # If there is text to speak, mimic speech_test.py by queuing two commands
    if text_to_speak:
        action = 'speak'
        current_volume = 70  # A sensible default
        if volume is not None:
            try:
                current_volume = int(volume)
            except (ValueError, TypeError):
                print(f"Warning: Could not parse volume '{volume}'. Using default.")

        # 1. Queue a volume-only command first. This might prepare the audio system.
        vol_only_cmd = SpeechControl()
        vol_only_cmd.volume = current_volume
        speech_command_queue.put(vol_only_cmd)
        print(f"Queued pre-emptive SpeechControl command: volume={vol_only_cmd.volume}")

        # 2. Queue the main speak command with both text and volume, as seen in speech_test.py.
        speak_cmd = SpeechControl()
        speak_cmd.text_to_speak = text_to_speak
        speak_cmd.volume = current_volume
        speech_command_queue.put(speak_cmd)
        print(f"Queued SpeechControl command: text='{speak_cmd.text_to_speak}', volume={speak_cmd.volume}")
        
        emit('speech_response', {'status': 'success', 'action': action, 'message': 'Speak command queued.'})

    # If there is only a volume change from the slider (no text)
    elif volume is not None:
        try:
            vol_cmd = SpeechControl()
            vol_cmd.volume = int(volume)
            speech_command_queue.put(vol_cmd)
            print(f"Queued SpeechControl command: volume={vol_cmd.volume}")
            emit('speech_response', {'status': 'success', 'action': action, 'message': 'Volume command queued.'})
        except (ValueError, TypeError):
            print(f"Warning: Could not parse volume '{volume}'. Ignoring.")
            emit('speech_response', {'status': 'error', 'action': 'volume_change', 'message': 'Invalid volume format.'})

@socketio.on('head_control_command')
@check_authentication
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
@check_authentication
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

@socketio.on('motion_command')
@check_authentication
def handle_motion_command(data):
    """Handles motion commands (state change, leg control, walking) and publishes them via DDS."""
    global motion_command_pub

    if motion_command_pub is None:
        print("Error: Motion control DDS publisher is not initialized.")
        emit('motion_response', {'status': 'error', 'message': 'Backend DDS publisher not ready.'})
        return

    print(f"Received motion command from authenticated client {request.sid}: {data}")
    
    try:
        command_type = data.get('command_type')
        msg = None
        response_message = "Command sent."

        if command_type == 0: # State Change
            state_enum = int(data.get('state_enum'))
            leg_selection = int(data.get('leg_selection', 0))
            msg = MyMotionCommand(
                command_type=command_type,
                state_enum=state_enum,
                leg_selection=leg_selection
            )
            response_message = f"State change command to state {state_enum} sent."

        elif command_type == 1: # Leg Control
            if 'sub_command' in data and data['sub_command'] == 'q':
                msg = MyMotionCommand(command_type=1, command_id=ord('q'), state_enum=0)
                response_message = "Exit Leg Mode command sent."
            else:
                angle1 = float(data.get('angle1'))
                angle2 = float(data.get('angle2'))
                msg = MyMotionCommand(
                    command_type=command_type,
                    state_enum=0, # It's good practice to provide a neutral value
                    angle1=angle1,
                    angle2=angle2
                )
                response_message = f"Leg angles ({angle1:.2f}, {angle2:.2f}) sent."

        elif command_type == 2: # High-level walk
            x = float(data.get('x') or 0.0)
            y = float(data.get('y') or 0.0)
            r = float(data.get('r') or 0.0)
            msg = MyMotionCommand(
                command_type=command_type,
                state_enum=0, # Provide a neutral value
                x=x,
                y=y,
                r=r
            )
            response_message = f"Walk command (x:{x:.2f}, y:{y:.2f}, r:{r:.2f}) sent."

        else:
            emit('motion_response', {'status': 'error', 'message': 'Invalid command type.'})
            return

        if msg:
            motion_command_pub.Write(msg)
            print(f"Published MyMotionCommand to DDS topic '{MOTION_COMMAND_TOPIC}': {msg}")
            emit('motion_response', {'status': 'success', 'message': response_message})

    except (ValueError, TypeError, KeyError) as e:
        print(f"Error parsing motion command data: {e}")
        emit('motion_response', {'status': 'error', 'message': f'Invalid data format: {e}'})
    except Exception as e:
        print(f"Error publishing motion command to DDS: {e}")
        emit('motion_response', {'status': 'error', 'message': f'DDS publish error: {e}'})

def process_status_subscriber_thread():
    """Thread function for subscribing to ProcessStatus DDS topic using cyclonedds."""
    global process_statuses, process_status_reader
    
    if dds_participant is None:
        print("Error: CycloneDDS participant not initialized for process status subscriber.")
        return

    # Use cyclonedds Topic and DataReader
    status_topic = Topic(dds_participant, PROCESS_STATUS_TOPIC, ProcessStatus)
    process_status_reader = DataReader(dds_participant, status_topic)

    print(f"Process Status (cyclonedds) subscriber listening on topic: '{PROCESS_STATUS_TOPIC}'...")
    try:
        while not shutdown_event.is_set():
            # DataReader's take() returns a list of samples
            for msg in process_status_reader.take():
                print(f"[{time.ctime()}] Received status update from manager: {msg.timestamp}")
                # The ProcessStatus message has fixed attribute names
                # We need to get the list of script names from the ProcessStatus dataclass definition
                # This is a bit advanced, but robust.
                from dataclasses import fields
                script_field_names = [f.name for f in fields(ProcessStatus) if f.name != 'timestamp']

                current_statuses = {}
                for field_name in script_field_names:
                    status_obj = getattr(msg, field_name)
                    if status_obj:
                        current_statuses[status_obj.script_name] = {
                            "script_name": status_obj.script_name,
                            "status": status_obj.status,
                            "pid": status_obj.pid
                        }
                with status_lock:
                    process_statuses = current_statuses
                # Atomically update the global dictionary and emit
                # socketio.emit('process_status_update', process_statuses)
            
            time.sleep(0.1) # Wait a bit between checks
    except Exception as e:
        print(f"Process Status subscriber thread error: {e}")
    finally:
        print("Process Status subscriber thread stopped.")

def status_broadcaster_thread():
    """
    Dedicated thread to broadcast the latest process status to all clients
    at a regular interval by directly checking the state.
    """
    print("Status broadcaster thread started.")
    while not shutdown_event.is_set():
        try:
            # Broadcast every 1 second.
            build_and_broadcast_status()
            time.sleep(1) 
        except Exception as e:
            print(f"Status broadcaster thread error: {e}")
    print("Status broadcaster thread stopped.")
    
@socketio.on('request_initial_process_status')
@check_authentication
def handle_request_initial_process_status():
    """Sends the current process status immediately to the requesting client."""
    sid = request.sid
    print(f"Client {sid} requested initial process status.")
    
    # We no longer need to request a status from a server, just build and send it.
    build_and_broadcast_status()

@socketio.on('process_command')
@check_authentication
def handle_process_command(data):
    """Handles process control commands (start/stop/etc.) directly."""
    command = data.get('command')
    target = data.get('target')
    print(f"Received direct process command from {request.sid}: {command} {target}")

    action_map = {
        'start': lambda t: launch_script(t),
        'stop': lambda t: terminate_script(t),
        'restart': lambda t: (terminate_script(t), time.sleep(0.2), launch_script(t)),
        'start_all': lambda t: [launch_script(s) for s in SCRIPTS_TO_MANAGE.keys()],
        'stop_all': lambda t: [terminate_script(s) for s in list(managed_processes.keys())],
        'restart_all': lambda t: (
            [terminate_script(s) for s in list(managed_processes.keys())], 
            time.sleep(0.5), 
            [launch_script(s) for s in SCRIPTS_TO_MANAGE.keys()]
        ),
        'shutdown_server': lambda t: socketio.stop() # Example of how to stop the server
    }

    if command in action_map:
        action_function = action_map[command]
        
        # We need to handle 'shutdown_server' specially as it doesn't operate on a script target.
        if command == 'shutdown_server':
             print("-> Received SHUTDOWN_SERVER command. The web server will stop.")
             emit('process_response', {'status': 'success', 'message': f"Command '{command}' received. Server is shutting down."})
             # A more robust solution for shutdown is handled by the atexit handler.
             # This just confirms receipt of the command. We can trigger a graceful shutdown.
             shutdown_event.set() # Use the existing event to trigger cleanup
        else:
            action_function(target)
            message = f"Command '{command}' for '{target or 'all'}' executed."
            print(f"-> {message}")
            emit('process_response', {'status': 'success', 'message': message})
            # Give immediate feedback to the client
            build_and_broadcast_status()
    else:
        message = 'Invalid command.'
        print(f"-> Error: {message} - '{command}'")
        emit('process_response', {'status': 'error', 'message': message})


def launch_process_manager_server():
    time.sleep(8)  # Give time for the main process to initialize
    """Checks for and launches the main_process_manager.py script."""
    script_path = os.path.join(os.path.dirname(__file__), '..', SERVER_SCRIPT_NAME) # Assuming it's in parent dir
    # If the script path is different, adjust it. e.g., os.path.join(os.path.dirname(__file__), SERVER_SCRIPT_NAME)
    
    if not os.path.exists(script_path):
        print(f"WARNING: Process manager script not found at '{script_path}'. Cannot launch it.")
        return None
    
    try:
        # Use Popen to run in the background without blocking
        print(f"Attempting to launch process manager server from: {script_path}")
        server_process = subprocess.Popen(
            [sys.executable, script_path],
            stdout=subprocess.DEVNULL, # Hide output from console
            stderr=subprocess.PIPE, # Capture errors
        )
        print(f"-> Launched process manager server with PID: {server_process.pid}")
        time.sleep(6) # Give server time to initialize
        return server_process
    except Exception as e:
        print(f"CRITICAL: Failed to launch process manager server: {e}")
        return None

def cleanup_resources():
    """Clean up all resources before shutdown."""
    global speech_publisher_active, process_manager_process
    global speech_control_pub, head_command_pub, power_control_pub, motion_command_pub, process_command_writer
    global dog_status_sub, process_status_sub
    
    print("Starting cleanup...")
    
    # Set shutdown flag
    shutdown_event.set()
    
    # Stop speech publisher
    speech_publisher_active = False

    print("-> Terminating all managed child processes...")
    with process_management_lock:
        # Create a copy of the keys to avoid issues while iterating and deleting
        scripts_to_terminate = list(managed_processes.keys())
    
    for script_name in scripts_to_terminate:
        terminate_script(script_name)
    
    # Close all DDS publishers
    publishers = [
        ('speech_control_pub', speech_control_pub),
        ('head_command_pub', head_command_pub),
        ('power_control_pub', power_control_pub),
        ('motion_command_pub', motion_command_pub),
        ('process_command_writer', process_command_writer)
    ]
    
    for name, pub in publishers:
        if pub:
            try:
                pub.Close()
                print(f"Closed DDS publisher: {name}")
            except Exception as e:
                print(f"Error closing DDS publisher {name}: {e}")
    
    # Close all DDS subscribers
    subscribers = [
        ('dog_status_sub', dog_status_sub),
        ('process_status_sub', process_status_sub)
    ]
    
    # Terminate process manager if it exists
    if process_manager_process:
        try:
            process_manager_process.terminate()
            process_manager_process.wait(timeout=5)
            print(f"Terminated process manager server (PID: {process_manager_process.pid})")
        except subprocess.TimeoutExpired:
            print("Process manager didn't terminate gracefully, killing it...")
            process_manager_process.kill()
        except Exception as e:
            print(f"Error terminating process manager: {e}")
    
    print("Cleanup completed.")

def signal_handler(signum, frame):
    """Handle shutdown signals."""
    print(f"Received signal {signum}, shutting down...")
    cleanup_resources()
    sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Register cleanup function to run on exit
atexit.register(cleanup_resources)

if __name__ == '__main__':
    print("--- Initializing Integrated Services ---")
    
    # 1. Perform autostart for designated scripts
    print("-> Performing autostart for designated scripts...")
    for script_name, config in SCRIPTS_TO_MANAGE.items():
        if config.get("autostart", False):
            launch_script(script_name)
    print("-> Autostart complete.")
    
    # 2. Initialize all necessary DDS publishers and subscribers
    try:
        print(f"Initializing DDS factory for main process on network interface: {DDS_NETWORK_INTERFACE}")
        ChannelFactoryInitialize(networkInterface=DDS_NETWORK_INTERFACE)

        # Publishers for robot control (these are correct and needed)
        speech_control_pub = ChannelPublisher(SPEECH_CONTROL_TOPIC, SpeechControl)
        speech_control_pub.Init()
        print(f"DDS Publisher for '{SPEECH_CONTROL_TOPIC}' initialized.")

        head_command_pub = ChannelPublisher(HEAD_COMMAND_TOPIC, HeadCommand)
        head_command_pub.Init()
        print(f"DDS Publisher for '{HEAD_COMMAND_TOPIC}' initialized.")

        power_control_pub = ChannelPublisher(POWER_CONTROL_TOPIC, PowerControl)
        power_control_pub.Init()
        print(f"DDS Publisher for '{POWER_CONTROL_TOPIC}' initialized.")

        motion_command_pub = ChannelPublisher(MOTION_COMMAND_TOPIC, MyMotionCommand)
        motion_command_pub.Init()
        print(f"DDS Publisher for '{MOTION_COMMAND_TOPIC}' initialized.")

    except Exception as e:
        print(f"FATAL: DDS initialization failed: {e}. The application cannot start.")
        cleanup_resources()
        sys.exit(1)
        
    # 3. Start the necessary background threads
    print("-> Starting background threads...")
    
    # Thread to get dog status from DDS
    subscriber_thread = threading.Thread(target=dds_subscriber_thread, daemon=True)
    subscriber_thread.start()

    # Thread to send speech commands via DDS
    speech_publisher_thread = threading.Thread(target=_speech_publisher_thread, daemon=True)
    speech_publisher_thread.start()

    # Thread to periodically broadcast the status of managed processes
    broadcaster_thread = threading.Thread(target=status_broadcaster_thread, daemon=True)
    broadcaster_thread.start()

    # (The obsolete process_status_thread is now removed)
    print("-> All threads started.")

    # 4. Run the web server
    try:
        print("Starting Flask-SocketIO server on http://0.0.0.0:5004...")
        socketio.run(app, host='0.0.0.0', port=5004, debug=False, allow_unsafe_werkzeug=True)
    except KeyboardInterrupt:
        print("Received keyboard interrupt, shutting down...")
    except Exception as e:
        print(f"Server error: {e}")
    finally:
        cleanup_resources()