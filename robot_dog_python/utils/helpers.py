# RemoteControlDog/robot_dog_python/utils/helpers.py
import uuid
from datetime import timezone, datetime

# Assuming protobuf_definitions is correctly in PYTHONPATH or relative import works
# For this structure, we might need to adjust import if messages_pb2 is not directly accessible
# For now, let's assume it will be handled by the main app or PYTHONPATH setup.
# from ..communication.protobuf_definitions import messages_pb2 as pb
# If running main_robot_dog.py from robot_dog_python, then:
# from communication.protobuf_definitions import messages_pb2 as pb

# This will be passed in to avoid circular dependencies or path issues early on
pb = None # Placeholder, will be set by the app

def set_protobuf_definition(protobuf_module):
    global pb
    pb = protobuf_module


def get_current_timestamp_ms():
    return int(datetime.now(timezone.utc).timestamp() * 1000)

def create_message_header(source_id, target_id, session_id=None, trial_id=None):
    if pb is None:
        raise RuntimeError("Protobuf definition (pb) not set in helpers module.")
    header = pb.Header()
    header.message_id = str(uuid.uuid4())
    header.timestamp_utc_ms = get_current_timestamp_ms()
    header.source_id = source_id
    header.target_id = target_id
    if session_id: header.session_id = session_id
    if trial_id: header.trial_id = trial_id
    return header

def create_udp_wrapper(inner_message_bytes, inner_message_type_str, source_client_id, relay_target_client_id, current_session_id=None, current_trial_id=None):
    if pb is None:
        raise RuntimeError("Protobuf definition (pb) not set in helpers module.")
    wrapper = pb.UdpPacketWrapper()
    # Pass session/trial IDs to the wrapper header as well if they are active
    wrapper.header.CopyFrom(create_message_header(
        source_id=source_client_id,
        target_id="server", # Wrapper always targets server for relay
        session_id=current_session_id,
        trial_id=current_trial_id
    ))
    wrapper.target_client_id_for_relay = relay_target_client_id
    wrapper.actual_message_type = inner_message_type_str
    wrapper.actual_message_data = inner_message_bytes
    return wrapper