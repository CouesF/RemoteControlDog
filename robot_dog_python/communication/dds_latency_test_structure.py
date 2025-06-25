# dds_latency_test_structure.py
"""
DDS data structure for latency testing with large payloads.
This should be placed in your communication directory alongside dds_data_structure.py
"""

# from unitree_sdk2py.idl.default import dds_
#from unitree_sdk2py.idl.unitree_go.msg.dds_ import Header_
from dataclasses import dataclass

@dataclass
class LargeTestPayload:
    """
    Large payload structure for DDS latency testing.
    Contains configurable data size and timing information.
    """
    def __init__(self):
        # Timing fields
        self.sequence_id = 0           # Unique ID for each message
        self.send_timestamp_ns = 0     # Timestamp when data was sent (nanoseconds)
        self.payload_size_bytes = 0    # Actual size of the payload in bytes
        self.test_session_id = 0       # ID to group related test messages
        
        # Large data payload - adjust size as needed
        # 500KB = 512,000 bytes. Since each float is typically 4 bytes,
        # we need ~128,000 floats for 500KB
        self.large_data = [0.0] * 128000  # ~500KB of float data
        
        # Additional metadata
        self.sender_id = ""            # Identifier for the sender
        self.test_frequency_hz = 0.0   # Target frequency for this test
        self.checksum = 0              # Simple checksum for data integrity

@dataclass 
class LatencyTestResponse:
    """
    Response payload for round-trip latency measurement.
    Smaller payload to acknowledge receipt and measure RTT.
    """
    def __init__(self):
        # Echo back the original timing info
        self.original_sequence_id = 0
        self.original_send_timestamp_ns = 0
        self.receive_timestamp_ns = 0      # When receiver got the original message
        self.response_send_timestamp_ns = 0 # When this response was sent
        
        # Test metadata
        self.test_session_id = 0
        self.receiver_id = ""
        self.processing_time_ns = 0        # Time spent processing the original message
        self.payload_received_size_bytes = 0 # Size of payload that was received