# jetson_power_server.py
import os
import sys
import time
import threading

# Adjust the path to where your dds_data_structure.py is located
current_script_dir = os.path.dirname(os.path.abspath(__file__))
communication_dir_path = os.path.join(os.path.dirname(current_script_dir), 'communication')
if communication_dir_path not in sys.path:
    sys.path.append(communication_dir_path)

try:
    from dds_data_structure import PowerControl
except ImportError as e:
    print(f"Error: Could not import PowerControl from dds_data_structure. "
          f"Please ensure 'dds_data_structure.py' is located at '{communication_dir_path}' "
          f"and contains the PowerControl dataclass.")
    print(f"ImportError details: {e}")
    sys.exit(1)

try:
    from unitree_sdk2py.core.channel import ChannelSubscriber, ChannelFactoryInitialize
except ImportError as e:
    print(f"Error: Could not import Unitree SDK components. Please ensure 'unitree_sdk2py' "
          f"is installed and accessible in your Python environment.")
    print(f"ImportError details: {e}")
    sys.exit(1)

# DDS Configuration
POWER_CONTROL_TOPIC = "PowerControl"
DDS_NETWORK_INTERFACE = "enP8p1s0" # Use the same interface as your robot

# Use a lock to ensure only one power command is processed at a time
command_lock = threading.Lock()
# Store the last processed command ID to avoid re-executing duplicate commands
last_processed_command_id = None

def shutdown_jetson():
    """
    Shuts down the Jetson board.
    Requires superuser privileges to execute.
    """
    print("Executing shutdown command...")
    # It's crucial to run this with sudo. The script itself might need to be run with sudo
    # or the user needs specific sudoers configuration for these commands without password.
    os.system("sudo shutdown -h now")
    print("Shutdown command issued. The system should power off shortly.")

def reboot_jetson():
    """
    Reboots the Jetson board.
    Requires superuser privileges to execute.
    """
    print("Executing reboot command...")
    # Same sudo considerations as shutdown.
    os.system("sudo reboot")
    print("Reboot command issued. The system should restart shortly.")

def process_power_command(command_msg: PowerControl):
    global last_processed_command_id

    with command_lock:
        if command_msg.command_id == last_processed_command_id:
            print(f"Ignoring duplicate command ID: {command_msg.command_id}")
            return

        print(f"\nReceived PowerControl command via DDS (ID: {command_msg.command_id}):")
        print(f"  Type: {command_msg.command_type}")
        print(f"  Message: {command_msg.message}")

        if command_msg.command_type == 1: # Shutdown
            print("Received shutdown command. Initiating shutdown process.")
            shutdown_jetson()
            last_processed_command_id = command_msg.command_id
            sys.exit(0) # Exit the script after issuing command
        elif command_msg.command_type == 2: # Reboot
            print("Received reboot command. Initiating reboot process.")
            reboot_jetson()
            last_processed_command_id = command_msg.command_id
            sys.exit(0) # Exit the script after issuing command
        else:
            print(f"Unknown PowerControl command type: {command_msg.command_type}. Ignoring.")
        
        last_processed_command_id = command_msg.command_id # Update after processing

def run_server():
    subscriber = None
    try:
        print(f"Initializing DDS factory on network interface: {DDS_NETWORK_INTERFACE}")
        ChannelFactoryInitialize(networkInterface=DDS_NETWORK_INTERFACE)
        
        subscriber = ChannelSubscriber(POWER_CONTROL_TOPIC, PowerControl)
        subscriber.Init()
        print(f"DDS Subscriber for '{POWER_CONTROL_TOPIC}' initialized.")

    except Exception as e:
        print(f"FATAL: DDS initialization failed: {e}. The server cannot start.")
        sys.exit(1)

    print("DDS Server for Jetson Power Management is running...")
    print("Waiting for PowerControl commands ('shutdown', 'reboot')...")
    print("-------------------------------------------------")

    try:
        while True:
            # Read with a timeout to allow for graceful shutdown if no messages are coming
            msg = subscriber.Read(100) # Timeout in milliseconds
            if msg:
                # Process command in a separate thread if execution takes long,
                # but for shutdown/reboot, it's usually fine to do directly.
                # Here, we directly call the processing function.
                process_power_command(msg)
            
            time.sleep(0.1) # Small delay to prevent busy-waiting

    except KeyboardInterrupt:
        print("\nServer interrupted by user.")
    except Exception as e:
        import traceback
        print(f"An unexpected error occurred in server: {e}")
        traceback.print_exc()
    finally:
        if subscriber:
            # Check if subscriber is initialized before closing
            if hasattr(subscriber, 'is_initialized') and subscriber.is_initialized():
                subscriber.Close()
            else:
                print("Subscriber was not initialized or already closed.")
        print("DDS Server cleanup complete.")

if __name__ == "__main__":
    run_server()