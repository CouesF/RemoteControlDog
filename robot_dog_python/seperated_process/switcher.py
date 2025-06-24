import time
import sys

# Core SDK components for communication
from unitree_sdk2py.core.channel import ChannelPublisher, ChannelSubscriber, ChannelFactoryInitialize
from unitree_sdk2py.utils.crc import CRC # For calculating CRC for LowCmd
from unitree_sdk2py.utils.thread import RecurrentThread # For continuous low-level command sending

# IDL for LowCmd and LowState messages (specific to Go2, Go2-W, B2, B2-W)
from unitree_sdk2py.idl.default import unitree_go_msg_dds__LowCmd_ # For Go2, Go2-W
from unitree_sdk2py.idl.default import unitree_go_msg_dds__LowState_ # For Go2, Go2-W
from unitree_sdk2py.idl.unitree_go.msg.dds_ import LowCmd_ as LowCmd_Go2 # Aliasing for clarity
from unitree_sdk2py.idl.unitree_go.msg.dds_ import LowState_ as LowState_Go2 # Aliasing for clarity

# For H1, H1-2 robots, you would use:
# from unitree_sdk2py.idl.default import unitree_hg_msg_dds__LowCmd_
# from unitree_sdk2py.idl.default import unitree_hg_msg_dds__LowState_
# from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowCmd_ as LowCmd_H1
# from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowState_ as LowState_H1


# High-level control clients
from unitree_sdk2py.comm.motion_switcher.motion_switcher_client import MotionSwitcherClient
from unitree_sdk2py.go2.sport.sport_client import SportClient # For Go2, Go2-W, B2, B2-W
# For H1, H1-2, you would use:
# from unitree_sdk2py.h1.loco.h1_loco_client import LocoClient

# Constants for motor control (example from unitree_legged_const.py)
# Assuming a 'unitree_legged_const.py' file exists or its contents are imported
# PosStopF = 2.146e9 # Example constant
# VelStopF = 16000.0 # Example constant
# LOWLEVEL = 0xFF # Example constant for low level flag

# For demonstration, we'll define minimal constants if not imported:
class Go2Const:
    PosStopF = 2.146e9
    VelStopF = 16000.0
    LOWLEVEL = 0xFF
    # Define LegID if needed for specific joints, e.g.,
    # LegID = {"FR_0": 0, "FR_1": 1, "FR_2": 2, ...}


class RobotControl:
    def __init__(self, robot_type="go2"):
        self.robot_type = robot_type
        self.msc = MotionSwitcherClient()
        self.sport_client = SportClient() if robot_type == "go2" else None # Or LocoClient for H1
        # self.loco_client = LocoClient() if robot_type == "h1" else None

        self.low_cmd = unitree_go_msg_dds__LowCmd_() # Use appropriate LowCmd_ based on robot_type
        self.low_state = None
        self.crc = CRC()
        self.lowCmdWriteThreadPtr = None
        self.low_level_active = False

        # Target positions for a simple low-level stand-up/down (Go2 specific example)
        self._targetPos_stand = [0.0, 0.67, -1.3, 0.0, 0.67, -1.3,
                                 0.0, 0.67, -1.3, 0.0, 0.67, -1.3]
        self._targetPos_damp = [0.0, 1.36, -2.65, 0.0, 1.36, -2.65,
                                -0.2, 1.36, -2.65, 0.2, 1.36, -2.65]
        self.Kp = 60.0
        self.Kd = 5.0
        self.duration_low_level_move = 500 # steps, 2ms/step = 1s
        self.low_level_percent = 0
        self.startPos_low_level = [0.0] * 12
        self.first_low_level_run = True

    def init_clients(self):
        """Initializes all necessary SDK clients."""
        self.msc.SetTimeout(5.0)
        self.msc.Init()

        if self.robot_type == "go2":
            self.sport_client.SetTimeout(5.0)
            self.sport_client.Init()
        # elif self.robot_type == "h1":
        #     self.loco_client.SetTimeout(5.0)
        #     self.loco_client.Init()

        # Low-level publisher/subscriber
        self.lowcmd_publisher = ChannelPublisher("rt/lowcmd", LowCmd_Go2) # Use LowCmd_H1 for H1
        self.lowcmd_publisher.Init()
        self.lowstate_subscriber = ChannelSubscriber("rt/lowstate", LowState_Go2) # Use LowState_H1 for H1
        self.lowstate_subscriber.Init(self._low_state_message_handler, 10)

        # Initialize low_cmd message structure
        self.low_cmd.head[0] = 0xFE
        self.low_cmd.head[1] = 0xEF
        self.low_cmd.level_flag = Go2Const.LOWLEVEL # Indicate low-level control
        self.low_cmd.gpio = 0
        for i in range(20): # Assuming 20 motors or max motor array size
            self.low_cmd.motor_cmd[i].mode = 0x01 # Set motor mode to 1 (enable)
            self.low_cmd.motor_cmd[i].q = Go2Const.PosStopF
            self.low_cmd.motor_cmd[i].kp = 0
            self.low_cmd.motor_cmd[i].dq = Go2Const.VelStopF
            self.low_cmd.motor_cmd[i].kd = 0
            self.low_cmd.motor_cmd[i].tau = 0

    def _release_current_mode(self):
        """Ensures no high-level mode is active."""
        print("Attempting to release current control mode...")
        status, result = self.msc.CheckMode()
        mode_released = False
        if result['name']:
            print(f"Current mode: {result['name']}. Attempting to release...")
            while result['name']:
                # For Go2, StandDown might help transition safely
                if self.robot_type == "go2":
                    self.sport_client.StandDown()
                # For H1, a similar 'relax' or 'zero torque' command might be used
                # elif self.robot_type == "h1":
                #     self.loco_client.ZeroTorque() # Example
                self.msc.ReleaseMode()
                time.sleep(1) # Give the robot time to process
                status, result = self.msc.CheckMode()
            mode_released = True
        else:
            print("No active mode found, proceeding.")
            mode_released = True
        print("Current control mode released.")
        return mode_released

    def _low_state_message_handler(self, msg: LowState_Go2): # Use LowState_H1 for H1
        """Callback for low state messages."""
        self.low_state = msg
        if self.first_low_level_run and self.low_level_active: # Only capture start position once at low-level start
            for i in range(12): # Assuming 12 joints for quadruped
                self.startPos_low_level[i] = self.low_state.motor_state[i].q
            self.first_low_level_run = False

    def _low_level_command_writer(self):
        """Thread target for continuous low-level command sending."""
        if self.low_state is None:
            return

        if self.low_level_active:
            # Simple linear interpolation for demonstration (e.g., stand up)
            if self.low_level_percent < 1:
                self.low_level_percent += 1.0 / self.duration_low_level_move
                self.low_level_percent = min(self.low_level_percent, 1)
                for i in range(12): # Assuming 12 controllable motors
                    # Interpolate from start position to target stand position
                    self.low_cmd.motor_cmd[i].q = (1 - self.low_level_percent) * self.startPos_low_level[i] + self.low_level_percent * self._targetPos_stand[i]
                    self.low_cmd.motor_cmd[i].dq = 0
                    self.low_cmd.motor_cmd[i].kp = self.Kp
                    self.low_cmd.motor_cmd[i].kd = self.Kd
                    self.low_cmd.motor_cmd[i].tau = 0

                self.low_cmd.crc = self.crc.Crc(self.low_cmd)
                self.lowcmd_publisher.Write(self.low_cmd)
            else:
                # Once target reached, keep holding position
                for i in range(12):
                    self.low_cmd.motor_cmd[i].q = self._targetPos_stand[i]
                    self.low_cmd.motor_cmd[i].dq = 0
                    self.low_cmd.motor_cmd[i].kp = self.Kp
                    self.low_cmd.motor_cmd[i].kd = self.Kd
                    self.low_cmd.motor_cmd[i].tau = 0
                self.low_cmd.crc = self.crc.Crc(self.low_cmd)
                self.lowcmd_publisher.Write(self.low_cmd)


    def switch_to_low_level_control(self):
        """Switches the robot to low-level control."""
        if not self._release_current_mode():
            print("Failed to release current mode. Cannot switch to low-level control.")
            return False

        print("Switching to low-level control...")
        self.low_level_active = True
        self.first_low_level_run = True # Reset to capture initial position
        self.low_level_percent = 0 # Reset interpolation
        
        # Start the low-level command sending thread
        if self.lowCmdWriteThreadPtr is None:
            self.lowCmdWriteThreadPtr = RecurrentThread(
                interval=0.002, target=self._low_level_command_writer, name="low_level_cmd_thread"
            )
            self.lowCmdWriteThreadPtr.Start()
        elif not self.lowCmdWriteThreadPtr.IsRunning():
            self.lowCmdWriteThreadPtr.Start()
        
        print("Low-level control activated. Robot will attempt to stand.")
        return True

    def switch_to_high_level_control(self, mode_name="ai"):
        """Switches the robot to high-level control."""
        # Stop low-level control thread first
        if self.lowCmdWriteThreadPtr and self.lowCmdWriteThreadPtr.IsRunning():
            print("Stopping low-level control thread...")
            self.low_level_active = False # Signal the thread to stop sending commands
            self.lowCmdWriteThreadPtr.Stop()
            self.lowCmdWriteThreadPtr.Join()
            self.lowCmdWriteThreadPtr = None
            print("Low-level control thread stopped.")

        if not self._release_current_mode(): # Release any lingering state or confirm release
            print("Failed to release current mode. Cannot switch to high-level control.")
            return False

        print(f"Switching to high-level control mode: {mode_name}...")
        if self.robot_type == "go2":
            ret = self.msc.SelectMode(mode_name)
            if ret == 0: # Assuming 0 for success
                print(f"High-level control mode '{mode_name}' activated. Robot will StandUp.")
                time.sleep(1) # Give robot time to switch mode
                self.sport_client.StandUp() # Send a common high-level command
                return True
            else:
                print(f"Failed to activate high-level control mode '{mode_name}'. Return code: {ret}")
                return False
        # elif self.robot_type == "h1":
        #     ret = self.msc.SelectMode(mode_name) # H1 might use different mode names or direct LocoClient commands
        #     if ret == 0:
        #         print(f"High-level control mode '{mode_name}' activated. Robot will StandUp.")
        #         time.sleep(1)
        #         self.loco_client.StandUp()
        #         return True
        #     else:
        #         print(f"Failed to activate high-level control mode '{mode_name}'. Return code: {ret}")
        #         return False
        return False


if __name__ == '__main__':
    print("WARNING: Ensure the robot is on a safe, clear surface before running.")
    input("Press Enter to continue...")

    if len(sys.argv) > 1:
        ChannelFactoryInitialize(0, sys.argv[1])
    else:
        ChannelFactoryInitialize(0)

    # Change 'go2' to 'h1' if you are controlling an H1 robot
    controller = RobotControl(robot_type="go2")
    controller.init_clients()

    time.sleep(2) # Allow some time for subscribers to connect and get initial state

    print("\n--- Phase 1: Switch to Low-Level Control (Robot attempts to stand) ---")
    if controller.switch_to_low_level_control():
        time.sleep(5) # Let low-level control run for a few seconds
        print("\n--- Phase 2: Switch to High-Level Control (Robot Stands Up via SportClient) ---")
        if controller.switch_to_high_level_control(mode_name="ai"): # Assuming "ai" mode for Go2
            time.sleep(5) # Let high-level control run for a few seconds
        else:
            print("Could not switch to high-level control.")
    else:
        print("Could not switch to low-level control.")

    print("\nDemonstration complete.")
    sys.exit(0)