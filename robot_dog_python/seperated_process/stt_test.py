# stt_test_0.py (Corrected Subscriber-Only Version)
import sys
import os
import time
import asyncio
import traceback
import netifaces

# --- Imports (keep as is) ---
current_script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_script_dir)
communication_dir_path = os.path.join(parent_dir, 'communication')
sys.path.append(communication_dir_path)

from dds_data_structure import Utterance # Make sure this path is correct
from unitree_sdk2py.core.channel import ChannelSubscriber, ChannelFactoryInitialize

def get_preferred_interface():
    # This function is fine, keep it
    interfaces = netifaces.interfaces()
    preferred_order = ['enP8p1s0', 'eth0', 'wlan0', 'enp8s0', 'en0', 'lo']
    for iface in preferred_order:
        if iface in interfaces:
            print(f"✅ Selected interface: {iface}")
            return iface
    return "enP8p1s0"

def dds_callback(data: Utterance):
    """Callback to process received speech results."""
    result_type = "FINAL" if data.definite else "INTERIM"
    print(f"DDS RECEIVED -> [{result_type}]: {data.text}")

async def main():
    """Main async function for the subscriber."""
    print("🔥 Starting DDS Subscriber...")
    
    interface = get_preferred_interface()
    
    try:
        ChannelFactoryInitialize(networkInterface=interface)
        print("✅ DDS Initialized Successfully")
    except Exception as e:
        print(f"⚠️ DDS Initialization Failed: {e}")
        return
    
    try:
        sub = ChannelSubscriber("SpeechRecognitionResult", Utterance)
        sub.Init(dds_callback)
        print("✅ DDS Subscriber Initialized. Waiting for messages...")
    except Exception as e:
        print(f"⚠️ Subscriber Initialization Failed: {e}")
        return
    
    # Keep the script alive to listen for messages
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Subscriber stopped by user.")
    finally:
        print("✅ Test complete.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"⚠️ Program terminated unexpectedly: {e}")