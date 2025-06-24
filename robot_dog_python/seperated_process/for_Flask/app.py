# app.py
from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import threading
import time
import sys
import os

# --- Real DDS Imports ---
# Adjust this path based on your exact directory structure on the robot.
# Given your path: /home/d3lab/Projects/RemoteControlDog/robot_dog_python/seperated_process/for_Flask/app.py
# The communication directory is at: /home/d3lab/Projects/RemoteControlDog/robot_dog_python/communication
COMMUNICATION_DIR = "/home/d3lab/Projects/RemoteControlDog/robot_dog_python/communication"
if COMMUNICATION_DIR not in sys.path:
    sys.path.append(COMMUNICATION_DIR)

try:
    from dds_data_structure import DogStatus
    # Ensure your DogStatus in dds_data_structure.py truly contains:
    # robot_mode_form, robot_mode_name, temperatures, power, hardware fields
    # If not, the application might display 'N/A' or default values for those fields.
except ImportError as e:
    print(f"Error: Could not import DogStatus. Please ensure 'dds_data_structure.py' "
          f"is located at '{COMMUNICATION_DIR}/dds_data_structure.py' and its dependencies are met.")
    print(f"ImportError details: {e}")
    sys.exit(1) # Exit if essential DDS data structure cannot be imported

try:
    from unitree_sdk2py.core.channel import ChannelSubscriber, ChannelFactoryInitialize
except ImportError as e:
    print(f"Error: Could not import Unitree SDK components. Please ensure 'unitree_sdk2py' "
          f"is installed and accessible in your Python environment.")
    print(f"ImportError details: {e}")
    sys.exit(1) # Exit if essential SDK components cannot be imported

# --- End of Real DDS Imports ---

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_super_secret_key_here_please_change_this_for_production'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# --- NEW: Helper function to decode motor error bits ---
MOTOR_ERROR_MAP = {
    0: "Over-current", 1: "Over-voltage", 2: "Under-voltage", 3: "Over-temperature (MOS)",
    4: "Encoder error", 5: "Reserved", 6: "Reserved", 7: "Communication Lost", 8: "Over-temperature (Motor)"
}

def decode_motor_errors(reserve0_val):
    """Decodes the error integer into a human-readable string."""
    if reserve0_val == 0:
        return "OK"
    errors = []
    for bit, error_str in MOTOR_ERROR_MAP.items():
        if (reserve0_val >> bit) & 1:
            errors.append(error_str)
    return ", ".join(errors) if errors else "OK"
# ---

# Helper function to safely get nested attributes and provide default value
def get_nested_attr(obj, attrs, default=0.0):
    """
    Safely retrieves a nested attribute from an object.
    obj: The base object.
    attrs: A list of strings representing the nested attribute path (e.g., ['bms_state', 'soc']).
    default: The default value to return if any attribute in the path is missing.
    """
    current_obj = obj
    for attr in attrs:
        if hasattr(current_obj, attr):
            current_obj = getattr(current_obj, attr)
        else:
            return default
    return current_obj

# Global variable to hold the latest DogStatus data
latest_dog_status = {
    # Core stats
    "battery_percent": 0.0,
    "cpu_usage_percent": 0.0,
    "gpu_usage_percent": 0.0,
    "memory_usage_percent": 0.0,
    "latency_ms": 0.0,

    # Robot Status
    "robot_mode_form": "N/A",
    "robot_mode_name": "N/A",

    # Jetson Temperatures
    "temp_cpu": 0.0,
    "temp_gpu": 0.0,
    "temp_tj": 0.0,
    "temp_soc0": 0.0,
    "temp_soc1": 0.0,
    "temp_soc2": 0.0,
    "temp_cv0": 0.0,
    "temp_cv1": 0.0,
    "temp_cv2": 0.0,

    # Jetson Power Consumption
    "power_cpu_gpu_cv": 0.0,
    "power_soc": 0.0,
    "power_nv_power_total": 0.0,
    "power_vdd_inn": 0.0,

    # Jetson Hardware Stats
    "hardware_uptime_seconds": 0.0,
    "hardware_jetson_clocks_on": False,
    "hardware_fan_speed_percent": 0.0,
    "hardware_emc_usage_percent": 0.0,
    "hardware_disk_usage_percent": 0.0,

    # UI status messages
    "status_message": "Initializing...",
    "data_received": False,

    # motor status
    "motors": []
}

# DDS Topic name (must match the publisher's topic from main_dog_status.py)
DOG_STATUS_TOPIC = "DogStatus"
# DDS Network Interface from your main_dog_status.py and status_receive.py
DDS_NETWORK_INTERFACE = "enP8p1s0"

# Thread for DDS subscription
def dds_subscriber_thread():
    """
    This function runs in a separate thread to continuously subscribe to DDS
    messages and update the global latest_dog_status.
    """
    global latest_dog_status

    print(f"Initializing DDS factory on network interface: {DDS_NETWORK_INTERFACE}")
    sub = None
    try:
        ChannelFactoryInitialize(networkInterface=DDS_NETWORK_INTERFACE)
        sub = ChannelSubscriber(DOG_STATUS_TOPIC, DogStatus)
        sub.Init()
    except Exception as e:
        print(f"DDS Initialization or Subscriber setup failed: {e}")
        latest_dog_status["status_message"] = f"DDS Setup Error: {e}. Check network interface & SDK."
        socketio.emit('dog_status_update', latest_dog_status)
        if sub and sub.is_initialized(): # Ensure to close if partially initialized
            sub.Close()
        return # Exit thread if DDS setup fails

    print(f"DDS subscriber thread listening for data on topic: '{DOG_STATUS_TOPIC}'...")

    try:
        while True:
            msg = sub.Read(100) # Wait for max 100ms for a message

            if msg is not None:
                receive_timestamp_ns = time.time_ns()
                latency_ns = receive_timestamp_ns - msg.timestamp_ns
                latency_ms = latency_ns / 1_000_000.0

                try:
                    # Core stats (already present in your dds_data_structure.py)
                    latest_dog_status["battery_percent"] = float(msg.battery_percent)
                    latest_dog_status["cpu_usage_percent"] = float(msg.cpu_usage_percent)
                    latest_dog_status["gpu_usage_percent"] = float(msg.gpu_usage_percent)
                    latest_dog_status["memory_usage_percent"] = float(msg.memory_usage_percent)
                    latest_dog_status["latency_ms"] = latency_ms

                    # Robot Status - Assuming these fields exist in the actual message
                    latest_dog_status["robot_mode_form"] = get_nested_attr(msg, ['robot_mode_form'], "N/A")
                    latest_dog_status["robot_mode_name"] = get_nested_attr(msg, ['robot_mode_name'], "N/A")

                    # Jetson Temperatures
                    latest_dog_status["temp_cpu"] = get_nested_attr(msg, ['temperatures', 'cpu'])
                    latest_dog_status["temp_gpu"] = get_nested_attr(msg, ['temperatures', 'gpu'])
                    latest_dog_status["temp_tj"] = get_nested_attr(msg, ['temperatures', 'tj'])
                    latest_dog_status["temp_soc0"] = get_nested_attr(msg, ['temperatures', 'soc0'])
                    latest_dog_status["temp_soc1"] = get_nested_attr(msg, ['temperatures', 'soc1'])
                    latest_dog_status["temp_soc2"] = get_nested_attr(msg, ['temperatures', 'soc2'])
                    latest_dog_status["temp_cv0"] = get_nested_attr(msg, ['temperatures', 'cv0'])
                    latest_dog_status["temp_cv1"] = get_nested_attr(msg, ['temperatures', 'cv1'])
                    latest_dog_status["temp_cv2"] = get_nested_attr(msg, ['temperatures', 'cv2'])

                    # Jetson Power Consumption
                    latest_dog_status["power_cpu_gpu_cv"] = get_nested_attr(msg, ['power', 'cpu_gpu_cv'])
                    latest_dog_status["power_soc"] = get_nested_attr(msg, ['power', 'soc'])
                    latest_dog_status["power_nv_power_total"] = get_nested_attr(msg, ['power', 'nv_power_total'])
                    latest_dog_status["power_vdd_inn"] = get_nested_attr(msg, ['power', 'vdd_inn'])

                    # Jetson Hardware Stats
                    latest_dog_status["hardware_uptime_seconds"] = get_nested_attr(msg, ['hardware', 'uptime_seconds'])
                    latest_dog_status["hardware_jetson_clocks_on"] = get_nested_attr(msg, ['hardware', 'jetson_clocks_on'], False)
                    latest_dog_status["hardware_fan_speed_percent"] = get_nested_attr(msg, ['hardware', 'fan_speed_percent'])
                    latest_dog_status["hardware_emc_usage_percent"] = get_nested_attr(msg, ['hardware', 'emc_usage_percent'])
                    latest_dog_status["hardware_disk_usage_percent"] = get_nested_attr(msg, ['hardware', 'disk_usage_percent'])

                    # Repackage the unrolled motor fields into a list for the website
                    motors_list = []
                    for i in range(12):
                        reserve0 = getattr(msg, f'm{i}_reserve0', 0)
                        motor_data = {
                            'mode': getattr(msg, f'm{i}_mode', 0),
                            'q': getattr(msg, f'm{i}_q', 0.0),
                            'dq': getattr(msg, f'm{i}_dq', 0.0),
                            'ddq': getattr(msg, f'm{i}_ddq', 0.0),
                            'tau_est': getattr(msg, f'm{i}_tau_est', 0.0),
                            'temperature': getattr(msg, f'm{i}_temperature', 0),
                            'lost': getattr(msg, f'm{i}_lost', 0),
                            'reserve0': reserve0,
                            'reserve1': getattr(msg, f'm{i}_reserve1', 0),
                            'error_str': decode_motor_errors(reserve0) # Add the decoded error string
                        }
                        motors_list.append(motor_data)
                    latest_dog_status['motors'] = motors_list
                    # --- End of repackaging ---

                    latest_dog_status["status_message"] = "Data received successfully."
                    latest_dog_status["data_received"] = True

                except Exception as attr_e:
                    # This catches errors if the 'msg' object does not have the expected attributes
                    # despite being a DogStatus instance.
                    latest_dog_status["status_message"] = f"DDS Data Format Error: {attr_e}. Check DogStatus definition."
                    latest_dog_status["data_received"] = False # Indicate a data format issue
                    print(f"DDS Data Format Error: {attr_e}")

                # Emit the updated data to all connected WebSocket clients
                socketio.emit('dog_status_update', latest_dog_status)
                # print(f"Emitted DogStatus update: {latest_dog_status}") # Keep commented for cleaner console
            else:
                # No message received within the timeout
                if not latest_dog_status["data_received"]:
                    latest_dog_status["status_message"] = "Waiting for data from robot... (No DDS messages detected yet)"
                else:
                    latest_dog_status["status_message"] = "No new data in last cycle."
                latest_dog_status["data_received"] = False # Revert data_received flag if no new data
                socketio.emit('dog_status_update', latest_dog_status)
                time.sleep(0.1) # Brief sleep to avoid busy-waiting if no message

    except Exception as e:
        print(f"DDS subscriber thread error during read loop: {e}")
        latest_dog_status["status_message"] = f"Critical DDS Stream Error: {e}"
        latest_dog_status["data_received"] = False
        socketio.emit('dog_status_update', latest_dog_status)
    finally:
        if sub and sub.is_initialized():
            sub.Close()
            print("DDS subscriber channel closed.")
        print("DDS subscriber thread stopped.")


@app.route('/')
def index():
    """
    Renders the main HTML page for displaying dog status.
    """
    return render_template('index.html')

@socketio.on('connect')
def test_connect():
    """
    Handles new WebSocket connections. Sends the current status on connect.
    """
    print('Client connected')
    emit('dog_status_update', latest_dog_status) # Send current status to newly connected client

@socketio.on('disconnect')
def test_disconnect():
    """
    Handles WebSocket disconnections.
    """
    print('Client disconnected')

if __name__ == '__main__':
    # Start the DDS subscriber in a separate thread
    subscriber_thread = threading.Thread(target=dds_subscriber_thread, daemon=True)
    subscriber_thread.start()

    # Run the Flask-SocketIO app
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True, port=5000)
