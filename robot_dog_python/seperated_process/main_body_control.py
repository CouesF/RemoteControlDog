import time
import sys
import os
import threading
import queue
from enum import Enum
from dataclasses import dataclass

from unitree_sdk2py.core.channel import (ChannelPublisher, ChannelFactoryInitialize, ChannelSubscriber)
from unitree_sdk2py.idl.unitree_go.msg.dds_ import LowCmd_
from unitree_sdk2py.idl.default import unitree_go_msg_dds__LowCmd_
from unitree_sdk2py.utils.crc import CRC
from unitree_sdk2py.comm.motion_switcher.motion_switcher_client import MotionSwitcherClient
from unitree_sdk2py.go2.sport.sport_client import SportClient
from cyclonedds.idl import IdlStruct

# --- Import custom DDS structure ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../communication")))
from dds_data_structure import MyMotionCommand

def clear_queue(q: queue.Queue):
    """Clears all items from a queue."""
    while not q.empty():
        q.get()


# --- State Machine Definition ---
class RobotState(Enum):
    HIGH_LEVEL_DAMP = 8
    LOW_LEVEL_DAMP = 12
    HIGH_LEVEL_STAND = 5
    HIGH_LEVEL_WALK = 9
    LOW_LEVEL_STAND = 7
    LOW_LEVEL_RAISE_LEG = 10
    LOW_LEVEL_LIE_DOWN = 11

class RobotController:
    def __init__(self):
        # --- State and Threading ---
        self.current_state = RobotState.HIGH_LEVEL_DAMP
        self.command_queue = queue.Queue()
        self.state_lock = threading.Lock()
        self.running = True
        self.low_level_thread = None
        self.low_level_stop_event = threading.Event()

        # --- Robot Hardware/SDK Interfaces ---
        ChannelFactoryInitialize(0, "enP8p1s0")
        self.msc = MotionSwitcherClient()
        self.msc.Init()
        self.sport = SportClient()
        self.sport.Init()
        self.low_cmd_publisher = ChannelPublisher("rt/lowcmd", LowCmd_)
        self.low_cmd_publisher.Init()
        self.dds_subscriber = ChannelSubscriber("rt/my_motion_command", MyMotionCommand)
        self.dds_subscriber.Init()
        
        self.low_cmd = unitree_go_msg_dds__LowCmd_()
        self.crc = CRC()

        # --- Robot Pose Definitions ---
        self.stand_pos = [0.0, 0.67, -1.3] * 4
        self.lie_down_pos = [-0.35, 1.36, -2.65, 0.35, 1.36, -2.65, -0.5, 1.36, -2.65, 0.5, 1.36, -2.65]
        self.current_pose = list(self.stand_pos) # Initialize with a default

        print("RobotController initialized. Starting in DAMP state.")

    def dds_listener_thread(self):
        """Listens for incoming DDS commands and puts them in a queue."""
        print("DDS listener thread started.")
        while self.running:
            try:
                msg = self.dds_subscriber.Read(timeout=0.1) # Timeout to allow checking self.running
                if msg:
                    print(f"Received DDS command: type={msg.command_type}, state={msg.state_enum}")
                    self.command_queue.put(msg)
            except Exception as e:
                print(f"Error in DDS listener: {e}")
            time.sleep(0.01)
        print("DDS listener thread stopped.")

    def state_machine_thread(self):
        """The core state machine logic."""
        print("State machine thread started.")
        while self.running:
            try:
                cmd: MyMotionCommand = self.command_queue.get(timeout=0.1)
                self.process_command(cmd)
            except queue.Empty:
                # No new command, continue in current state
                pass
            except Exception as e:
                print(f"Error in state machine: {e}")
        print("State machine thread stopped.")

    def process_command(self, cmd: MyMotionCommand):
        with self.state_lock:
            if cmd.command_type == 0: # State Switch
                try:
                    target_state = RobotState(cmd.state_enum)
                    print(f"Attempting transition from {self.current_state.name} to {target_state.name}")
                    self.handle_state_transition(target_state)
                except ValueError:
                    print(f"Error: Invalid target state enum {cmd.state_enum}")
            elif cmd.command_type == 1 and self.current_state == RobotState.LOW_LEVEL_RAISE_LEG:
                # This command is now passed to the queue for the leg control thread
                # TODO: 应该已经在对应线程了
                pass 
            elif cmd.command_type == 2 and self.current_state in [RobotState.HIGH_LEVEL_STAND, RobotState.HIGH_LEVEL_WALK]:
                self.sport.Move(cmd.x, cmd.y, cmd.r, False) # TODO：修改成实际接口(test)
                print(f"Executing walk: x={cmd.x}, y={cmd.y}, r={cmd.r}")

    def handle_state_transition(self, target_state: RobotState):
        # --- Context-aware transition to DAMP ---
        if target_state in [RobotState.HIGH_LEVEL_DAMP, RobotState.LOW_LEVEL_DAMP]:
            self.transition_to_damp()
            return

        # --- Transitions from DAMP states ---
        if self.current_state == RobotState.HIGH_LEVEL_DAMP:
            if target_state == RobotState.HIGH_LEVEL_STAND:
                self.transition_to_high_level_stand()
                self.current_state = RobotState.HIGH_LEVEL_STAND
            else:
                print(f"Invalid transition from HIGH_LEVEL_DAMP to {target_state.name}")

        elif self.current_state == RobotState.LOW_LEVEL_DAMP:
            if target_state == RobotState.LOW_LEVEL_STAND:
                self.transition_to_low_level_stand()
                self.current_state = RobotState.LOW_LEVEL_STAND
            else:
                print(f"Invalid transition from LOW_LEVEL_DAMP to {target_state.name}")

        # --- Transitions from active states ---
        elif self.current_state == RobotState.LOW_LEVEL_STAND:
            if target_state == RobotState.LOW_LEVEL_RAISE_LEG:
                self.transition_to_low_level_raise_leg() #TODO
                self.current_state = RobotState.LOW_LEVEL_RAISE_LEG
            elif target_state == RobotState.HIGH_LEVEL_STAND:
                self.transition_from_low_to_high()
                self.current_state = RobotState.HIGH_LEVEL_STAND

        elif self.current_state == RobotState.HIGH_LEVEL_STAND:
            if target_state == RobotState.LOW_LEVEL_STAND:
                self.transition_from_high_to_low()
                self.current_state = RobotState.LOW_LEVEL_STAND
        
        elif self.current_state == RobotState.LOW_LEVEL_RAISE_LEG:
            if target_state == RobotState.LOW_LEVEL_STAND:
                self.transition_to_low_level_stand() #TODO
                self.current_state = RobotState.LOW_LEVEL_STAND

    # --- Transition Implementations ---

    def transition_to_damp(self):
        """Context-aware damp transition."""
        if self.current_state in [RobotState.HIGH_LEVEL_STAND, RobotState.HIGH_LEVEL_WALK, RobotState.HIGH_LEVEL_DAMP]:
            self.transition_to_high_level_damp()
        elif self.current_state in [RobotState.LOW_LEVEL_STAND, RobotState.LOW_LEVEL_RAISE_LEG, RobotState.LOW_LEVEL_DAMP]:
            self.transition_to_low_level_damp()
        else:
            print(f"Unknown context for DAMP from state {self.current_state.name}. Defaulting to HIGH_LEVEL_DAMP.")
            self.transition_to_high_level_damp()
        clear_queue(self.command_queue)

    def transition_to_high_level_damp(self):
        print("Transitioning to HIGH_LEVEL_DAMP...")
        self.stop_low_level_thread()
        self.ensure_high_level_mode()
        self.sport.Damp()
        self.current_state = RobotState.HIGH_LEVEL_DAMP
        print("State is now HIGH_LEVEL_DAMP.")
        clear_queue(self.command_queue)

    def transition_to_low_level_damp(self):
        print("Transitioning to LOW_LEVEL_DAMP...")
        self.stop_low_level_thread()
        self.ensure_low_level_mode()
        self.start_low_level_thread(self.maintain_low_level_damp)
        self.current_state = RobotState.LOW_LEVEL_DAMP
        print("State is now LOW_LEVEL_DAMP.")
        clear_queue(self.command_queue)

    def transition_to_high_level_stand(self):
        print("Transitioning to HIGH_LEVEL_STAND...")
        self.stop_low_level_thread()
        self.ensure_high_level_mode() # 是否每次都要ensure，因为感觉系统返回会有延迟一般。
        self.sport.StandUp()
        self.current_pose = list(self.stand_pos)
        print("State is now HIGH_LEVEL_STAND.")
        clear_queue(self.command_queue)

    def transition_to_low_level_stand(self):
        print("Transitioning to LOW_LEVEL_STAND...")
        self.stop_low_level_thread()
        self.ensure_low_level_mode() # TODO: 测试是否过于冗余。
        self.current_pose = list(self.stand_pos)
        self.start_low_level_thread(self.maintain_static_pose) # 这里相当于直接切stand pose，没有差值。
        print("State is now LOW_LEVEL_STAND.")
        clear_queue(self.command_queue)
        
    def transition_to_low_level_raise_leg(self):
        print("Transitioning to LOW_LEVEL_RAISE_LEG...")
        self.stop_low_level_thread() #TODO 如果本来是low stand，停止，是否来得及切到抬腿stand。
        # self.ensure_low_level_mode() # Should already be in it
        self.start_low_level_thread(self.maintain_raise_leg_pose)
        print("State is now LOW_LEVEL_RAISE_LEG.")
        clear_queue(self.command_queue)

    def transition_from_high_to_low(self):
        print("Transitioning from HIGH_LEVEL to LOW_LEVEL...")
        # This is a complex process. For now, we just switch modes.
        # A more robust implementation would send low-level commands during the switch.
        # TODO: 需要测试
        self.sport.StandUp()
        time.sleep(0.6) # Settle
        self.stop_low_level_thread()
        self.ensure_low_level_mode()
        self.current_pose = list(self.stand_pos)
        self.start_low_level_thread(self.maintain_static_pose)
        print("Transition complete to LOW_LEVEL_STAND.")
        clear_queue(self.command_queue)

    def transition_from_low_to_high(self):
        print("Transitioning from LOW_LEVEL to HIGH_LEVEL...")
        self.stop_low_level_thread()
        # 1. Go to lie down pose in low-level
        self.interpolate_pose(self.current_pose, self.lie_down_pos, 1500)
        self.current_pose = list(self.lie_down_pos)
        time.sleep(0.5) # Settle
        # 2. Switch to high-level mode
        self.ensure_high_level_mode()
        # 3. Stand up in high-level mode
        self.sport.StandUp()
        self.current_pose = list(self.stand_pos)
        print("Transition complete to HIGH_LEVEL_STAND.")
        clear_queue(self.command_queue)

    # --- Mode Switching Helpers ---

    def ensure_high_level_mode(self):
        print("Ensuring high-level (AI) mode...")
        _, result = self.msc.CheckMode()
        if result.get("name") != "ai":
            self.msc.SelectMode("ai")
            time.sleep(1.0) # Give time for the switch
            print("Switched to AI mode.")
        else:
            print("Already in AI mode.")

    def ensure_low_level_mode(self):
        print("Ensuring low-level mode...")
        
        while True:
            self.msc.ReleaseMode()
            time.sleep(0.01)
            status, result = self.msc.CheckMode()
            if result.get("name", "") == "":
                print("Switched to low-level mode.")
                break
            print("Waiting for mode release...")

    # --- Low-Level Control Threads ---

    def start_low_level_thread(self, target_func):
        if self.low_level_thread and self.low_level_thread.is_alive():
            print("Warning: A low-level thread is already running. Stopping it first.")
            self.stop_low_level_thread()
        
        self.low_level_stop_event.clear()
        self.low_level_thread = threading.Thread(target=target_func)
        self.low_level_thread.start()
        print(f"Started low-level thread: {target_func.__name__}")

    def stop_low_level_thread(self):
        if self.low_level_thread and self.low_level_thread.is_alive():
            self.low_level_stop_event.set()
            self.low_level_thread.join(timeout=1.0)
            print("Stopped low-level thread.")
        self.low_level_thread = None

    def maintain_static_pose(self):
        """Maintains the robot's current_pose."""
        print(f"Maintaining static pose: {self.current_pose}")
        while not self.low_level_stop_event.is_set():
            self.send_low_level_pose_cmd(self.current_pose)
            time.sleep(0.002)

    def maintain_raise_leg_pose(self):
        """Maintains pose while allowing one leg to be controlled via DDS."""
        print("Maintaining raise leg pose...")
        local_pose = list(self.current_pose)
        # TODO: 初始化，肩关节等抬腿初始位置。
        # TODO: 前面已经停止low stand指令，需要快速衔接上stand-然后转抬腿。
        
        while not self.low_level_stop_event.is_set():

            try:
                cmd: MyMotionCommand = self.command_queue.get_nowait()
                if cmd.command_type == 1: # Leg control
                    # Basic implementation: directly set angles
                    # A better one would use interpolation 
                    # TODO: interpolation
                    leg_idx = cmd.leg_selection
                    base_joint_idx = leg_idx * 3
                    
                    # WARNING: This is a simplified example.
                    # TODO 这里必须改。需要有阈值。
                    # Real implementation needs safety checks and smooth interpolation.
                    local_pose[base_joint_idx + 1] = cmd.angle1
                    local_pose[base_joint_idx + 2] = cmd.angle2
            except queue.Empty:
                pass
            
            self.send_low_level_pose_cmd(local_pose)
            time.sleep(0.002)

    def send_low_level_pose_cmd(self, pose, kp=100.0, kd=8.0):
        for i in range(12):
            self.low_cmd.motor_cmd[i].mode = 0x01
            self.low_cmd.motor_cmd[i].q = pose[i]
            self.low_cmd.motor_cmd[i].dq = 0.0
            self.low_cmd.motor_cmd[i].kp = kp
            self.low_cmd.motor_cmd[i].kd = kd
            self.low_cmd.motor_cmd[i].tau = 0.0
        self.low_cmd.crc = self.crc.Crc(self.low_cmd)
        self.low_cmd_publisher.Write(self.low_cmd)

    def send_low_level_damp_cmd(self):
        for i in range(12):
            self.low_cmd.motor_cmd[i].mode = 0x01
            self.low_cmd.motor_cmd[i].q = 0.0
            self.low_cmd.motor_cmd[i].dq = 0.0
            self.low_cmd.motor_cmd[i].kp = 0.0
            self.low_cmd.motor_cmd[i].kd = 2.0
            self.low_cmd.motor_cmd[i].tau = 0.0
        self.low_cmd.crc = self.crc.Crc(self.low_cmd)
        self.low_cmd_publisher.Write(self.low_cmd)

    def interpolate_pose(self, start, end, duration_ms): 
        print(f"Interpolating pose over {duration_ms}ms")
        steps = int(duration_ms / 2) # 2ms per step
        for step in range(steps):
            alpha = min(1.0, step / steps)
            q_interp = [(1 - alpha) * s + alpha * e for s, e in zip(start, end)]
            self.send_low_level_pose_cmd(q_interp)
            time.sleep(0.002)
        self.send_low_level_pose_cmd(end) # Ensure final pose is sent
        self.current_pose = list(end)

    def run(self):
        """Starts all threads and runs the controller."""
        self.transition_to_high_level_damp() # Start in a safe, high-level damp state

        main_sm_thread = threading.Thread(target=self.state_machine_thread)
        dds_thread = threading.Thread(target=self.dds_listener_thread)

        main_sm_thread.start()
        dds_thread.start()

        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Shutdown requested.")
        
        self.shutdown()
        main_sm_thread.join()
        dds_thread.join()
        print("All threads terminated. Exiting.")

    def maintain_low_level_damp(self):
        """Continuously sends low-level damp commands."""
        print("Maintaining low-level damp...")
        while not self.low_level_stop_event.is_set():
            self.send_low_level_damp_cmd()
            time.sleep(0.01) # Can be a bit slower than pose control

    def shutdown(self):
        self.running = False
        self.stop_low_level_thread()
        # Attempt a final damp command based on the last known mode
        try:
            print("Attempting final shutdown damp...")
            self.transition_to_damp()
        except Exception as e:
            print(f"Could not send final damp command: {e}")


if __name__ == '__main__':
    print("Starting Robot Dog Main Body Controller")
    controller = RobotController()
    controller.run()
