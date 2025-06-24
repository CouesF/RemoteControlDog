# RemoteControlDog/robot_dog_python/app/robot_dog_client_app.py
import socket
import time
import select
import logging

# Use relative imports based on the new structure
from . import config
# Import pb from the correct location once it's generated and path is set
from ..communication.protobuf_definitions import messages_pb2 as pb
from ..utils import helpers
from ..perception.camera_handler import CameraHandler
from ..robot_control.go2_controller import Go2Controller
from ..robot_control.robot_state import RobotState


logger = logging.getLogger(__name__)

class RobotDogClientApp:
    def __init__(self):
        config.setup_logging() # Initialize logging using config settings
        helpers.set_protobuf_definition(pb) # Provide pb to helpers

        self.rd_client_id = config.RD_CLIENT_ID
        self.ce_client_id = config.CE_CLIENT_ID
        self.cs_host = config.CS_HOST
        self.cs_port = config.CS_PORT

        self.udp_socket = None
        self.running = False
        self.frame_id_counter = 0
        self.loop_counter = 0
        self.last_status_update_time = 0

        # Protobuf enum to string mappings for logging
        self._initialize_enum_mappings()

        # Initialize modules
        self.camera_handler = CameraHandler(
            width=640, height=480, jpeg_quality=config.JPEG_QUALITY
        )
        self.robot_controller = Go2Controller(network_interface=config.UNITREE_NETWORK_INTERFACE)

        # Active session/trial IDs (can be updated by server commands if needed)
        self.current_session_id = None # Example: "sess_123"
        self.current_trial_id = None   # Example: "trial_abc"


    def _initialize_enum_mappings(self):
        self.system_action_type_names = {v: k for k, v in pb.SystemActionCommand.ActionType.items()}
        self.posture_type_names = {v: k for k, v in pb.SetPostureCommand.PostureType.items()}
        # ... any other enum mappings you need

    def _setup_network(self):
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # No explicit bind() for client sending & receiving replies
        logger.info(f"Robot Dog '{self.rd_client_id}' targeting CS at {self.cs_host}:{self.cs_port}. Will relay to '{self.ce_client_id}'.")

    def _send_registration(self):
        if not self.udp_socket:
            logger.error("UDP socket not available for sending registration.")
            return

        reg_request_payload = pb.RegisterClientRequest()
        # Use helper for header, pass current session/trial if applicable (though usually not for registration)
        reg_request_payload.header.CopyFrom(helpers.create_message_header(self.rd_client_id, "server"))
        reg_request_payload.client_type = pb.ClientType.ROBOT_DOG
        reg_request_payload.client_id = self.rd_client_id
        reg_request_payload.client_version = "0.3.0" # Updated version
        reg_request_payload.capabilities.extend(["video_JPEG", "status_updates", "sport_control_v1"])

        wrapper_reg = helpers.create_udp_wrapper(
            inner_message_bytes=reg_request_payload.SerializeToString(),
            inner_message_type_str="dog_system.v1.RegisterClientRequest",
            source_client_id=self.rd_client_id,
            relay_target_client_id="server" # Registration is for the server itself
        )
        try:
            self.udp_socket.sendto(wrapper_reg.SerializeToString(), (self.cs_host, self.cs_port))
            logger.info(f"Sent RegisterClientRequest to CS. Message ID: {reg_request_payload.header.message_id}")
        except Exception as e:
            logger.error(f"Error sending registration: {e}", exc_info=True)
            # Consider how to handle this - retry? shutdown?
            self.running = False


    def _handle_incoming_message(self, data, addr):
        try:
            wrapper = pb.UdpPacketWrapper()
            wrapper.ParseFromString(data)
            
            # Log basic wrapper info
            # logger.debug(f"Incoming: Type='{wrapper.actual_message_type}', From='{wrapper.header.source_id}', RelayTarget='{wrapper.target_client_id_for_relay}'")

            # Update current session/trial from wrapper if present (server might set these)
            if wrapper.header.HasField("session_id"): self.current_session_id = wrapper.header.session_id
            if wrapper.header.HasField("trial_id"): self.current_trial_id = wrapper.header.trial_id


            if wrapper.actual_message_type == "dog_system.v1.ControlCommand":
                cmd = pb.ControlCommand()
                cmd.ParseFromString(wrapper.actual_message_data)
                logger.info(f"ROBOT RECEIVED ControlCommand: LinX={cmd.linear_velocity_x:.2f}, LinY={cmd.linear_velocity_y:.2f}, AngZ={cmd.angular_velocity_z:.2f} (from {wrapper.header.source_id})")
                self.robot_controller.move(cmd.linear_velocity_x, cmd.linear_velocity_y, cmd.angular_velocity_z)
            
            elif wrapper.actual_message_type == "dog_system.v1.SetPostureCommand":
                cmd = pb.SetPostureCommand()
                cmd.ParseFromString(wrapper.actual_message_data)
                posture_name = self.posture_type_names.get(cmd.posture, "UNKNOWN_POSTURE")
                logger.info(f"ROBOT RECEIVED SetPostureCommand: Posture={posture_name} ({cmd.posture}) (from {wrapper.header.source_id})")
                
                if cmd.posture == pb.SetPostureCommand.PostureType.STAND:
                    logger.info("ROBOT EXECUTES: Stand up and balance")
                    if self.robot_controller.stand_up():
                        time.sleep(1.5) # Allow time for stand_up action
                        self.robot_controller.balance_stand()
                elif cmd.posture == pb.SetPostureCommand.PostureType.LIE_DOWN:
                    logger.info("ROBOT EXECUTES: Lie down")
                    self.robot_controller.stand_down()
                elif cmd.posture == pb.SetPostureCommand.PostureType.SIT: # Assuming you add SIT to your proto
                    logger.info("ROBOT EXECUTES: Sit")
                    self.robot_controller.sit()
                elif cmd.posture == pb.SetPostureCommand.PostureType.DAMP: # Assuming you add DAMP
                    logger.info("ROBOT EXECUTES: Damp")
                    self.robot_controller.damp()
                # Add other postures as needed

            elif wrapper.actual_message_type == "dog_system.v1.SystemActionCommand":
                cmd = pb.SystemActionCommand()
                cmd.ParseFromString(wrapper.actual_message_data)
                action_name = self.system_action_type_names.get(cmd.action, "UNKNOWN_ACTION")
                logger.info(f"ROBOT RECEIVED SystemActionCommand: Action={action_name} ({cmd.action}) (from {wrapper.header.source_id})")
                if cmd.action == pb.SystemActionCommand.ActionType.EMERGENCY_STOP:
                    logger.critical("ROBOT EXECUTES EMERGENCY STOP")
                    self.robot_controller.emergency_stop()
                # Add other system actions
            
            elif wrapper.actual_message_type == "dog_system.v1.RegisterClientResponse":
                response = pb.RegisterClientResponse()
                response.ParseFromString(wrapper.actual_message_data)
                logger.info(f"Received RegisterClientResponse from {wrapper.header.source_id}: Success={response.success}, Msg='{response.message}'")
                if not response.success:
                    logger.error(f"Registration failed: {response.message}. Shutting down.")
                    self.running = False # Stop the main loop if registration fails

            else:
                logger.warning(f"Unhandled message type received: {wrapper.actual_message_type} from {wrapper.header.source_id}")

        except Exception as e:
            logger.error(f"Error processing incoming message: {e}", exc_info=True)

    def _send_status_update(self):
        status_update_payload = pb.RobotStatusUpdate()
        status_update_payload.header.CopyFrom(
            helpers.create_message_header(
                self.rd_client_id, self.ce_client_id, 
                self.current_session_id, self.current_trial_id
            )
        )
        status_update_payload.battery_percent = 88.8 - (self.loop_counter / 100.0 % 20) # Example
        # TODO: Get actual pose from robot_controller if available via high-level state API
        status_update_payload.current_world_pose.position.x = 1.0 + (self.loop_counter / 10.0 % 5)
        status_update_payload.current_world_pose.position.y = 2.0
        status_update_payload.current_world_pose.orientation.w = 1.0
        
        # Get robot state from controller
        current_robot_state = self.robot_controller.get_current_state()
        status_update_payload.robot_internal_state = current_robot_state.name # Send state name

        # Map RobotState to NavigationState (simplified)
        if current_robot_state == RobotState.MOVING:
            status_update_payload.navigation_state = pb.NavigationState.NAVIGATING
        elif current_robot_state == RobotState.BALANCED_STANDING:
            status_update_payload.navigation_state = pb.NavigationState.IDLE
        elif current_robot_state == RobotState.DAMPED:
            status_update_payload.navigation_state = pb.NavigationState.IDLE
        else:
            status_update_payload.navigation_state = pb.NavigationState.UNKNOWN # Or more specific mapping

        status_update_payload.human_detection.is_present = (self.loop_counter % 20 < 10) # Example
        status_update_payload.human_detection.distance_m = 3.2
        status_update_payload.overall_system_health = pb.SystemEventSeverity.INFO # TODO: Reflect actual health

        wrapper_status = helpers.create_udp_wrapper(
            inner_message_bytes=status_update_payload.SerializeToString(),
            inner_message_type_str="dog_system.v1.RobotStatusUpdate",
            source_client_id=self.rd_client_id,
            relay_target_client_id=self.ce_client_id,
            current_session_id=self.current_session_id,
            current_trial_id=self.current_trial_id
        )
        try:
            self.udp_socket.sendto(wrapper_status.SerializeToString(), (self.cs_host, self.cs_port))
            # logger.debug(f"Sent RobotStatusUpdate (msg_id: {status_update_payload.header.message_id})")
        except Exception as e:
            logger.error(f"Error sending status update: {e}", exc_info=True)
        
        self.last_status_update_time = time.monotonic()

    def _send_video_frame(self):
        if not self.camera_handler.is_opened():
            return

        frame = self.camera_handler.read_frame()
        if frame is None:
            return

        frame_data = self.camera_handler.preprocess_frame(frame)
        if not frame_data:
            return

        video_packet_payload = pb.VideoStreamPacket()
        video_packet_payload.header.CopyFrom(
            helpers.create_message_header(
                self.rd_client_id, self.ce_client_id,
                self.current_session_id, self.current_trial_id
            )
        )
        video_packet_payload.frame_id = self.frame_id_counter
        video_packet_payload.frame_data = frame_data
        video_packet_payload.encoding_type = "JPEG"
        video_packet_payload.width = self.camera_handler.width
        video_packet_payload.height = self.camera_handler.height
        video_packet_payload.is_key_frame = True

        wrapper_video = helpers.create_udp_wrapper(
            inner_message_bytes=video_packet_payload.SerializeToString(),
            inner_message_type_str="dog_system.v1.VideoStreamPacket",
            source_client_id=self.rd_client_id,
            relay_target_client_id=self.ce_client_id,
            current_session_id=self.current_session_id,
            current_trial_id=self.current_trial_id
        )
        try:
            self.udp_socket.sendto(wrapper_video.SerializeToString(), (self.cs_host, self.cs_port))
            # logger.debug(f"Sent VideoStreamPacket frame_id: {self.frame_id_counter}")
            self.frame_id_counter += 1
        except Exception as e:
            logger.error(f"Error sending video frame: {e}", exc_info=True)


    def run(self):
        self._setup_network()
        if not self.udp_socket: # Setup failed
            logger.critical("Network setup failed. Exiting.")
            self.shutdown()
            return

        self._send_registration()
        
        self.running = True
        self.last_status_update_time = time.monotonic()

        logger.info("Robot Dog Client App running...")
        try:
            while self.running:
                # Handle Incoming Messages (Non-blocking)
                ready_to_read, _, _ = select.select([self.udp_socket], [], [], 0.005) # Small timeout
                if ready_to_read:
                    try:
                        data, addr = self.udp_socket.recvfrom(65535)
                        self._handle_incoming_message(data, addr)
                    except Exception as e: # Catch socket errors too
                        logger.error(f"Error receiving message: {e}", exc_info=True)


                current_time = time.monotonic()

                # Send Robot Status Update periodically
                if current_time - self.last_status_update_time >= config.STATUS_UPDATE_INTERVAL_S:
                    self._send_status_update()

                # Send Video Stream Packet
                if self.camera_handler.is_opened():
                    self._send_video_frame()
                
                self.loop_counter += 1
                
                # Control loop speed / video FPS
                # This sleep also dictates how responsive the robot is to commands if not using threads
                # For real-time control, command processing might need its own thread or careful timing.
                loop_sleep = 1.0 / config.VIDEO_FPS if config.VIDEO_FPS > 0 else 0.05
                time.sleep(loop_sleep)

        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt received. Shutting down...")
        except Exception as e:
            logger.error(f"Critical error in main loop: {e}", exc_info=True)
        finally:
            self.shutdown()

    def shutdown(self):
        logger.info("Robot dog client shutting down...")
        self.running = False # Signal loops to stop

        if self.robot_controller:
            logger.info("Executing robot controller shutdown sequence...")
            self.robot_controller.shutdown_sequence() # Damp motors, etc.

        if self.camera_handler:
            self.camera_handler.release()
        
        if self.udp_socket:
            self.udp_socket.close()
            logger.info("UDP socket closed.")
        
        logger.info("Robot dog client terminated.")