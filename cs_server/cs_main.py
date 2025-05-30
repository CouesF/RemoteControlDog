import socket
# Make sure messages_pb2.py is in the same directory or Python path
import messages_pb2 as pb
from dotenv import load_dotenv
import os

# Configuration
# Load environment variables from .env file in the parent directory
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env') # Added
load_dotenv(dotenv_path=dotenv_path) # Added

# Configuration from .env
CS_HOST = os.getenv("CS_LISTEN_HOST", "0.0.0.0")         # Changed
CS_PORT = int(os.getenv("CS_LISTEN_PORT", 9000))     # Changed and cast to int
BUFFER_SIZE = 65535

# In-memory store for client_id -> (ip, port)
client_addresses = {}

def main():
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        udp_socket.bind((CS_HOST, CS_PORT))
        print(f"CS: Cloud Server listening on {CS_HOST}:{CS_PORT}")
    except Exception as e:
        print(f"CS: Error binding socket: {e}")
        return

    while True:
        try:
            data, addr = udp_socket.recvfrom(BUFFER_SIZE)
            print(f"CS: Received {len(data)} bytes from {addr}")

            wrapper = pb.UdpPacketWrapper()
            try:
                wrapper.ParseFromString(data)
            except Exception as e:
                print(f"CS: Failed to parse UdpPacketWrapper from {addr}: {e}")
                continue

            source_id = wrapper.header.source_id
            target_relay_id = wrapper.target_client_id_for_relay

            # Update client address for the source
            if source_id and source_id != "server": # Don't store server as a routable client
                if source_id not in client_addresses or client_addresses[source_id] != addr:
                    print(f"CS: Registered/Updated {source_id} -> {addr}")
                    client_addresses[source_id] = addr
            
            # If the message is a RegisterClientRequest, we can optionally send a response
            # For now, we just note the client's address from the wrapper.
            # The actual_message_type could be checked here for specific server-side processing
            # if wrapper.actual_message_type == "dog_system.v1.RegisterClientRequest":
            #     reg_req = pb.RegisterClientRequest()
            #     reg_req.ParseFromString(wrapper.actual_message_data)
            #     print(f"CS: Received RegisterClientRequest from {reg_req.client_id} ({addr})")
                # Potentially send RegisterClientResponse back to addr

            # Relay logic
            if target_relay_id and target_relay_id != "server": # Don't relay messages addressed to server
                if target_relay_id in client_addresses:
                    target_addr = client_addresses[target_relay_id]
                    udp_socket.sendto(data, target_addr) # Forward the original data
                    # print(f"CS: Relayed message from {source_id} ({addr}) to {target_relay_id} ({target_addr})")
                else:
                    print(f"CS: Warning - Target client '{target_relay_id}' not found in address map. Packet from {source_id} dropped.")
            # else:
                # print(f"CS: Message from {source_id} is for server or has no relay target. (Type: {wrapper.actual_message_type})")


        except ConnectionResetError:
            # Common on Windows if a client disconnects abruptly
            print(f"CS: Connection reset by remote host {addr}. Might be a client that closed.")
        except Exception as e:
            print(f"CS: Error in server loop: {e}")

if __name__ == "__main__":
    main()