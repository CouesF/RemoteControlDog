# dds_latency_test_receiver.py
"""
DDS Latency Test Receiver - Receives large payloads and sends back responses
for round-trip latency measurement.
"""
# ... (imports are the same as before) ...
import time
import sys
import os
import threading
import statistics
from datetime import datetime
import hashlib

try:
    from dds_latency_test_structure import LargeTestPayload, LatencyTestResponse
    from unitree_sdk2py.core.channel import ChannelSubscriber, ChannelPublisher, ChannelFactoryInitialize
except ImportError as e:
    # ... (error message is the same) ...
    sys.exit(1)

    
class DDSLatencyReceiver:
    # ... (__init__ and initialize_dds are the same) ...
    def __init__(self, network_interface="enP8p1s0"):
        self.network_interface = network_interface
        self.receiver_id = f"receiver_{int(time.time())}"
        
        # DDS components
        self.payload_subscriber = None
        self.response_publisher = None
        
        # Statistics tracking
        self.messages_received = 0
        self.responses_sent = 0
        self.receive_times = []  # Time from send to receive
        self.processing_times = []  # Time to process and respond
        self.payload_sizes = []
        self.checksum_errors = 0
        
        # Control flags
        self.running = False
        self.stats_lock = threading.Lock()
        
        # Performance tracking
        self.last_sequence_id = -1
        self.lost_messages = 0
        self.out_of_order_messages = 0
        
    def initialize_dds(self):
        """Initialize DDS subscriber and publisher"""
        try:
            print(f"Initializing DDS on interface: {self.network_interface}")
            ChannelFactoryInitialize(networkInterface=self.network_interface)
            
            # Subscriber for receiving large payloads
            self.payload_subscriber = ChannelSubscriber("LargeTestPayload", LargeTestPayload)
            self.payload_subscriber.Init()
            
            # Publisher for sending responses
            self.response_publisher = ChannelPublisher("LatencyTestResponse", LatencyTestResponse)
            self.response_publisher.Init()
            
            print("DDS initialization successful")
            return True
            
        except Exception as e:
            print(f"DDS initialization failed: {e}")
            return False

    def calculate_checksum(self, data: bytes):
        """Calculate checksum for a bytes object."""
        return int(hashlib.md5(data).hexdigest()[:8], 16)
    
    def verify_data_integrity(self, payload):
        """Verify data integrity using checksum"""
        # CHANGED: Convert the received list of ints back to 'bytes' before checking.
        received_bytes = bytes(payload.large_data)
        calculated_checksum = self.calculate_checksum(received_bytes)
        return calculated_checksum == payload.checksum
    
    def process_received_payload(self, payload):
        """Process received payload and send response"""
        # ... (most of the function is the same) ...
        receive_timestamp = time.time_ns()
        processing_start = time.time_ns()
        
        if payload.send_timestamp_ns > 0:
            receive_latency_ns = receive_timestamp - payload.send_timestamp_ns
            receive_latency_ms = receive_latency_ns / 1_000_000.0
        else:
            receive_latency_ms = 0.0
        
        integrity_ok = self.verify_data_integrity(payload)
        if not integrity_ok:
            with self.stats_lock:
                self.checksum_errors += 1
        
        if payload.sequence_id <= self.last_sequence_id:
            with self.stats_lock:
                self.out_of_order_messages += 1
        elif payload.sequence_id > self.last_sequence_id + 1:
            missed = payload.sequence_id - self.last_sequence_id - 1
            with self.stats_lock:
                self.lost_messages += missed
        
        self.last_sequence_id = payload.sequence_id
        
        # Create response with default values for its explicit types
        response = LatencyTestResponse(
            original_sequence_id=0, test_session_id=0, receiver_id="",
            original_send_timestamp_ns=0, receive_timestamp_ns=0,
            response_send_timestamp_ns=0, payload_received_size_bytes=0
        )
        response.original_sequence_id = payload.sequence_id
        response.original_send_timestamp_ns = payload.send_timestamp_ns
        response.receive_timestamp_ns = receive_timestamp
        response.test_session_id = payload.test_session_id
        response.receiver_id = self.receiver_id
        response.payload_received_size_bytes = len(payload.large_data)
        
        try:
            response.response_send_timestamp_ns = time.time_ns()
            self.response_publisher.Write(response)
            
            processing_end = time.time_ns()
            processing_time_ns = processing_end - processing_start
            processing_time_ms = processing_time_ns / 1_000_000.0
            
            with self.stats_lock:
                self.messages_received += 1
                self.responses_sent += 1
                self.receive_times.append(receive_latency_ms)
                self.processing_times.append(processing_time_ms)
                self.payload_sizes.append(response.payload_received_size_bytes)
            
            integrity_status = "✓" if integrity_ok else "✗"
            print(f"Processed seq {payload.sequence_id:4d} | "
                  f"Size: {response.payload_received_size_bytes/1024:.0f}KB | "
                  f"Receive: {receive_latency_ms:.3f}ms | "
                  f"Process: {processing_time_ms:.3f}ms | "
                  f"Integrity: {integrity_status}")
                  
        except Exception as e:
            print(f"Failed to send response for sequence {payload.sequence_id}: {e}")

    # ... (rest of the class is unchanged) ...
    def receiver_thread(self):
        """Main receiver thread"""
        print("Starting receiver thread...")
        
        while self.running:
            try:
                payload = self.payload_subscriber.Read(100)  # 100ms timeout
                
                if payload is not None:
                    self.process_received_payload(payload)
                    
            except Exception as e:
                if self.running:
                    print(f"Receiver thread error: {e}")
                    time.sleep(0.1)
    
    def stats_thread(self):
        """Thread to print periodic statistics"""
        last_stats_time = time.time()
        
        while self.running:
            time.sleep(5.0)  # Print stats every 5 seconds
            
            current_time = time.time()
            if current_time - last_stats_time >= 5.0:
                self.print_interim_stats()
                last_stats_time = current_time
    
    def print_interim_stats(self):
        """Print interim statistics during test"""
        with self.stats_lock:
            if self.receive_times:
                avg_receive_time = statistics.mean(self.receive_times)
                avg_processing_time = statistics.mean(self.processing_times)
                avg_payload_size = statistics.mean(self.payload_sizes) / 1024  # KB
                
                print(f"\n--- Receiver Stats ---")
                print(f"Messages received: {self.messages_received}")
                print(f"Responses sent: {self.responses_sent}")
                print(f"Lost messages: {self.lost_messages}")
                print(f"Out of order: {self.out_of_order_messages}")
                print(f"Checksum errors: {self.checksum_errors}")
                print(f"Avg receive latency: {avg_receive_time:.3f}ms")
                print(f"Avg processing time: {avg_processing_time:.3f}ms")
                print(f"Avg payload size: {avg_payload_size:.0f}KB")
                print("-" * 22)
    
    def run_receiver(self):
        """Run the receiver"""
        print(f"\n=== DDS Latency Test Receiver ===")
        print(f"Network Interface: {self.network_interface}")
        print(f"Receiver ID: {self.receiver_id}")
        print("Waiting for test messages...")
        print("Press Ctrl+C to stop")
        print("=" * 40)
        
        if not self.initialize_dds():
            return
        
        self.running = True
        
        # Start receiver thread
        receiver_thread = threading.Thread(target=self.receiver_thread, daemon=True)
        receiver_thread.start()
        
        # Start stats thread
        stats_thread = threading.Thread(target=self.stats_thread, daemon=True)
        stats_thread.start()
        
        try:
            # Keep main thread alive
            while self.running:
                time.sleep(1.0)
                
        except KeyboardInterrupt:
            print("\nReceiver stopped by user")
        finally:
            self.running = False
            
        # Print final statistics
        self.print_final_stats()
        
        # Cleanup
        if self.payload_subscriber:
            self.payload_subscriber.Close()
        if self.response_publisher:
            self.response_publisher.Close()
    
    def print_final_stats(self):
        """Print comprehensive final statistics"""
        print(f"\n{'='*60}")
        print("FINAL RECEIVER RESULTS")
        print(f"{'='*60}")
        
        with self.stats_lock:
            print(f"Messages Statistics:")
            print(f"  Messages Received: {self.messages_received}")
            print(f"  Responses Sent: {self.responses_sent}")
            print(f"  Lost Messages: {self.lost_messages}")
            print(f"  Out of Order Messages: {self.out_of_order_messages}")
            print(f"  Checksum Errors: {self.checksum_errors}")
            
            if self.messages_received > 0:
                loss_rate = (self.lost_messages / (self.messages_received + self.lost_messages)) * 100
                error_rate = (self.checksum_errors / self.messages_received) * 100
                print(f"  Message Loss Rate: {loss_rate:.2f}%")
                print(f"  Data Error Rate: {error_rate:.2f}%")
            
            if self.receive_times:
                print(f"\nReceive Latency (Forward Path):")
                rx_avg = statistics.mean(self.receive_times)
                rx_min = min(self.receive_times)
                rx_max = max(self.receive_times)
                rx_std = statistics.stdev(self.receive_times) if len(self.receive_times) > 1 else 0
                
                print(f"  Average: {rx_avg:.3f}ms")
                print(f"  Min: {rx_min:.3f}ms")
                print(f"  Max: {rx_max:.3f}ms")
                print(f"  Std Dev: {rx_std:.3f}ms")
                
                # Percentiles
                sorted_rx = sorted(self.receive_times)
                p95_rx = sorted_rx[int(0.95 * len(sorted_rx))]
                p99_rx = sorted_rx[int(0.99 * len(sorted_rx))]
                print(f"  95th percentile: {p95_rx:.3f}ms")
                print(f"  99th percentile: {p99_rx:.3f}ms")
            
            if self.processing_times:
                print(f"\nProcessing Times:")
                proc_avg = statistics.mean(self.processing_times)
                proc_min = min(self.processing_times)
                proc_max = max(self.processing_times)
                proc_std = statistics.stdev(self.processing_times) if len(self.processing_times) > 1 else 0
                
                print(f"  Average: {proc_avg:.3f}ms")
                print(f"  Min: {proc_min:.3f}ms")
                print(f"  Max: {proc_max:.3f}ms")
                print(f"  Std Dev: {proc_std:.3f}ms")
                
                # Percentiles
                sorted_proc = sorted(self.processing_times)
                p95_proc = sorted_proc[int(0.95 * len(sorted_proc))]
                p99_proc = sorted_proc[int(0.99 * len(sorted_proc))]
                print(f"  95th percentile: {p95_proc:.3f}ms")
                print(f"  99th percentile: {p99_proc:.3f}ms")
            
            if self.payload_sizes:
                avg_size_kb = statistics.mean(self.payload_sizes) / 1024
                print(f"\nPayload Information:")
                print(f"  Average Payload Size: {avg_size_kb:.0f}KB")
                print(f"  Total Data Received: {sum(self.payload_sizes)/1024/1024:.1f}MB")
        
        print(f"{'='*60}")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='DDS Latency Test Receiver')
    parser.add_argument('--interface', default='enP8p1s0', help='DDS network interface')
    
    args = parser.parse_args()
    
    # Create and run receiver
    receiver = DDSLatencyReceiver(network_interface=args.interface)
    receiver.run_receiver()

if __name__ == "__main__":
    main()