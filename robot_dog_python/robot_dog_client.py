import socket
import time
import uuid
from datetime import timezone, datetime
import os
import logging
from dotenv import load_dotenv
import select # For non-blocking receive

import cv2 

# Adjust import path if messages_pb2.py is not directly in protobuf_definitions
# For example, if it's in a subfolder like 'generated':
# from protobuf_definitions.generated import messages_pb2 as pb
# Assuming it's directly under protobuf_definitions for now
from protobuf_definitions import messages_pb2 as pb

# --- Configuration ---
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env') # Path to .env in project root
load_dotenv(dotenv_path=dotenv_path, override=True)
print(f"RD: Attempting to load .env from: {os.path.abspath(dotenv_path)}")


RD_CLIENT_ID = os.getenv("RD_CLIENT_ID", "robot_dog_alpha")
CE_CLIENT_ID = os.getenv("CE_CLIENT_ID", "controller_main_default") # Match default if CE .env not found
CS_HOST = os.getenv("TARGET_CS_HOST", "127.0.0.1")
CS_PORT = int(os.getenv("TARGET_CS_PORT", 9000))
JPEG_QUALITY = int(os.getenv("JPEG_QUALITY", 70))
VIDEO_FPS = int(os.getenv("VIDEO_FPS", 10)) # Target FPS for video stream
STATUS_UPDATE_INTERVAL_S = float(os.getenv("STATUS_UPDATE_INTERVAL_S", 1.0)) # Interval in seconds

logging.basicConfig(level=logging.INFO, format='RD: %(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_current_timestamp_ms():
    return int(datetime.now(timezone.utc).timestamp() * 1000)

def create_message_header(source_id, target_id, session_id=None, trial_id=None):
    header = pb.Header()
    header.message_id = str(uuid.uuid4())
    header.timestamp_utc_ms = get_current_timestamp_ms()
    header.source_id = source_id
    header.target_id = target_id
    if session_id: header.session_id = session_id
    if trial_id: header.trial_id = trial_id
    return header

def create_udp_wrapper(inner_message_bytes, inner_message_type_str, source_client_id, relay_target_client_id):
    wrapper = pb.UdpPacketWrapper()
    wrapper.header.CopyFrom(create_message_header(source_id=source_client_id, target_id="server")) # Wrapper always targets server for relay
    wrapper.target_client_id_for_relay = relay_target_client_id
    wrapper.actual_message_type = inner_message_type_str
    wrapper.actual_message_data = inner_message_bytes # Expecting bytes
    return wrapper

def preprocess_frame(frame, width=640, height=480, jpeg_quality=80):
    if frame is None:
        return b''
    try:
        resized = cv2.resize(frame, (width, height))
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality]
        result, encimg = cv2.imencode('.jpg', resized, encode_param)
        if result:
            return encimg.tobytes()
        else:
            logger.error("Failed to encode frame to JPEG.")
            return b''
    except Exception as e:
        logger.error(f"Error in preprocess_frame: {e}")
        return b''

def main():
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # No explicit bind() needed for client sending and receiving replies/relayed messages
    # The OS assigns an ephemeral port when sendto is first called.

    logger.info(f"Robot Dog '{RD_CLIENT_ID}' started. Targeting CS at {CS_HOST}:{CS_PORT}. Will relay to '{CE_CLIENT_ID}'.")

    # 1. Register with Cloud Server
    reg_request_payload = pb.RegisterClientRequest()
    reg_request_payload.header.CopyFrom(create_message_header(RD_CLIENT_ID, "server"))
    reg_request_payload.client_type = pb.ClientType.ROBOT_DOG
    reg_request_payload.client_id = RD_CLIENT_ID
    reg_request_payload.client_version = "0.2.0" # Match CE version
    reg_request_payload.capabilities.extend(["video_JPEG", "status_updates"])


    wrapper_reg = create_udp_wrapper(
        inner_message_bytes=reg_request_payload.SerializeToString(),
        inner_message_type_str="dog_system.v1.RegisterClientRequest",
        source_client_id=RD_CLIENT_ID,
        relay_target_client_id="server" # Registration is for the server itself
    )

    try:
        udp_socket.sendto(wrapper_reg.SerializeToString(), (CS_HOST, CS_PORT))
        logger.info(f"Sent RegisterClientRequest to CS. Message ID: {reg_request_payload.header.message_id}")
    except Exception as e:
        logger.error(f"Error sending registration: {e}", exc_info=True)
        udp_socket.close()
        return

    cap = None
    try:
        cap = cv2.VideoCapture(0) # Default camera
        if not cap.isOpened():
            logger.warning("Cannot open camera! Video stream will be disabled.")
            cap = None # Ensure cap is None if not opened
    except Exception as e:
        logger.warning(f"Error opening camera: {e}. Video stream will be disabled.")
        cap = None

    frame_id_counter = 0
    loop_counter = 0
    last_status_update_time = time.monotonic()
    
    # For converting enum numbers to names for logging
    system_action_type_names = {v: k for k, v in pb.SystemActionCommand.ActionType.items()}
    posture_type_names = {v: k for k, v in pb.SetPostureCommand.PostureType.items()}
    nav_state_names = {v: k for k, v in pb.NavigationState.items()}
    sys_event_severity_names = {v: k for k, v in pb.SystemEventSeverity.items()}


    try:
        while True:
            # --- Handle Incoming Messages (Non-blocking) ---
            # Check if there's data to read with a short timeout
            ready_to_read, _, _ = select.select([udp_socket], [], [], 0.005) # Small timeout

            if ready_to_read:
                try:
                    data, addr = udp_socket.recvfrom(65535) # Max UDP packet size
                    # logger.debug(f"Received {len(data)} bytes from {addr}")

                    wrapper = pb.UdpPacketWrapper()
                    wrapper.ParseFromString(data)
                    
                    # Log basic wrapper info, but not too verbosely for frequent messages
                    # logger.info(f"Incoming: Type='{wrapper.actual_message_type}', From='{wrapper.header.source_id}', RelayTarget='{wrapper.target_client_id_for_relay}'")

                    # Process based on actual_message_type
                    if wrapper.actual_message_type == "dog_system.v1.ControlCommand":
                        cmd = pb.ControlCommand()
                        cmd.ParseFromString(wrapper.actual_message_data)
                        logger.info(f"ROBOT RECEIVED ControlCommand: LinX={cmd.linear_velocity_x:.2f}, LinY={cmd.linear_velocity_y:.2f}, AngZ={cmd.angular_velocity_z:.2f} (from {wrapper.header.source_id})")
                        # TODO: Implement actual robot movement logic here
                    
                    elif wrapper.actual_message_type == "dog_system.v1.SystemActionCommand":
                        cmd = pb.SystemActionCommand()
                        cmd.ParseFromString(wrapper.actual_message_data)
                        action_name = system_action_type_names.get(cmd.action, "UNKNOWN_ACTION")
                        logger.info(f"ROBOT RECEIVED SystemActionCommand: Action={action_name} ({cmd.action}) (from {wrapper.header.source_id})")
                        if cmd.action == pb.SystemActionCommand.ActionType.EMERGENCY_STOP:
                            logger.critical("ROBOT EXECUTES EMERGENCY STOP")
                            # TODO: Implement actual emergency stop logic
                        # Add other actions as needed
                    
                    elif wrapper.actual_message_type == "dog_system.v1.SetPostureCommand":
                        cmd = pb.SetPostureCommand()
                        cmd.ParseFromString(wrapper.actual_message_data)
                        posture_name = posture_type_names.get(cmd.posture, "UNKNOWN_POSTURE")
                        logger.info(f"ROBOT RECEIVED SetPostureCommand: Posture={posture_name} ({cmd.posture}) (from {wrapper.header.source_id})")
                        if cmd.posture == pb.SetPostureCommand.PostureType.STAND:
                            logger.info("ROBOT EXECUTES: Stand up")
                        elif cmd.posture == pb.SetPostureCommand.PostureType.LIE_DOWN:
                            logger.info("ROBOT EXECUTES: Lie down")
                        # TODO: Implement actual posture change logic
                    
                    elif wrapper.actual_message_type == "dog_system.v1.RegisterClientResponse":
                        response = pb.RegisterClientResponse()
                        response.ParseFromString(wrapper.actual_message_data)
                        logger.info(f"Received RegisterClientResponse from {wrapper.header.source_id}: Success={response.success}, Msg='{response.message}'")

                    else:
                        logger.warning(f"Unhandled message type received: {wrapper.actual_message_type} from {wrapper.header.source_id}")

                except Exception as e:
                    logger.error(f"Error processing incoming message: {e}", exc_info=True)


            # --- Outgoing Messages (Status and Video) ---
            current_time = time.monotonic()

            # Send Robot Status Update periodically
            if current_time - last_status_update_time >= STATUS_UPDATE_INTERVAL_S:
                status_update_payload = pb.RobotStatusUpdate()
                status_update_payload.header.CopyFrom(create_message_header(RD_CLIENT_ID, CE_CLIENT_ID)) # Target CE
                status_update_payload.battery_percent = 88.8 - (loop_counter / 100.0 % 20) # Example
                status_update_payload.current_world_pose.position.x = 1.0 + (loop_counter / 10.0 % 5)
                status_update_payload.current_world_pose.position.y = 2.0
                status_update_payload.current_world_pose.position.z = 0.0
                status_update_payload.current_world_pose.orientation.w = 1.0 # Default orientation
                status_update_payload.navigation_state = pb.NavigationState.IDLE
                status_update_payload.human_detection.is_present = (loop_counter % 20 < 10)
                status_update_payload.human_detection.distance_m = 3.2
                status_update_payload.overall_system_health = pb.SystemEventSeverity.INFO

                wrapper_status = create_udp_wrapper(
                    inner_message_bytes=status_update_payload.SerializeToString(),
                    inner_message_type_str="dog_system.v1.RobotStatusUpdate",
                    source_client_id=RD_CLIENT_ID,
                    relay_target_client_id=CE_CLIENT_ID # Relay to Controller End
                )
                udp_socket.sendto(wrapper_status.SerializeToString(), (CS_HOST, CS_PORT))
                # logger.debug(f"Sent RobotStatusUpdate (msg_id: {status_update_payload.header.message_id})")
                last_status_update_time = current_time

            # Send Video Stream Packet
            frame_data = b''
            if cap:
                ret, frame = cap.read()
                if ret:
                    frame_data = preprocess_frame(frame, 640, 480, JPEG_QUALITY)
                else:
                    logger.warning("Camera read failed, frame skipped for this iteration.")
            
            if frame_data: # Only send if frame data was successfully processed
                video_packet_payload = pb.VideoStreamPacket()
                video_packet_payload.header.CopyFrom(create_message_header(RD_CLIENT_ID, CE_CLIENT_ID)) # Target CE
                video_packet_payload.frame_id = frame_id_counter
                video_packet_payload.frame_data = frame_data
                video_packet_payload.encoding_type = "JPEG" # Matched with preprocess_frame
                video_packet_payload.width = 640
                video_packet_payload.height = 480
                video_packet_payload.is_key_frame = True # For JPEG, every frame is a key frame

                wrapper_video = create_udp_wrapper(
                    inner_message_bytes=video_packet_payload.SerializeToString(),
                    inner_message_type_str="dog_system.v1.VideoStreamPacket",
                    source_client_id=RD_CLIENT_ID,
                    relay_target_client_id=CE_CLIENT_ID # Relay to Controller End
                )
                udp_socket.sendto(wrapper_video.SerializeToString(), (CS_HOST, CS_PORT))
                # logger.debug(f"Sent VideoStreamPacket frame_id: {frame_id_counter}")
                frame_id_counter += 1
            
            loop_counter += 1
            time.sleep(1.0 / VIDEO_FPS if VIDEO_FPS > 0 else 0.1) # Control loop speed / video FPS

    except KeyboardInterrupt:
        logger.info("Robot dog client shutting down due to KeyboardInterrupt...")
    except Exception as e:
        logger.error(f"Critical error in main loop: {e}", exc_info=True)
    finally:
        if cap:
            cap.release()
            logger.info("Camera released.")
        udp_socket.close()
        logger.info("UDP socket closed. Robot dog client terminated.")

if __name__ == "__main__":
    # Ensure protobuf definitions are generated and accessible
    # e.g., run from the project root: python -m robot_dog_python.robot_dog_client
    # or ensure PYTHONPATH is set up correctly.
    
    # For direct execution, if protobuf_definitions is a sibling folder:
    # import sys
    # sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
    # from protobuf_definitions import messages_pb2 as pb # Re-import if path was added
    
    main()