# dds_diagnostic_tool.py

import time
import sys

# --- Safely import all necessary modules ---
try:
    from unitree_sdk2py.core.channel import ChannelSubscriber, ChannelFactoryInitialize
    # Import message types based on the library structure you found
    from unitree_sdk2py.idl.geometry_msgs.msg.dds_ import PointStamped_
    from unitree_sdk2py.idl.sensor_msgs.msg.dds_ import PointCloud2_
    from unitree_sdk2py.idl.unitree_go.msg.dds_ import LowState_
    # The HeightMap message is likely in the unitree_go package as per the docs
    from unitree_sdk2py.idl.unitree_go.msg.dds_ import HeightMap_

except ImportError as e:
    print(f"Fatal Error: Could not import a required message type: {e}")
    print("Please double-check the unitree_sdk2py library installation and structure.")
    sys.exit(1)


def check_subscription(topic_name, message_type, type_name_str):
    """
    Attempts to subscribe to a single topic and read one message.
    Returns True if data is received, False otherwise.
    """
    subscriber = None
    print(f"--- TESTING ---")
    print(f"Topic: '{topic_name}'")
    print(f"Type:  '{type_name_str}'")
    
    try:
        subscriber = ChannelSubscriber(topic_name, message_type)
        subscriber.Init()
        
        # Try to read data for a short period (e.g., 1 second)
        # A longer timeout gives the system more time to respond.
        msg = subscriber.Read(1000) 
        
        if msg is not None:
            print("✅ SUCCESS: Data received on this channel.")
            # Print header info to prove we got a real message
            if hasattr(msg, 'header'):
                 print(f"   -> Header Frame ID: '{msg.header.frame_id}'")
            return True
        else:
            print("❌ FAILED: No data received on this channel.")
            return False
            
    except Exception as e:
        print(f"🔥 ERROR: An exception occurred during the test: {e}")
        return False
    finally:
        if subscriber:
            subscriber.Close()
        print("-" * 15 + "\n")


def main():
    DDS_NETWORK_INTERFACE = "enP8p1s0"
    print("Starting DDS Diagnostic Tool...")
    print("This will test several topic/type combinations.\n")

    try:
        ChannelFactoryInitialize(networkInterface=DDS_NETWORK_INTERFACE)
    except Exception as e:
        print(f"🔥 CRITICAL ERROR: Failed to initialize DDS on interface '{DDS_NETWORK_INTERFACE}'.")
        print("Please ensure this is the correct network interface name for your device.")
        print(f"Error details: {e}")
        return

    # --- Define the list of tests ---
    # Each tuple is (topic_name, message_type_class, "string_name_for_printing")
    tests_to_run = [
        # BASELINE TEST: This should work if networking is correct.
        ("rt/lowstate", LowState_, "LowState_"),
        
        # LiDAR Simple Obstacle Distance Tests
        ("rt/utlidar/range_info", PointStamped_, "PointStamped_"),
        ("/utlidar/range_info", PointStamped_, "PointStamped_"), # ROS2 style name
        
        # LiDAR Point Cloud Tests
        ("rt/utlidar/cloud_deskewed", PointCloud2_, "PointCloud2_"),
        ("/utlidar/cloud_deskewed", PointCloud2_, "PointCloud2_"),
        
        # LiDAR Height Map Tests
        ("rt/utlidar/height_map_array", HeightMap_, "HeightMap_"),
        ("/utlidar/height_map_array", HeightMap_, "HeightMap_"),
    ]

    success_count = 0
    for topic, msg_type, type_str in tests_to_run:
        if check_subscription(topic, msg_type, type_str):
            success_count += 1
    
    print("--- DIAGNOSIS COMPLETE ---")
    if success_count == 0:
        print("RESULT: 🔴 No data was received on ANY channel.")
        print("This strongly suggests a fundamental network issue.")
        print(f"ACTION: Please verify that '{DDS_NETWORK_INTERFACE}' is the correct network interface name.")
    else:
        print(f"RESULT: 🟢 Successfully received data on {success_count} out of {len(tests_to_run)} channels.")
        print("This confirms your network settings are likely correct.")
        print("ACTION: Review the test results above to find the working LiDAR topic and type.")


if __name__ == "__main__":
    main()