# jetson_power_client.py
import sys
import os
import time
import uuid # For generating unique command IDs

# Adjust the path to where your dds_data_structure.py is located
# Assuming it's in a 'communication' directory one level up from this script
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
    from unitree_sdk2py.core.channel import ChannelPublisher, ChannelFactoryInitialize
except ImportError as e:
    print(f"Error: Could not import Unitree SDK components. Please ensure 'unitree_sdk2py' "
          f"is installed and accessible in your Python environment.")
    print(f"ImportError details: {e}")
    sys.exit(1)

# DDS Configuration
POWER_CONTROL_TOPIC = "PowerControl"
DDS_NETWORK_INTERFACE = "enP8p1s0" # Use the same interface as your robot

def run_client():
    publisher = None
    try:
        print(f"Initializing DDS factory on network interface: {DDS_NETWORK_INTERFACE}")
        ChannelFactoryInitialize(networkInterface=DDS_NETWORK_INTERFACE)
        
        publisher = ChannelPublisher(POWER_CONTROL_TOPIC, PowerControl)
        publisher.Init()
        print(f"DDS Publisher for '{POWER_CONTROL_TOPIC}' initialized.")

    except Exception as e:
        print(f"FATAL: DDS initialization failed: {e}. The client cannot start.")
        sys.exit(1)

    print("DDS Client for Jetson Power Management")
    print("-------------------------------------")
    print("Commands: 'shutdown', 'reboot', 'quit'")

    try:
        while True:
            command_input = input("\nEnter command: ").strip().lower()
            command_type = 0 # 0=No_Op, 1=Shutdown, 2=Reboot

            if command_input == "quit":
                print("Exiting client.")
                break
            elif command_input == "shutdown":
                command_type = 1
            elif command_input == "reboot":
                command_type = 2
            else:
                print("Invalid command. Please use 'shutdown', 'reboot', or 'quit'.")
                continue

            confirm = input(f"Are you sure you want to {command_input} the Jetson? (yes/no): ").strip().lower()
            if confirm == "yes":
                power_command_msg = PowerControl()
                power_command_msg.command_type = command_type
                power_command_msg.command_id = uuid.uuid4().int & (2**31 - 1) # Unique ID for each command
                power_command_msg.message = f"Request to {command_input}."

                try:
                    publisher.Write(power_command_msg)
                    print(f"Published PowerControl command '{command_input}' with ID {power_command_msg.command_id} to DDS topic '{POWER_CONTROL_TOPIC}'.")
                    time.sleep(1) # Give some time for transmission
                except Exception as e:
                    print(f"Error publishing to DDS: {e}")
            else:
                print(f"{command_input.capitalize()} cancelled.")

    except KeyboardInterrupt:
        print("\nClient interrupted.")
    finally:
        if publisher:
            # Check if publisher is initialized before closing
            if hasattr(publisher, 'is_initialized') and publisher.is_initialized():
                publisher.Close()
            else:
                print("Publisher was not initialized or already closed.")
        print("DDS Client cleanup complete.")

if __name__ == "__main__":
    run_client()