# status_receive.py (Corrected Version 2)

import time
import os
import sys
import threading
import queue 

# --- FIX FOR CROSS-DIRECTORY IMPORT ---
current_script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_script_dir)
communication_dir_path = os.path.join(parent_dir, 'communication')
sys.path.append(communication_dir_path)
# --- END OF FIX ---

from dds_data_structure import DogStatus

# --- CORRECTED: Add the missing import for ChannelFactoryInitialize ---
from unitree_sdk2py.core.channel import ChannelSubscriber, ChannelFactoryInitialize

DOG_STATUS_TOPIC = "DogStatus"
DDS_NETWORK_INTERFACE = "enP8p1s0"

stop_thread_flag = threading.Event()
message_queue = queue.Queue()

def dds_reader_thread_function(subscriber_channel):
    """Function to be run in a separate thread to handle DDS message reading."""
    print("[DDS Reader Thread] Starting...")
    while not stop_thread_flag.is_set():
        try:
            msg = subscriber_channel.Read(1000)
            if msg is not None:
                message_queue.put(msg)
        except Exception as e:
            print(f"[DDS Reader Thread ERROR] An error occurred during read: {e}")
            break
    print("[DDS Reader Thread] Exiting.")

if __name__ == "__main__":
    print("Subscriber (Main Thread) starting...")
    dds_reader_thread = None
    sub = None # Initialize to None for the finally block

    try:
        ChannelFactoryInitialize(networkInterface=DDS_NETWORK_INTERFACE)

        sub = ChannelSubscriber(DOG_STATUS_TOPIC, DogStatus)
        sub.Init()

        dds_reader_thread = threading.Thread(target=dds_reader_thread_function, args=(sub,))
        dds_reader_thread.daemon = True
        dds_reader_thread.start()

        print(f"Listening for data on topic: '{DOG_STATUS_TOPIC}'...")
        print("Run the main_dog_status.py script in another terminal to see messages.")
        print("Press Ctrl+C to stop.")

        while True:
            try:
                msg = message_queue.get(timeout=0.1)
                receive_timestamp_ns = time.time_ns()
                latency_ns = receive_timestamp_ns - msg.timestamp_ns
                latency_ms = latency_ns / 1_000_000.0

                print("\033[H\033[J", end="")
                print("--- Unified Dog Status Receiver ---")
                print(f"Last Update: {time.strftime('%H:%M:%S')} | Network Latency: {latency_ms:.2f} ms")
                print("\n--- Robot Status ---")
                print(f"  - Mode (Form/Name): '{msg.robot_mode_form}' / '{msg.robot_mode_name}'")
                print(f"  - Battery: {msg.battery_percent:.1f}%")
                print("\n--- Jetson Primary Usage ---")
                print(f"  - CPU Usage: {msg.cpu_usage_percent:.1f}%")
                print(f"  - GPU Usage: {msg.gpu_usage_percent:.1f}%")
                print(f"  - RAM Usage: {msg.memory_usage_percent:.1f}%")
                print("\n--- Jetson Temperatures (°C) ---")
                print(f"  - CPU (TJ): {msg.temperatures.cpu:<5.1f} | GPU: {msg.temperatures.gpu:<5.1f} | Other CPU: {msg.temperatures.tj:<5.1f}")
                print(f"  - SOC: [{msg.temperatures.soc0}, {msg.temperatures.soc1}, {msg.temperatures.soc2}]")
                print(f"  - CV : [{msg.temperatures.cv0}, {msg.temperatures.cv1}, {msg.temperatures.cv2}]")
                print("\n--- Jetson Power Consumption (mW) ---")
                print(f"  - CPU/GPU/CV: {msg.power.cpu_gpu_cv:<7.0f} | SOC: {msg.power.soc:<7.0f}")
                print(f"  - Total (NV): {msg.power.nv_power_total:<7.0f} | VDD_INN: {msg.power.vdd_inn:<7.0f}")
                print("\n--- Jetson Hardware Stats ---")
                uptime_min = msg.hardware.uptime_seconds / 60
                print(f"  - Uptime: {uptime_min:.1f} mins | Jetson Clocks: {'ON' if msg.hardware.jetson_clocks_on else 'OFF'}")
                print(f"  - Fan Speed: {msg.hardware.fan_speed_percent:.1f}% | EMC Usage: {msg.hardware.emc_usage_percent:.1f}% | Disk Usage: {msg.hardware.disk_usage_percent:.1f}%")
                print("\n(Press Ctrl+C to stop)")

            except queue.Empty:
                pass

    except KeyboardInterrupt:
        print("\n[Ctrl+C Detected] Subscriber (Main Thread) stopping...")
    except Exception as e:
        print(f"An unexpected error occurred in main thread: {e}")
    finally:
        print("Finalizing subscriber shutdown...")
        stop_thread_flag.set()
        
        if dds_reader_thread and dds_reader_thread.is_alive():
            dds_reader_thread.join(timeout=1.5)
            if dds_reader_thread.is_alive():
                print("[Warning] DDS reader thread did not terminate cleanly.")
        
        if sub: # Simply check if 'sub' was assigned
            sub.Close()
            print("Subscriber channel closed successfully.")
        else:
            print("Subscriber channel was not initialized or already closed.")
        print("Shutdown complete.")