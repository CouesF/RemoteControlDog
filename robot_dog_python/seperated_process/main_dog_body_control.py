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

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../communication")))
from dds_data_structure import MyMotionCommand

def clear_queue(q: queue.Queue):
    while not q.empty():
        q.get()

class RobotState(Enum):
    HIGH_LEVEL_DAMP = 8
    LOW_LEVEL_DAMP = 12
    HIGH_LEVEL_STAND = 5
    HIGH_LEVEL_WALK = 9
    LOW_LEVEL_STAND = 7
    LOW_LEVEL_RAISE_LEG = 10
    LOW_LEVEL_LIE_DOWN = 11

def mirror_joint_index(idx):
    # 用于l模式下关节下标整体镜像
    swap_map = {0:3, 1:4, 2:5, 3:0, 4:1, 5:2, 6:9, 7:10, 8:11, 9:6, 10:7, 11:8}
    return swap_map.get(idx, idx)

class RobotController:
    def __init__(self):
        self.current_state = RobotState.HIGH_LEVEL_DAMP
        self.command_queue = queue.Queue()
        self.state_lock = threading.Lock()
        self.running = True
        self.low_level_thread = None
        self.raise_leg_pose_init = False
        self.low_level_stop_event = threading.Event()
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
        self.stand_pos = [0.0, 0.67, -1.3] * 4
        self.lie_down_pos = [-0.35, 1.36, -2.65, 0.35, 1.36, -2.65, -0.5, 1.36, -2.65, 0.5, 1.36, -2.65]
        self.current_pose = list(self.stand_pos)
        self.last_leg_selection = 0  # 新增，保存上一次raise leg时选的腿
        print("RobotController initialized. Starting in DAMP state.")

    def dds_listener_thread(self):
        print("DDS listener thread started.")
        while self.running:
            try:
                msg = self.dds_subscriber.Read(timeout=0.1)
                if msg:
                    self.command_queue.put(msg)
            except Exception as e:
                if str(e) != "[Reader] take sample error":
                    print(f"Error in DDS listener: {e}")
            time.sleep(0.01)
        print("DDS listener thread stopped.")

    def state_machine_thread(self):
        print("State machine thread started.")
        while self.running:
            try:
                cmd: MyMotionCommand = self.command_queue.get(timeout=0.05)
                if cmd.command_type == 1:
                    # 抬腿角度指令直接丢给底层线程
                    self.command_queue.put(cmd)
                    time.sleep(0.05)
                    continue
                self.process_command(cmd)
            except queue.Empty:
                pass
            except Exception as e:
                print(f"Error in state machine: {e}")
        print("State machine thread stopped.")

    def process_command(self, cmd: MyMotionCommand):
        with self.state_lock:
            if cmd.command_type == 0: # State Switch
                try:
                    target_state = RobotState(cmd.state_enum)
                    print(f"Attempting transition from {self.current_state.name} to {target_state.name} (leg_selection={cmd.leg_selection})")
                    # 记录raise leg的腿
                    if target_state == RobotState.LOW_LEVEL_RAISE_LEG:
                        self.last_leg_selection = cmd.leg_selection
                    self.handle_state_transition(target_state)
                except ValueError:
                    print(f"Error: Invalid target state enum {cmd.state_enum}")
            elif cmd.command_type == 1 and self.current_state == RobotState.LOW_LEVEL_RAISE_LEG:
                pass
            elif cmd.command_type == 2 and self.current_state in [RobotState.HIGH_LEVEL_STAND, RobotState.HIGH_LEVEL_WALK]:
                vx, vy, vyaw = cmd.x, cmd.y, cmd.r
                if not (-2.5 <= vx <= 3.8):
                    print(f"[ERROR] vx速度超限：{vx}，允许范围[-2.5, 3.8] m/s，指令已被忽略。")
                    return
                if not (-1.0 <= vy <= 1.0):
                    print(f"[ERROR] vy速度超限：{vy}，允许范围[-1.0, 1.0] m/s，指令已被忽略。")
                    return
                if not (-4 <= vyaw <= 4):
                    print(f"[ERROR] vyaw速度超限：{vyaw}，允许范围[-4, 4] rad/s，指令已被忽略。")
                    return
                self.sport.Move(vx, vy, vyaw)
                print(f"Executing walk: x={vx}, y={vy}, r={vyaw}")

    def handle_state_transition(self, target_state: RobotState):
        # DAMP切换特判，允许随时切DAMP，DAMP本身负责分支
        if target_state in [RobotState.HIGH_LEVEL_DAMP, RobotState.LOW_LEVEL_DAMP]:
            self.transition_to_damp()
            return

        # HIGH_LEVEL_DAMP 只允许切 HIGH_LEVEL_STAND
        if self.current_state == RobotState.HIGH_LEVEL_DAMP:
            if target_state == RobotState.HIGH_LEVEL_STAND:
                self.transition_to_high_level_stand()
                self.current_state = RobotState.HIGH_LEVEL_STAND
            else:
                print(f"[ERROR] HIGH_LEVEL_DAMP 只允许切换到 HIGH_LEVEL_STAND，非法切换到 {target_state.name} 已被拒绝！")
            return

        # LOW_LEVEL_DAMP 只允许切 HIGH_LEVEL_STAND 或 HIGH_LEVEL_WALK
        if self.current_state == RobotState.LOW_LEVEL_DAMP:
            if target_state in [RobotState.HIGH_LEVEL_STAND, RobotState.HIGH_LEVEL_WALK]:
                print("[FSM] LOW_LEVEL_DAMP → HIGH_LEVEL：将先切 ai 并站立，再执行目标高层状态")
                self.stop_low_level_thread()
                self.ensure_high_level_mode()
                self.sport.StandUp()
                self.sport.BalanceStand()
                self.current_state = RobotState.HIGH_LEVEL_STAND
                print("[FSM] 已切换为 HIGH_LEVEL_STAND")
            else:
                print(f"[ERROR] LOW_LEVEL_DAMP 只允许切换到 HIGH_LEVEL_STAND/WALK，非法切换到 {target_state.name} 已被拒绝！")
            return

        # LOW_LEVEL_STAND 只允许切 LOW_LEVEL_RAISE_LEG、HIGH_LEVEL_STAND
        if self.current_state == RobotState.LOW_LEVEL_STAND:
            if target_state == RobotState.LOW_LEVEL_RAISE_LEG:
                self.transition_to_low_level_raise_leg()
                self.current_state = RobotState.LOW_LEVEL_RAISE_LEG
            elif target_state == RobotState.HIGH_LEVEL_STAND:
                self.transition_from_low_to_high()
                self.current_state = RobotState.HIGH_LEVEL_STAND
            else:
                print(f"[ERROR] LOW_LEVEL_STAND 只允许切换到 LOW_LEVEL_RAISE_LEG/HIGH_LEVEL_STAND，非法切换到 {target_state.name} 已被拒绝！")
            return

        # HIGH_LEVEL_STAND 只允许切 LOW_LEVEL_STAND
        if self.current_state == RobotState.HIGH_LEVEL_STAND:
            if target_state == RobotState.LOW_LEVEL_STAND:
                self.transition_from_high_to_low()
                self.current_state = RobotState.LOW_LEVEL_STAND
            else:
                print(f"[ERROR] HIGH_LEVEL_STAND 只允许切换到 LOW_LEVEL_STAND，非法切换到 {target_state.name} 已被拒绝！")
            return

        # LOW_LEVEL_RAISE_LEG 只允许切 LOW_LEVEL_STAND
        if self.current_state == RobotState.LOW_LEVEL_RAISE_LEG:
            if target_state == RobotState.LOW_LEVEL_STAND:
                self.transition_to_low_level_stand()
                self.current_state = RobotState.LOW_LEVEL_STAND
            else:
                print(f"[ERROR] LOW_LEVEL_RAISE_LEG 只允许切换到 LOW_LEVEL_STAND，非法切换到 {target_state.name} 已被拒绝！")
            return

        # 兜底
        print(f"[ERROR] 当前状态 {self.current_state.name} 不允许切换到 {target_state.name}，操作被拒绝！")

    def transition_to_damp(self):
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
        self.ensure_high_level_mode()
        self.sport.BalanceStand()
        self.current_pose = list(self.stand_pos)
        print("State is now HIGH_LEVEL_STAND.")
        clear_queue(self.command_queue)

    def transition_to_low_level_stand(self):
        print("Transitioning to LOW_LEVEL_STAND...")
        self.stop_low_level_thread()
        self.ensure_low_level_mode()
        # ------ 重点：恢复姿态步骤需按上次是哪条腿做镜像 ------
        if self.current_state == RobotState.LOW_LEVEL_RAISE_LEG:
            print("[LowLevelRaiseLeg → Stand] 分阶段恢复腿部姿态")
            pose_buffer = self.current_pose[:]
            stand_pos = self.stand_pos
            # 决定用哪组关节顺序
            use_mirror = (self.last_leg_selection == 1)
            # 恢复顺序下标
            default_indices = [0,1,2,9,10,11]
            indices = [mirror_joint_index(i) if use_mirror else i for i in default_indices]
            # 恢复流程和原本一致，只是index换掉
            def interpolate_selected_joints(start, end, joint_indices, duration_ms):
                steps = int(duration_ms / 2)
                for step in range(steps):
                    alpha = step / steps
                    current = start[:]
                    for j in joint_indices:
                        current[j] = (1 - alpha) * start[j] + alpha * end[j]
                    for i in range(12):
                        self.low_cmd.motor_cmd[i].mode = 0x01
                        self.low_cmd.motor_cmd[i].q = current[i]
                        self.low_cmd.motor_cmd[i].dq = 0
                        self.low_cmd.motor_cmd[i].kp = 100.0
                        self.low_cmd.motor_cmd[i].kd = 8.0
                        self.low_cmd.motor_cmd[i].tau = 0
                    self.low_cmd.crc = self.crc.Crc(self.low_cmd)
                    self.low_cmd_publisher.Write(self.low_cmd)
                    time.sleep(0.002)
            # 分步插值（index已经镜像或原样）
            tmp = pose_buffer[:]; tmp[indices[0]] = stand_pos[indices[0]]
            interpolate_selected_joints(pose_buffer, tmp, [indices[0]], 300)
            tmp2 = tmp[:]; tmp2[indices[1]] = stand_pos[indices[1]]
            interpolate_selected_joints(tmp, tmp2, [indices[1]], 300)
            tmp3 = tmp2[:]; tmp3[indices[2]] = stand_pos[indices[2]]
            interpolate_selected_joints(tmp2, tmp3, [indices[2]], 300)
            tmp4 = tmp3[:]; tmp4[indices[3]] = stand_pos[indices[3]]
            interpolate_selected_joints(tmp3, tmp4, [indices[3]], 400)
            tmp5 = tmp4[:]; tmp5[indices[4]] = stand_pos[indices[4]]
            interpolate_selected_joints(tmp4, tmp5, [indices[4]], 400)
            tmp6 = tmp5[:]; tmp6[indices[5]] = stand_pos[indices[5]]
            interpolate_selected_joints(tmp5, tmp6, [indices[5]], 400)
            self.current_pose = list(stand_pos)
        else:
            self.current_pose = list(self.stand_pos)
        self.start_low_level_thread(self.maintain_static_pose)
        print("State is now LOW_LEVEL_STAND.")
        clear_queue(self.command_queue)

    def transition_to_low_level_raise_leg(self):
        print("Transitioning to LOW_LEVEL_RAISE_LEG...")
        self.stop_low_level_thread()
        # 重点：带上last_leg_selection参数
        self.start_low_level_thread(lambda: self.maintain_raise_leg_pose(self.last_leg_selection))
        print("State is now LOW_LEVEL_RAISE_LEG.")
        clear_queue(self.command_queue)

    def transition_from_high_to_low(self):
        print("Transitioning from HIGH_LEVEL to LOW_LEVEL...")
        self.sport.StandUp()
        time.sleep(0.6)
        self.stop_low_level_thread()
        self.ensure_low_level_mode()
        self.current_pose = list(self.stand_pos)
        self.start_low_level_thread(self.maintain_static_pose)
        print("Transition complete to LOW_LEVEL_STAND.")
        clear_queue(self.command_queue)

    def transition_from_low_to_high(self):
        print("Transitioning from LOW_LEVEL to HIGH_LEVEL...")
        self.stop_low_level_thread()
        _, result = self.msc.CheckMode()
        print(f"[DEBUG] Before interpolate_pose, mode is: {result.get('name')}")
        self.interpolate_pose(self.current_pose, self.lie_down_pos, 1500)
        self.current_pose = list(self.lie_down_pos)
        time.sleep(0.5)
        self.ensure_high_level_mode()
        self.sport.BalanceStand()
        self.current_pose = list(self.stand_pos)
        print("Transition complete to HIGH_LEVEL_STAND.")
        clear_queue(self.command_queue)

    def ensure_high_level_mode(self):
        print("Ensuring high-level (AI) mode...")
        _, result = self.msc.CheckMode()
        if result.get("name") != "ai":
            self.msc.SelectMode("ai")
            time.sleep(1.0)
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
        print(f"Maintaining static pose: {self.current_pose}")
        while not self.low_level_stop_event.is_set():
            self.send_low_level_pose_cmd(self.current_pose)
            time.sleep(0.002)

    def maintain_raise_leg_pose(self, leg_selection):
        self.raise_leg_pose_init = True
        self.interpolate_pose(self.current_pose, self.stand_pos, 1500)
        self.current_pose = list(self.stand_pos)
        print(f"[LowLevelRaiseLeg] 开始执行{'左' if leg_selection==1 else '右'}前腿抬腿流程")
        def clamp_warning(index, new_val, min_val, max_val):
            if new_val < min_val or new_val > max_val:
                print(f"[Warning] 超过限制值，关节 {index} 的目标角度 {new_val:.2f} 超出范围 [{min_val}, {max_val}]，忽略本次输入")
                return False
            return True
        self.interpolate_pose(self.current_pose, self.stand_pos, 1500)
        self.current_pose = list(self.stand_pos)

        # 下标做镜像处理
        use_mirror = (leg_selection == 1)
        # 动作流程：所有涉及下标全镜像
        step1 = self.stand_pos[:]
        step1[mirror_joint_index(11) if use_mirror else 11] -= 0.3

        idx_9 = mirror_joint_index(9) if use_mirror else 9
        if use_mirror:
            step1[idx_9] -= 0.3    # 镜像后6号关节是-=0.3
        else:
            step1[idx_9] += 0.3    # 原逻辑

        self.interpolate_pose(self.current_pose, step1, 650)

        step2 = step1[:]
        step2[mirror_joint_index(2) if use_mirror else 2] -= 0.8
        self.interpolate_pose(step1, step2, 250)
        step3 = step2[:]
        idx = mirror_joint_index(0) if use_mirror else 0
        if use_mirror:
            step3[idx] += 0.8   # 左腿镜像，3号关节抬起变为+0.8
        else:
            step3[idx] -= 0.8   # 右腿/原本逻辑，-0.8
        self.interpolate_pose(step2, step3, 300)
        step4 = step3[:]
        step4[mirror_joint_index(1) if use_mirror else 1] -= 1.0
        self.interpolate_pose(step3, step4, 250)
        step5 = step4[:]
        step5[mirror_joint_index(2) if use_mirror else 2] = self.stand_pos[mirror_joint_index(2) if use_mirror else 2]
        self.interpolate_pose(step4, step5, 250)

        pose_buffer = step5[:]
        self.current_pose = list(pose_buffer)
        # 高刚度腿下标镜像
        default_indices = [0,1,2,3,4,5,9,10,11]
        high_kp = [100.0]*12
        high_kd = [8.0]*12
        for i in default_indices:
            idx = mirror_joint_index(i) if use_mirror else i
            high_kp[idx] = 160.0
            high_kd[idx] = 10.0
        self.raise_leg_pose_init = False 

        def maintain_dynamic():
            while not self.low_level_stop_event.is_set():
                for j in range(12):
                    self.low_cmd.motor_cmd[j].mode = 0x01
                    self.low_cmd.motor_cmd[j].q = pose_buffer[j]
                    self.low_cmd.motor_cmd[j].dq = 0
                    self.low_cmd.motor_cmd[j].kp = high_kp[j]
                    self.low_cmd.motor_cmd[j].kd = high_kd[j]
                    self.low_cmd.motor_cmd[j].tau = 0
                self.low_cmd.crc = self.crc.Crc(self.low_cmd)
                self.low_cmd_publisher.Write(self.low_cmd)
                time.sleep(0.002)

        def receive_angle_command():
            print("[LowLevelRaiseLeg] 开始监听DDS角度指令...")
            while not self.low_level_stop_event.is_set():
                # 插值阶段主动跳过，保护姿态
                if self.raise_leg_pose_init:
                    time.sleep(0.02)
                    continue
                try:
                    cmd: MyMotionCommand = self.command_queue.get(timeout=0.05)
                    if cmd.command_type == 1:
                        # 重点：angle1/2控制关节下标做镜像
                        joint1_idx = mirror_joint_index(1) if use_mirror else 1
                        joint2_idx = mirror_joint_index(2) if use_mirror else 2
                        target1 = cmd.angle1
                        target2 = cmd.angle2
                        if not clamp_warning(joint1_idx, target1, -1.5, 3.4) or not clamp_warning(joint2_idx, target2, -2.7, -0.8):
                            continue
                        while (abs(pose_buffer[joint1_idx] - target1) > 0.05 or
                            abs(pose_buffer[joint2_idx] - target2) > 0.05) and not self.low_level_stop_event.is_set():
                            if pose_buffer[joint1_idx] < target1:
                                pose_buffer[joint1_idx] = min(pose_buffer[joint1_idx] + 0.1, target1)
                            else:
                                pose_buffer[joint1_idx] = max(pose_buffer[joint1_idx] - 0.1, target1)
                            if pose_buffer[joint2_idx] < target2:
                                pose_buffer[joint2_idx] = min(pose_buffer[joint2_idx] + 0.1, target2)
                            else:
                                pose_buffer[joint2_idx] = max(pose_buffer[joint2_idx] - 0.1, target2)
                            time.sleep(0.05)
                except queue.Empty:
                    continue

        thread_hold = threading.Thread(target=maintain_dynamic)
        thread_cmd = threading.Thread(target=receive_angle_command)
        thread_hold.start()
        thread_cmd.start()
        thread_cmd.join()
        thread_hold.join()
        self.current_pose = list(pose_buffer)
        print("[LowLevelRaiseLeg] 抬腿线程正常退出，current_pose已同步，控制权已交还主状态机")

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
        steps = int(duration_ms / 2)
        for step in range(steps):
            if self.low_level_stop_event.is_set():
                print("[interpolate_pose] Interrupted by stop_event!")
                return
            alpha = min(1.0, step / steps)
            q_interp = [(1 - alpha) * s + alpha * e for s, e in zip(start, end)]
            self.send_low_level_pose_cmd(q_interp)
            time.sleep(0.002)
        self.send_low_level_pose_cmd(end)
        self.current_pose = list(end)

    def run(self):
        self.transition_to_high_level_damp()
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
        print("Maintaining low-level damp...")
        while not self.low_level_stop_event.is_set():
            self.send_low_level_damp_cmd()
            time.sleep(0.01)

    def shutdown(self):
        self.running = False
        self.stop_low_level_thread()
        try:
            print("Attempting final shutdown damp...")
            self.transition_to_damp()
        except Exception as e:
            print(f"Could not send final damp command: {e}")

if __name__ == '__main__':
    print("Starting Robot Dog Main Body Controller")
    controller = RobotController()
    controller.run()