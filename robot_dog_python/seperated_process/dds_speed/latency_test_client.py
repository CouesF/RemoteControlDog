# latency_test_client.py (FIXED)
# This script sends large data packets and measures the Round-Trip Time (RTT).
# It now correctly constructs the Go2FrontVideoData_ message using positional arguments.

import time
import os
import sys
import threading
import struct
from unitree_sdk2py.core.channel import ChannelPublisher, ChannelSubscriber, ChannelFactoryInitialize
# Import both the main message type and the required 'TimeSpec_' for its timestamp field.
from unitree_sdk2py.idl.unitree_go.msg.dds_ import Go2FrontVideoData_, TimeSpec_

# --- Test Configuration ---
PAYLOAD_SIZE = 500 * 1024  # 500 KB
FREQUENCY_HZ = 20.0
TEST_DURATION_S = 30
DDS_NETWORK_INTERFACE = "enP8p1s0"
REQUEST_TOPIC = "LatencyRequest"
REPLY_TOPIC = "LatencyReply"

# --- Global variables for statistics ---
latency_stats = {
    "rtt": [], "forward_latency": [], "return_latency": [],
    "packets_sent": 0, "packets_received": 0, "timeouts": 0
}
stop_event = threading.Event()

def subscriber_thread_func(sub):
    """
    This thread function continuously reads replies from the server.
    """
    print("Subscriber thread started, waiting for replies...")
    while not stop_event.is_set():
        try:
            msg = sub.Read(200) # Wait for max 200ms
            if msg is not None:
                client_receive_ts = time.time_ns()
                latency_stats["packets_received"] += 1

                # Unpack timestamps from the 'video720p' field where we stored them.
                client_send_ts, server_receive_ts = struct.unpack_from('>QQ', msg.video720p)
                
                rtt_ms = (client_receive_ts - client_send_ts) / 1_000_000.0
                forward_latency_ms = (server_receive_ts - client_send_ts) / 1_000_000.0
                return_latency_ms = (client_receive_ts - server_receive_ts) / 1_000_000.0

                latency_stats["rtt"].append(rtt_ms)
                latency_stats["forward_latency"].append(forward_latency_ms)
                latency_stats["return_latency"].append(return_latency_ms)

                print(f"Reply: RTT={rtt_ms:.2f}ms | Fwd={forward_latency_ms:.2f}ms | Ret={return_latency_ms:.2f}ms")
            else:
                latency_stats["timeouts"] += 1
        except struct.error as e:
            print(f"Error unpacking timestamps: {e}. Malformed packet received.")
        except Exception as e:
            print(f"Subscriber thread error: {e}")
            break
    print("Subscriber thread stopped.")

def main():
    pub = None
    sub = None
    try:
        print("Initializing DDS Client...")
        ChannelFactoryInitialize(networkInterface=DDS_NETWORK_INTERFACE)
        pub = ChannelPublisher(REQUEST_TOPIC, Go2FrontVideoData_)
        pub.Init()
        sub = ChannelSubscriber(REPLY_TOPIC, Go2FrontVideoData_)
        sub.Init()

        sub_thread = threading.Thread(target=subscriber_thread_func, args=(sub,), daemon=True)
        sub_thread.start()

        print(f"Starting test: Sending {PAYLOAD_SIZE / 1024} KB packets at {FREQUENCY_HZ} Hz for {TEST_DURATION_S} seconds...")
        print("Press Ctrl+C to stop the test early.")
        
        time_spec = TimeSpec_(sec=0, nanosec=0)

        start_time = time.time()
        while time.time() - start_time < TEST_DURATION_S and not stop_event.is_set():
            loop_start_time = time.time()

            payload = bytearray(PAYLOAD_SIZE)
            client_send_ts = time.time_ns()
            struct.pack_into('>Q', payload, 0, client_send_ts)
            
            # **THE FIX**: Call the constructor with positional arguments, not keyword arguments.
            msg_to_send = Go2FrontVideoData_(
                time_spec,      # 1st argument: time_frame
                payload,        # 2nd argument: video720p
                b'',            # 3rd argument: video360p
                b''             # 4th argument: video180p
            )
            pub.Write(msg_to_send)
            latency_stats["packets_sent"] += 1

            elapsed_time = time.time() - loop_start_time
            sleep_duration = (1.0 / FREQUENCY_HZ) - elapsed_time
            if sleep_duration > 0:
                time.sleep(sleep_duration)

    except KeyboardInterrupt:
        print("\nTest interrupted by user. Shutting down...")
    except Exception as e:
        print(f"A critical error occurred in the main loop: {e}")
    finally:
        stop_event.set()
        if 'sub_thread' in locals() and sub_thread.is_alive():
            sub_thread.join(timeout=1.0)

        print("\n--- Test Complete ---")
        print(f"Packets Sent: {latency_stats['packets_sent']}")
        print(f"Packets Received: {latency_stats['packets_received']}")
        print(f"Packets Timed Out / Dropped: {latency_stats['timeouts']}")
        
        if latency_stats["rtt"]:
            avg_rtt = sum(latency_stats["rtt"]) / len(latency_stats["rtt"])
            max_rtt = max(latency_stats["rtt"])
            min_rtt = min(latency_stats["rtt"])
            print(f"\nRTT (ms): Avg={avg_rtt:.2f}, Max={max_rtt:.2f}, Min={min_rtt:.2f}")

        if latency_stats["forward_latency"]:
            avg_fwd = sum(latency_stats["forward_latency"]) / len(latency_stats["forward_latency"])
            max_fwd = max(latency_stats["forward_latency"])
            min_fwd = min(latency_stats["forward_latency"])
            print(f"Forward Latency (ms): Avg={avg_fwd:.2f}, Max={max_fwd:.2f}, Min={min_fwd:.2f}")
        
        if latency_stats["return_latency"]:
            avg_ret = sum(latency_stats["return_latency"]) / len(latency_stats["return_latency"])
            max_ret = max(latency_stats["return_latency"])
            min_ret = min(latency_stats["return_latency"])
            print(f"Return Latency (ms): Avg={avg_ret:.2f}, Max={max_ret:.2f}, Min={min_ret:.2f}")

        print("\nClosing DDS channels...")
        if pub: pub.Close()
        if sub: sub.Close()
        print("Shutdown complete.")

if __name__ == "__main__":
    main()
