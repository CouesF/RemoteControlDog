import socket
import time
import uuid
from datetime import timezone, datetime
import os
import logging
from dotenv import load_dotenv

import cv2  # 新增

# Adjust import path
from protobuf_definitions import messages_pb2 as pb

# --- Configuration ---
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path=dotenv_path, override=True)
print(f"RD: Attempting to load .env from: {dotenv_path}")

RD_CLIENT_ID = os.getenv("RD_CLIENT_ID", "robot_dog_alpha")
CE_CLIENT_ID = os.getenv("CE_CLIENT_ID", "controller_main")
CS_HOST = os.getenv("TARGET_CS_HOST", "127.0.0.1")
CS_PORT = int(os.getenv("TARGET_CS_PORT", 9000))
JPEG_QUALITY = int(os.getenv("JPEG_QUALITY", 70))  # 新增，允许配置压缩率，默认80

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

def create_udp_wrapper(inner_message, inner_message_type_str, source_client_id, relay_target_client_id):
    wrapper = pb.UdpPacketWrapper()
    wrapper.header.CopyFrom(create_message_header(source_id=source_client_id, target_id="server"))
    wrapper.target_client_id_for_relay = relay_target_client_id
    wrapper.actual_message_type = inner_message_type_str
    wrapper.actual_message_data = inner_message
    return wrapper

def preprocess_frame(frame, width=640, height=480, jpeg_quality=80):
    """BGR np.ndarray -> JPEG Bytes, 预处理到640x480，并设置压缩率"""
    resized = cv2.resize(frame, (width, height))
    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality]
    result, encimg = cv2.imencode('.jpg', resized, encode_param)
    if result:
        return encimg.tobytes()
    else:
        logger.error("Failed to encode frame to JPEG.")
        return b''

def main():
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    logger.info(f"Robot Dog '{RD_CLIENT_ID}' started. Sending data to CS at {CS_HOST}:{CS_PORT}")

    # 1. Register with Cloud Server
    reg_request_payload = pb.RegisterClientRequest()
    reg_request_payload.header.CopyFrom(create_message_header(RD_CLIENT_ID, "server"))
    reg_request_payload.client_type = pb.ClientType.ROBOT_DOG
    reg_request_payload.client_id = RD_CLIENT_ID
    reg_request_payload.client_version = "0.2.0"

    wrapper_reg = create_udp_wrapper(
        inner_message=reg_request_payload.SerializeToString(),
        inner_message_type_str="dog_system.v1.RegisterClientRequest",
        source_client_id=RD_CLIENT_ID,
        relay_target_client_id="server"
    )

    try:
        udp_socket.sendto(wrapper_reg.SerializeToString(), (CS_HOST, CS_PORT))
        logger.info(f"Sent RegisterClientRequest to CS. Message ID: {reg_request_payload.header.message_id}")
    except Exception as e:
        logger.error(f"Error sending registration: {e}", exc_info=True)
        return

    # --- 新增：初始化摄像头 ---
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        logger.error("Cannot open camera! Please check your camera device.")
        return

    frame_id_counter = 0
    loop_counter = 0
    try:
        while True:
            # --- 读取摄像头帧 ---
            ret, frame = cap.read()
            if not ret:
                logger.warning("Camera read failed, frame skipped.")
                sample_frame_data = b''
            else:
                # --- 预处理帧 ---
                sample_frame_data = preprocess_frame(frame, 640, 480, JPEG_QUALITY)

            # Send Robot Status Update (e.g., every 1 second)
            if loop_counter % 10 == 0:
                status_update_payload = pb.RobotStatusUpdate()
                status_update_payload.header.CopyFrom(create_message_header(RD_CLIENT_ID, CE_CLIENT_ID))
                status_update_payload.battery_percent = 88.8 - (loop_counter / 100.0)
                status_update_payload.current_world_pose.position.x = 1.0 + (loop_counter / 10.0)
                status_update_payload.current_world_pose.position.y = 2.0
                status_update_payload.current_world_pose.position.z = 0.0
                status_update_payload.current_world_pose.orientation.w = 1.0
                status_update_payload.navigation_state = pb.NavigationState.IDLE
                status_update_payload.human_detection.is_present = (loop_counter % 20 < 10)
                status_update_payload.human_detection.distance_m = 3.2
                status_update_payload.overall_system_health = pb.SystemEventSeverity.INFO

                wrapper_status = create_udp_wrapper(
                    inner_message=status_update_payload.SerializeToString(),
                    inner_message_type_str="dog_system.v1.RobotStatusUpdate",
                    source_client_id=RD_CLIENT_ID,
                    relay_target_client_id=CE_CLIENT_ID
                )
                udp_socket.sendto(wrapper_status.SerializeToString(), (CS_HOST, CS_PORT))
                logger.debug(f"Sent RobotStatusUpdate (msg_id: {status_update_payload.header.message_id})")

            # Send Video Stream Packet
            video_packet_payload = pb.VideoStreamPacket()
            video_packet_payload.header.CopyFrom(create_message_header(RD_CLIENT_ID, CE_CLIENT_ID))
            video_packet_payload.frame_id = frame_id_counter
            video_packet_payload.frame_data = sample_frame_data
            video_packet_payload.encoding_type = "JPEG"
            video_packet_payload.width = 640
            video_packet_payload.height = 480
            video_packet_payload.is_key_frame = True

            wrapper_video = create_udp_wrapper(
                inner_message=video_packet_payload.SerializeToString(),
                inner_message_type_str="dog_system.v1.VideoStreamPacket",
                source_client_id=RD_CLIENT_ID,
                relay_target_client_id=CE_CLIENT_ID
            )
            udp_socket.sendto(wrapper_video.SerializeToString(), (CS_HOST, CS_PORT))
            logger.debug(f"Sent VideoStreamPacket frame_id: {frame_id_counter} (msg_id: {video_packet_payload.header.message_id})")

            frame_id_counter += 1
            loop_counter += 1
            time.sleep(0.1) # ~10 FPS

    except Exception as e:
        logger.error(f"Error in main loop: {e}", exc_info=True)
    finally:
        cap.release()

if __name__ == "__main__":
    main()