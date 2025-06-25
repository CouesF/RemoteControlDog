# dds_latency_test_sender.py
"""
DDS Latency Test Sender - Sends large payloads at specified frequency
and measures transmission timing and round-trip latency.
"""
# ... (imports are the same as before, including 'struct') ...
import time
import sys
import os
import json
import threading
import statistics
from datetime import datetime
import hashlib
import struct

try:
    from dds_latency_test_structure import LargeTestPayload, LatencyTestResponse
    from unitree_sdk2py.core.channel import ChannelSubscriber, ChannelPublisher, ChannelFactoryInitialize
except ImportError as e:
    print(f"Import error: {e}")
    # ... (error message is the same) ...
    sys.exit(1)

class DDSLatencySender:
    # ... (__init__, initialize_dds, generate_test_data are the same) ...
    def __init__(self, network_interface="enP8p1s0", payload_size_kb=500, test_frequency_hz=20):
        self.network_interface = network_interface
        self.payload_size_kb = payload_size_kb
        self.test_frequency_hz = test_frequency_hz
        self.sender_id = f"sender_{int(time.time())}"
        self.test_session_id = int(time.time())
        
        # Calculate number of floats needed for target size
        target_bytes = payload_size_kb * 1024
        self.num_floats = target_bytes // 4  # 4 bytes per float
        
        # DDS components
        self.payload_publisher = None
        self.response_subscriber = None
        
        # Statistics tracking
        self.sequence_counter = 0
        self.send_times = {}  # sequence_id -> send_timestamp_ns
        self.transmission_times = []  # Time to send (publish)
        self.rtt_times = []  # Round-trip times
        self.responses_received = 0
        self.messages_sent = 0
        
        # Control flags
        self.running = False
        self.stats_lock = threading.Lock()
        
    def initialize_dds(self):
        """Initialize DDS publisher and subscriber"""
        try:
            print(f"Initializing DDS on interface: {self.network_interface}")
            ChannelFactoryInitialize(networkInterface=self.network_interface)
            
            # Publisher for sending large payloads
            self.payload_publisher = ChannelPublisher("LargeTestPayload", LargeTestPayload)
            self.payload_publisher.Init()
            
            # Subscriber for receiving responses (RTT measurement)
            self.response_subscriber = ChannelSubscriber("LatencyTestResponse", LatencyTestResponse)
            self.response_subscriber.Init()
            
            print("DDS initialization successful")
            return True
            
        except Exception as e:
            print(f"DDS initialization failed: {e}")
            return False
    
    def generate_test_data(self):
        """Generate test data with known pattern for integrity checking"""
        base_pattern = [float(i % 1000) for i in range(min(1000, self.num_floats))]
        full_data = []
        while len(full_data) < self.num_floats:
            remaining = self.num_floats - len(full_data)
            full_data.extend(base_pattern[:remaining])
        
        return full_data

    def calculate_checksum(self, data: bytes):
        """Calculate simple checksum for a bytes object."""
        return int(hashlib.md5(data).hexdigest()[:8], 16)
    
    def send_test_message(self):
        """Send a single test message and measure transmission time"""
        # Create payload with default values for its explicit types
        payload = LargeTestPayload(
            sequence_id=0, test_session_id=0, sender_id="", send_timestamp_ns=0,
            test_frequency_hz=0.0, payload_size_bytes=0, checksum=0, large_data=[]
        )

        payload.sequence_id = self.sequence_counter
        payload.test_session_id = self.test_session_id
        payload.sender_id = self.sender_id
        payload.test_frequency_hz = self.test_frequency_hz
        payload.payload_size_bytes = self.num_floats * 4
        
        test_data_floats = self.generate_test_data()
        
        try:
            test_data_bytes = struct.pack(f'>{self.num_floats}f', *test_data_floats)
        except struct.error as e:
            print(f"Struct packing error: {e}")
            return False

        # Calculate checksum on the bytes object
        payload.checksum = self.calculate_checksum(test_data_bytes)
        
        # CHANGED: Convert the 'bytes' object to a list of integers (0-255)
        # for the 'types.sequence[types.uint8]' field.
        payload.large_data = list(test_data_bytes)

        # ... (rest of the function is the same) ...
        pre_send_time = time.time_ns()
        payload.send_timestamp_ns = pre_send_time
        
        try:
            self.payload_publisher.Write(payload)
            post_send_time = time.time_ns()
            
            transmission_time_ns = post_send_time - pre_send_time
            transmission_time_ms = transmission_time_ns / 1_000_000.0
            
            with self.stats_lock:
                self.send_times[self.sequence_counter] = pre_send_time
                self.transmission_times.append(transmission_time_ms)
                self.messages_sent += 1
            
            print(f"Sent message {self.sequence_counter:4d} | "
                  f"Payload: {self.payload_size_kb}KB | "
                  f"Tx Time: {transmission_time_ms:.3f}ms")
            
            self.sequence_counter += 1
            return True
            
        except Exception as e:
            print(f"Failed to send message {self.sequence_counter}: {e}")
            return False
            
    # ... (rest of the class is unchanged) ...
    def response_listener_thread(self):
        """Thread to listen for response messages and calculate RTT"""
        print("Starting response listener thread...")
        
        while self.running:
            try:
                response = self.response_subscriber.Read(100)  # 100ms timeout
                
                if response is not None:
                    receive_time = time.time_ns()
                    
                    # Calculate RTT
                    original_seq_id = response.original_sequence_id
                    if original_seq_id in self.send_times:
                        original_send_time = self.send_times[original_seq_id]
                        rtt_ns = receive_time - original_send_time
                        rtt_ms = rtt_ns / 1_000_000.0
                        
                        # Calculate one-way latencies
                        forward_latency_ns = response.receive_timestamp_ns - response.original_send_timestamp_ns
                        return_latency_ns = receive_time - response.response_send_timestamp_ns
                        forward_latency_ms = forward_latency_ns / 1_000_000.0
                        return_latency_ms = return_latency_ns / 1_000_000.0
                        
                        with self.stats_lock:
                            self.rtt_times.append(rtt_ms)
                            self.responses_received += 1
                            # Clean up old send times to prevent memory leak
                            if original_seq_id in self.send_times:
                                del self.send_times[original_seq_id]
                        
                        print(f"RTT for seq {original_seq_id:4d}: {rtt_ms:.3f}ms | "
                              f"Forward: {forward_latency_ms:.3f}ms | "
                              f"Return: {return_latency_ms:.3f}ms")
                        
            except Exception as e:
                if self.running:  # Only print errors if we're supposed to be running
                    print(f"Response listener error: {e}")
                    time.sleep(0.1)
    
    def run_test(self, duration_seconds=60):
        """Run the latency test for specified duration"""
        print(f"\n=== DDS Latency Test ===")
        print(f"Payload Size: {self.payload_size_kb}KB ({self.num_floats} floats)")
        print(f"Frequency: {self.test_frequency_hz}Hz")
        print(f"Duration: {duration_seconds}s")
        print(f"Network Interface: {self.network_interface}")
        print(f"Expected messages: {duration_seconds * self.test_frequency_hz}")
        print("=" * 50)
        
        if not self.initialize_dds():
            return
        
        self.running = True
        
        # Start response listener thread
        response_thread = threading.Thread(target=self.response_listener_thread, daemon=True)
        response_thread.start()
        
        # Calculate sleep time for target frequency
        sleep_time = 1.0 / self.test_frequency_hz
        
        start_time = time.time()
        end_time = start_time + duration_seconds
        last_stats_time = start_time
        
        try:
            while time.time() < end_time and self.running:
                loop_start = time.time()
                
                # Send test message
                self.send_test_message()
                
                # Print periodic statistics
                current_time = time.time()
                if current_time - last_stats_time >= 5.0:  # Every 5 seconds
                    self.print_interim_stats()
                    last_stats_time = current_time
                
                # Sleep to maintain frequency
                elapsed = time.time() - loop_start
                sleep_remaining = sleep_time - elapsed
                if sleep_remaining > 0:
                    time.sleep(sleep_remaining)
                
        except KeyboardInterrupt:
            print("\nTest interrupted by user")
        finally:
            self.running = False
            
        # Wait a bit for final responses
        print("Waiting for final responses...")
        time.sleep(2.0)
        
        # Print final statistics
        self.print_final_stats()
        
        # Cleanup
        if self.payload_publisher:
            self.payload_publisher.Close()
        if self.response_subscriber:
            self.response_subscriber.Close()
    
    def print_interim_stats(self):
        """Print interim statistics during test"""
        with self.stats_lock:
            if self.transmission_times and self.rtt_times:
                avg_tx_time = statistics.mean(self.transmission_times)
                avg_rtt = statistics.mean(self.rtt_times)
                response_rate = (self.responses_received / self.messages_sent * 100) if self.messages_sent > 0 else 0
                
                print(f"\n--- Interim Stats ---")
                print(f"Messages sent: {self.messages_sent}")
                print(f"Responses received: {self.responses_received} ({response_rate:.1f}%)")
                print(f"Avg transmission time: {avg_tx_time:.3f}ms")
                print(f"Avg RTT: {avg_rtt:.3f}ms")
                print("-" * 20)
    
    def print_final_stats(self):
        """Print comprehensive final statistics"""
        print(f"\n{'='*60}")
        print("FINAL TEST RESULTS")
        print(f"{'='*60}")
        
        with self.stats_lock:
            print(f"Test Configuration:")
            print(f"  Payload Size: {self.payload_size_kb}KB")
            print(f"  Target Frequency: {self.test_frequency_hz}Hz")
            print(f"  Messages Sent: {self.messages_sent}")
            print(f"  Responses Received: {self.responses_received}")
            
            if self.messages_sent > 0:
                response_rate = self.responses_received / self.messages_sent * 100
                print(f"  Response Rate: {response_rate:.1f}%")
            
            if self.transmission_times:
                print(f"\nTransmission Times (time to publish):")
                tx_avg = statistics.mean(self.transmission_times)
                tx_min = min(self.transmission_times)
                tx_max = max(self.transmission_times)
                tx_std = statistics.stdev(self.transmission_times) if len(self.transmission_times) > 1 else 0
                
                print(f"  Average: {tx_avg:.3f}ms")
                print(f"  Min: {tx_min:.3f}ms")
                print(f"  Max: {tx_max:.3f}ms")
                print(f"  Std Dev: {tx_std:.3f}ms")
                
                # Percentiles
                sorted_tx = sorted(self.transmission_times)
                p95_tx = sorted_tx[int(0.95 * len(sorted_tx))]
                p99_tx = sorted_tx[int(0.99 * len(sorted_tx))]
                print(f"  95th percentile: {p95_tx:.3f}ms")
                print(f"  99th percentile: {p99_tx:.3f}ms")
            
            if self.rtt_times:
                print(f"\nRound-Trip Times:")
                rtt_avg = statistics.mean(self.rtt_times)
                rtt_min = min(self.rtt_times)
                rtt_max = max(self.rtt_times)
                rtt_std = statistics.stdev(self.rtt_times) if len(self.rtt_times) > 1 else 0
                
                print(f"  Average: {rtt_avg:.3f}ms")
                print(f"  Min: {rtt_min:.3f}ms")
                print(f"  Max: {rtt_max:.3f}ms")
                print(f"  Std Dev: {rtt_std:.3f}ms")
                
                # Percentiles
                sorted_rtt = sorted(self.rtt_times)
                p95_rtt = sorted_rtt[int(0.95 * len(sorted_rtt))]
                p99_rtt = sorted_rtt[int(0.99 * len(sorted_rtt))]
                print(f"  95th percentile: {p95_rtt:.3f}ms")
                print(f"  99th percentile: {p99_rtt:.3f}ms")
        
        print(f"{'='*60}")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='DDS Latency Test Sender')
    parser.add_argument('--interface', default='enP8p1s0', help='DDS network interface')
    parser.add_argument('--size', type=int, default=500, help='Payload size in KB')
    parser.add_argument('--frequency', type=float, default=20.0, help='Test frequency in Hz')
    parser.add_argument('--duration', type=int, default=60, help='Test duration in seconds')
    
    args = parser.parse_args()
    
    # Create and run sender
    sender = DDSLatencySender(
        network_interface=args.interface,
        payload_size_kb=args.size,
        test_frequency_hz=args.frequency
    )
    
    sender.run_test(duration_seconds=args.duration)

if __name__ == "__main__":
    main()