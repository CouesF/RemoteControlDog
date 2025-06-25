# dds_latency_test_structure.py
"""
Data structures for the DDS latency test, defined using explicit 
cyclonedds.idl.types for maximum robustness.
"""

from dataclasses import dataclass, field
from cyclonedds.idl import IdlStruct
import cyclonedds.idl.types as types # IMPORT the explicit types

@dataclass
class LargeTestPayload(IdlStruct, typename="LargeTestPayload"):
    """
    The payload sent from the sender to the receiver.
    """
    # CHANGED: All fields now use explicit DDS types.
    sequence_id: types.uint32
    test_session_id: types.uint64
    sender_id: types.string
    send_timestamp_ns: types.uint64
    test_frequency_hz: types.float32
    payload_size_bytes: types.uint32
    checksum: types.uint32
    # CHANGED: This is the correct way to define a variable-length byte array.
    large_data: types.sequence[types.uint8]

@dataclass
class LatencyTestResponse(IdlStruct, typename="LatencyTestResponse"):
    """
    The response sent from the receiver back to the sender.
    """
    # CHANGED: All fields now use explicit DDS types.
    original_sequence_id: types.uint32
    test_session_id: types.uint64
    receiver_id: types.string
    original_send_timestamp_ns: types.uint64
    receive_timestamp_ns: types.uint64
    response_send_timestamp_ns: types.uint64
    payload_received_size_bytes: types.uint32