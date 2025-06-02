import socket
import os
import logging
from dotenv import load_dotenv

# Adjust import path based on the new structure
from protobuf_definitions import messages_pb2 as pb

# --- Configuration ---
# Load environment variables from .env file in the project root
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path=dotenv_path, override=True)
print(f"CS: Attempting to load .env from: {dotenv_path}")
if not os.path.exists(dotenv_path):
    print(f"CS: Warning - .env file not found at {dotenv_path}. Trying local .env")
    local_dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(local_dotenv_path):
        load_dotenv(dotenv_path=local_dotenv_path, override=True)
        print(f"CS: Loaded .env from local directory: {local_dotenv_path}")
    else:
        print(f"CS: Warning - No .env file found. Using defaults or environment variables.")


CS_HOST = os.getenv("CS_LISTEN_HOST", "0.0.0.0")
CS_PORT = int(os.getenv("CS_LISTEN_PORT", 9000))
BUFFER_SIZE = 65535

# --- Logging ---
logging.basicConfig(level=logging.INFO, format='CS: %(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# In-memory store for client_id -> (ip, port)
client_addresses = {}

def main():
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        udp_socket.bind((CS_HOST, CS_PORT))
        logger.info(f"Cloud Server listening on {CS_HOST}:{CS_PORT}")
    except Exception as e:
        logger.fatal(f"Error binding socket: {e}", exc_info=True)
        return

    while True:
        try:
            data, addr = udp_socket.recvfrom(BUFFER_SIZE)
            # logger.debug(f"Received {len(data)} bytes from {addr}")

            wrapper = pb.UdpPacketWrapper()
            try:
                wrapper.ParseFromString(data)
                # logger.debug(f"Parsed UdpPacketWrapper from {addr}. Type: {wrapper.actual_message_type}, RelayTarget: {wrapper.target_client_id_for_relay}")
            except Exception as e:
                logger.error(f"Failed to parse UdpPacketWrapper from {addr}: {e}. Data (hex): {data[:64].hex()}")
                continue

            source_id_from_wrapper_header = wrapper.header.source_id
            if not source_id_from_wrapper_header:
                logger.warning(f"Packet from {addr} has no source_id in wrapper header. Cannot register/update.")
            elif source_id_from_wrapper_header != "server": # Don't register "server" as a client
                if client_addresses.get(source_id_from_wrapper_header) != addr:
                    logger.info(f"Registered/Updated client '{source_id_from_wrapper_header}' -> {addr}")
                    client_addresses[source_id_from_wrapper_header] = addr

            # Handle RegisterClientRequest specifically to send a response (optional but good practice)
            if wrapper.actual_message_type == "dog_system.v1.RegisterClientRequest":
                try:
                    reg_req = pb.RegisterClientRequest()
                    reg_req.ParseFromString(wrapper.actual_message_data) # Parse inner message
                    logger.info(f"Received RegisterClientRequest from '{reg_req.client_id}' (source_id: {source_id_from_wrapper_header})")
                    
                    # Send RegisterClientResponse
                    response_msg = pb.RegisterClientResponse()
                    response_msg.header.message_id = wrapper.header.message_id # Acknowledge original message_id
                    response_msg.header.timestamp_utc_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
                    response_msg.header.source_id = "server"
                    response_msg.header.target_id = source_id_from_wrapper_header
                    response_msg.success = True
                    response_msg.message = f"Client '{reg_req.client_id}' registered successfully with CS."
                    
                    response_wrapper = pb.UdpPacketWrapper()
                    response_wrapper.header.CopyFrom(response_msg.header) # Use the same header for wrapper
                    response_wrapper.target_client_id_for_relay = source_id_from_wrapper_header # Direct response
                    response_wrapper.actual_message_type = "dog_system.v1.RegisterClientResponse"
                    response_wrapper.actual_message_data = response_msg.SerializeToString()
                    
                    udp_socket.sendto(response_wrapper.SerializeToString(), addr)
                    logger.info(f"Sent RegisterClientResponse to '{source_id_from_wrapper_header}' at {addr}")

                except Exception as e:
                    logger.error(f"Error processing RegisterClientRequest from {addr}: {e}", exc_info=True)


            # Relay logic: forward the original 'data' (the UdpPacketWrapper)
            target_relay_id = wrapper.target_client_id_for_relay
            if target_relay_id and target_relay_id != "server":
                if target_relay_id in client_addresses:
                    target_addr = client_addresses[target_relay_id]
                    udp_socket.sendto(data, target_addr) # Forward the raw wrapper
                    logger.debug(f"Relayed message from '{source_id_from_wrapper_header}' to '{target_relay_id}' at {target_addr}")
                else:
                    logger.warning(f"Relay target client '{target_relay_id}' not found. Packet from '{source_id_from_wrapper_header}' dropped. Known clients: {list(client_addresses.keys())}")
            # else:
                # Message is for the server itself (e.g. RegisterClientRequest) or has no valid relay target.
                # logger.debug(f"Message from '{source_id_from_wrapper_header}' for server or no relay target. Type: {wrapper.actual_message_type}")
                pass


        except ConnectionResetError: # Common on Windows
            logger.warning(f"Connection reset by remote host {addr}. Client might have closed.")
        except Exception as e:
            logger.error(f"Unexpected error in server loop: {e}", exc_info=True)

if __name__ == "__main__":
    from datetime import datetime, timezone # Needed for RegisterClientResponse timestamp
    main()