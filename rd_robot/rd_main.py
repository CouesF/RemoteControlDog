import socket
import time
import uuid
from datetime import timezone, datetime
from dotenv import load_dotenv # Added


# Make sure messages_pb2.py is in the same directory or Python path
import messages_pb2 as pb

# Load environment variables from .env file in the parent directory
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env') # Added
load_dotenv(dotenv_path=dotenv_path) # Added

# Configuration
RD_CLIENT_ID = "robot_dog_alpha"
CE_CLIENT_ID = "controller_main" # Target for data
CS_HOST = os.getenv("TARGET_CS_HOST", "127.0.0.1") # Changed
CS_PORT = int(os.getenv("TARGET_CS_PORT", 9000))    # Changed and cast to int
VIDEO_FRAME_PATH = "sample_video_frame.jpg" # Path to a sample JPEG image

def get_current_timestamp_ms():
    return int(datetime.now(timezone.utc).timestamp() * 1000)

def create_header(source_id, target_id):
    header = pb.Header()
    header.message_id = str(uuid.uuid4())
    header.timestamp_utc_ms = get_current_timestamp_ms()
    header.source_id = source_id
    header.target_id = target_id # For UdpPacketWrapper, target_id is server,
                                 # target_client_id_for_relay is the final recipient
    return header

def main():
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print(f"RD: Robot Dog '{RD_CLIENT_ID}' started. Sending data to CS at {CS_HOST}:{CS_PORT}")

    # 1. Register with Cloud Server
    reg_request = pb.RegisterClientRequest()
    reg_request.header.CopyFrom(create_header(RD_CLIENT_ID, "server")) # Message for server
    reg_request.client_type = pb.ClientType.ROBOT_DOG
    reg_request.client_id = RD_CLIENT_ID
    reg_request.client_version = "0.1.0"

    wrapper_reg = pb.UdpPacketWrapper()
    wrapper_reg.header.CopyFrom(create_header(RD_CLIENT_ID, "server")) # Wrapper for server
    wrapper_reg.target_client_id_for_relay = "server" # Registration is for server itself
    wrapper_reg.actual_message_type = "dog_system.v1.RegisterClientRequest"
    wrapper_reg.actual_message_data = reg_request.SerializeToString()
    
    try:
        udp_socket.sendto(wrapper_reg.SerializeToString(), (CS_HOST, CS_PORT))
        print(f"RD: Sent RegisterClientRequest to CS")
    except Exception as e:
        print(f"RD: Error sending registration: {e}")
        return


    frame_id_counter = 0
    try:
        with open(VIDEO_FRAME_PATH, "rb") as f:
            sample_frame_data = f.read()
    except FileNotFoundError:
        print(f"RD: Error - {VIDEO_FRAME_PATH} not found. Video stream will send empty frames.")
        sample_frame_data = b''


    while True:
        try:
            # 2. Send Robot Status Update
            status_update = pb.RobotStatusUpdate()
            status_update.header.CopyFrom(create_header(RD_CLIENT_ID, CE_CLIENT_ID))
            status_update.battery_percent = 75.5
            status_update.current_world_pose.position.x = 1.0
            status_update.current_world_pose.position.y = 2.0
            status_update.current_world_pose.position.z = 0.0
            status_update.current_world_pose.orientation.w = 1.0 # Neutral orientation
            status_update.navigation_state = pb.NavigationState.IDLE
            status_update.human_detection.is_present = True
            status_update.human_detection.distance_m = 3.2
            status_update.overall_system_health = pb.SystemEventSeverity.INFO

            wrapper_status = pb.UdpPacketWrapper()
            # The wrapper's header source is RD, target is SERVER (CS)
            wrapper_status.header.CopyFrom(create_header(RD_CLIENT_ID, "server"))
            wrapper_status.target_client_id_for_relay = CE_CLIENT_ID # Final destination
            wrapper_status.actual_message_type = "dog_system.v1.RobotStatusUpdate"
            wrapper_status.actual_message_data = status_update.SerializeToString()
            
            udp_socket.sendto(wrapper_status.SerializeToString(), (CS_HOST, CS_PORT))
            print(f"RD: Sent RobotStatusUpdate (msg_id: {status_update.header.message_id})")

            # 3. Send Video Stream Packet
            video_packet = pb.VideoStreamPacket()
            video_packet.header.CopyFrom(create_header(RD_CLIENT_ID, CE_CLIENT_ID))
            video_packet.frame_id = frame_id_counter
            video_packet.frame_data = sample_frame_data # Use actual frame data
            video_packet.encoding_type = "JPEG" # Assuming MJPEG or similar
            video_packet.width = 640 # Example
            video_packet.height = 480 # Example
            video_packet.is_key_frame = True

            wrapper_video = pb.UdpPacketWrapper()
            wrapper_video.header.CopyFrom(create_header(RD_CLIENT_ID, "server"))
            wrapper_video.target_client_id_for_relay = CE_CLIENT_ID
            wrapper_video.actual_message_type = "dog_system.v1.VideoStreamPacket"
            wrapper_video.actual_message_data = video_packet.SerializeToString()

            udp_socket.sendto(wrapper_video.SerializeToString(), (CS_HOST, CS_PORT))
            print(f"RD: Sent VideoStreamPacket frame_id: {frame_id_counter} (msg_id: {video_packet.header.message_id})")
            
            frame_id_counter += 1
            time.sleep(0.1) # Send data roughly 10 FPS for video, 1 FPS for status (adjust as needed)

        except Exception as e:
            print(f"RD: Error in main loop: {e}")
            time.sleep(1) # Avoid spamming errors

if __name__ == "__main__":
    main()