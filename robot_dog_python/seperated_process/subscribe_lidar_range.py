# subscribe_lidar_range.py

import time
import sys
import os

# --- Imports from unitree_sdk2py ---
# This follows the pattern from your main_dog_status.py file.
try:
    from unitree_sdk2py.idl.sensor_msgs.msg.dds_ import PointCloud2_
    from unitree_sdk2py.core.channel import ChannelSubscriber, ChannelFactoryInitialize
except ImportError:
    print("Error: Could not import unitree_sdk2py modules.")
    print("Please ensure the unitree_sdk2py library is installed and accessible.")
    sys.exit(1)
def handle_point_cloud(msg):
    print("Received PointCloud2 message:")

def main():
    """
    Initializes DDS and subscribes to the LiDAR's simple obstacle distance topic.
    """
    # --- Configuration ---
    # The network interface the robot uses for DDS communication.
    DDS_NETWORK_INTERFACE = "enP8p1s0"
    # The DDS topic for simple obstacle distance, from the LiDAR documentation.
    TOPIC_RANGE_INFO = "rt/utlidar/cloud"

    subscriber = None
    try:
        # Initialize the DDS communication channel
        print(f"Initializing DDS on network interface: {DDS_NETWORK_INTERFACE}...")
        ChannelFactoryInitialize(0,networkInterface=DDS_NETWORK_INTERFACE)

        # Create a subscriber for the LiDAR range info topic
        subscriber = ChannelSubscriber(TOPIC_RANGE_INFO, PointCloud2_)
        subscriber.Init(handler=handle_point_cloud)
        print(f"Successfully subscribed to DDS topic: '{TOPIC_RANGE_INFO}'")
        print("Waiting for LiDAR range data... Press Ctrl+C to stop.")

        # Main loop to continuously read and process data
        while True:
            # Read data from the topic with a 200ms timeout
            # msg = subscriber.Read(200)

            # if msg is not None:
            #     # The 'point' attribute holds the distance data.
            #     # As per the documentation:
            #     # x -> front distance
            #     # y -> left distance
            #     # z -> right distance
            #     print(f"Received LiDAR range data:")

            # else:
            #     # This message appears if no data is received within the timeout
            #     print("No new LiDAR range data received. Waiting...")
            
            # Polling interval
            time.sleep(5)

    except KeyboardInterrupt:
        print("\nMonitoring stopped by user.")
    except Exception as e:
        import traceback
        print(f"\nAn unexpected error occurred: {e}")
        traceback.print_exc()
    finally:
        # Ensure the subscriber is closed properly on exit
        if subscriber:
            subscriber.Close()
        print("DDS subscriber closed. Shutdown complete.")


if __name__ == "__main__":
    main()