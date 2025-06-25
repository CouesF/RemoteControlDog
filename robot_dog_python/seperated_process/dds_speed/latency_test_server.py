# latency_test_server.py (FIXED)
# This script listens for Go2FrontVideoData packets, adds a timestamp, and echoes them back.
# It now correctly constructs the reply message using positional arguments.

import time
import struct
from unitree_sdk2py.core.channel import ChannelPublisher, ChannelSubscriber, ChannelFactoryInitialize
# Import both the main message type and the required 'TimeSpec_' for its timestamp field.
from unitree_sdk2py.idl.unitree_go.msg.dds_ import Go2FrontVideoData_, TimeSpec_

# --- Test Configuration ---
DDS_NETWORK_INTERFACE = "enP8p1s0"
REQUEST_TOPIC = "LatencyRequest"
REPLY_TOPIC = "LatencyReply"

def main():
    sub = None
    pub = None
    try:
        print("Initializing DDS Echo Server...")
        ChannelFactoryInitialize(networkInterface=DDS_NETWORK_INTERFACE)
        sub = ChannelSubscriber(REQUEST_TOPIC, Go2FrontVideoData_)
        sub.Init()
        pub = ChannelPublisher(REPLY_TOPIC, Go2FrontVideoData_)
        pub.Init()

        print("Server started. Waiting for requests to echo...")
        print("Press Ctrl+C to stop.")

        while True:
            msg = sub.Read()
            if msg is not None:
                server_receive_ts = time.time_ns()
                
                reply_payload = bytearray(msg.video720p)
                struct.pack_into('>Q', reply_payload, 8, server_receive_ts)

                # **THE FIX**: Call the constructor with positional arguments, not keyword arguments.
                msg_to_reply = Go2FrontVideoData_(
                    msg.time_frame, # 1st argument: time_frame
                    reply_payload,  # 2nd argument: video720p
                    b'',            # 3rd argument: video360p
                    b''             # 4th argument: video180p
                )
                pub.Write(msg_to_reply)
                
    except KeyboardInterrupt:
        print("\nCtrl+C detected. Shutting down server gracefully...")
    except Exception as e:
        print(f"A critical error occurred: {e}")
    finally:
        print("Closing DDS channels...")
        if sub: sub.Close()
        if pub: pub.Close()
        print("Shutdown complete.")

if __name__ == "__main__":
    main()
