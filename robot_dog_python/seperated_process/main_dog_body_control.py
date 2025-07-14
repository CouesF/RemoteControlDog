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
from dds_data_structure import MyMotionCommand, RobotLog
import numpy as np

# 日志事件编号字典（本地可用，不影响DDS，仅 print 辅助查阅）
ROBOT_EVENT_CODE = {
    0: "初始化完成",
    1: "启动主控线程",
    2: "DDS 通道初始化成功",
    3: "收到新指令",
    4: "系统正常退出",

    10: "当前是HIGH_LEVEL_DAMP",
    11: "当前是LOW_LEVEL_DAMP",
    12: "当前是HIGH_LEVEL_STAND",
    13: "当前是LOW_LEVEL_STAND",
    14: "当前是LOW_LEVEL_RAISE_LEG",
    16: "当前是HIGH_LEVEL_STAND_DOWN",
    17: "当前是LOW_LEVEL_LIE_DOWN",

    20: "执行 StandUp",
    21: "执行 StandDown",
    22: "执行 BalanceStand",
    23: "执行 Damp",

    30: "抬腿流程开始",
    31: "抬腿流程结束",
    32: "接收并处理抬腿角度指令",
    33: "抬腿坐标不可达",
    34: "抬腿关节超限",

    90: "非法状态切换（已拒绝）",
    91: "速度超限（已拒绝）",
    92: "DDS 指令解析异常",
    93: "低层线程未正常停止",
    94: "未识别的状态机异常",
    95: "运动模式切换失败",
    96: "退出时尝试切阻尼失败",
    97: "未知命令类型（忽略）",
    98: "系统内部异常",
    99: "CRITICAL ERROR",
}

def ik_leg(xC: float, yC: float, side: str = "L"):
    """
    求2-link机械臂逆运动学解，输出每组(a, b)，分别为第一个关节绝对角度（a），末端方向角度（b）。
    带角度限位，单位弧度。
    返回: [{'a_rad': a, 'b_rad': b, 'a_deg': ..., 'b_deg': ...}, ...]
    """
    import numpy as np
    side = side.upper()
    if side not in ("L", "R"):
        raise ValueError("side 只能是 'L' 或 'R'")

    # 镜像处理
    dx = -xC if side == "R" else xC
    dy = yC

    results = []
    R = np.hypot(dx, dy)
    if abs(R) > 2:
        return results

    phi = np.arctan2(dy, dx)

    # 限位，单位为弧度
    θ1_min, θ1_max = np.deg2rad([-90, 100])
    θ2_min, θ2_max = np.deg2rad([48, 156])

    for sign in [+1, -1]:
        try:
            acos_val = np.arccos(R / 2)
        except ValueError:
            continue

        c = phi + sign * acos_val
        cos_c = np.cos(c)
        sin_c = np.sin(c)
        cos_a = dx - cos_c
        sin_a = -(dy - sin_c)

        norm = np.hypot(cos_a, sin_a)
        if norm == 0:
            continue
        cos_a /= norm
        sin_a /= norm

        a = np.arctan2(sin_a, cos_a)
        b = a + c

        # 限位过滤：a是θ1（shoulder），b-a是θ2（elbow）
        θ2 = b - a
        if (θ1_min <= a <= θ1_max) and (θ2_min <= θ2 <= θ2_max):
            results.append({
                'a_rad': a,
                'b_rad': b,
                'a_deg': np.degrees(a),
                'b_deg': np.degrees(b),
            })

    return results

def map_unit_circle_to_radius2(x_in, y_in):
    """
    直接将输入 (x_in, y_in) 映射到 (2 * x_in, 2 * y_in)
    """
    return -1.6 * x_in, 1.6 * y_in


def clear_queue(q: queue.Queue):
    while not q.empty():
        q.get()

class RobotState(Enum):
    HIGH_LEVEL_DAMP = 8
    LOW_LEVEL_DAMP = 12
    HIGH_LEVEL_STAND = 5
    LOW_LEVEL_STAND = 7
    LOW_LEVEL_RAISE_LEG = 10
    LOW_LEVEL_LIE_DOWN = 11
    HIGH_LEVEL_STAND_DOWN = 13

def mirror_joint_index(idx):
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
        self.last_leg_selection = 0
        self.stand_down = False
        # --- 新增日志Publisher ---
        self.log_publisher = ChannelPublisher("rt/robot_log", RobotLog)
        self.log_publisher.Init()
        self.log(0, 0)  # 初始化完成

    def log(self, event_id, level=0, param1=0.0, param2=0.0, extra=None):
        desc = ROBOT_EVENT_CODE.get(event_id, "未知事件")
        msg = f"[LOG-{level}] [{event_id}] {desc}, p1:{param1}, p2:{param2}"
        if extra:
            msg += f" | {extra}"
        print(msg)
        log_msg = RobotLog(level=level, event_id=event_id, param1=param1, param2=param2)
        self.log_publisher.Write(log_msg)

    def dds_listener_thread(self):
        self.log(1, 0)  # 启动主控线程
        while self.running:
            try:
                msg = self.dds_subscriber.Read(timeout=0.1)
                if msg:
                    self.command_queue.put(msg)
                    self.log(3, 0)  # 收到新指令
            except Exception as e:
                if str(e) != "[Reader] take sample error":
                    self.log(92, 3, extra=str(e))
            time.sleep(0.01)
        self.log(4, 0)  # 线程正常退出

    def state_machine_thread(self):
        while self.running:
            try:
                cmd: MyMotionCommand = self.command_queue.get(timeout=0.05)
                if cmd.command_type == 1:
                    self.command_queue.put(cmd)
                    time.sleep(0.05)
                    continue
                self.process_command(cmd)
            except queue.Empty:
                pass
            except Exception as e:
                self.log(98, 3, extra=str(e))
        self.log(4, 0)

    def process_command(self, cmd: MyMotionCommand):
        print(f"[Debug] 当前状态: {self.current_state}, 收到指令: {cmd}")

        with self.state_lock:
            if cmd.command_type == 0:
                try:
                    target_state = RobotState(cmd.state_enum)
                    self.log(10 + list(RobotState).index(target_state), 0, param1=self.current_state.value, param2=target_state.value)
                    if target_state == RobotState.LOW_LEVEL_RAISE_LEG:
                        self.last_leg_selection = cmd.leg_selection
                    self.handle_state_transition(target_state)
                except ValueError:
                    self.log(90, 2, param1=self.current_state.value, param2=cmd.state_enum)
            elif cmd.command_type == 1 and self.current_state == RobotState.LOW_LEVEL_RAISE_LEG:
                pass
            elif cmd.command_type == 2:
                if self.current_state in [RobotState.HIGH_LEVEL_STAND]:
                    vx, vy, vyaw = cmd.x, cmd.y, cmd.r
                    if not (-2.5 <= vx <= 3.8):
                        self.log(91, 2, param1=1, param2=vx)
                        return
                    if not (-1.0 <= vy <= 1.0):
                        self.log(91, 2, param1=2, param2=vy)
                        return
                    if not (-4 <= vyaw <= 4):
                        self.log(91, 2, param1=3, param2=vyaw)
                        return
                    self.sport.Move(vx, vy, vyaw)
                    self.log(24, 0, param1=vx, param2=vyaw)

    def handle_state_transition(self, target_state: RobotState):
        if target_state in [RobotState.HIGH_LEVEL_DAMP, RobotState.LOW_LEVEL_DAMP]:
            self.transition_to_damp()
            return

        if self.current_state == RobotState.HIGH_LEVEL_STAND:
            if target_state == RobotState.LOW_LEVEL_STAND:
                self.transition_from_high_to_low()
                self.current_state = RobotState.LOW_LEVEL_STAND
            elif target_state == RobotState.HIGH_LEVEL_STAND_DOWN:
                self.log(16, 0)
                self.sport.StandDown()
                self.current_state = RobotState.HIGH_LEVEL_STAND_DOWN
                self.stand_down = True
            else:
                self.log(90, 2, param1=self.current_state.value, param2=target_state.value)
            return

        if self.current_state == RobotState.HIGH_LEVEL_STAND_DOWN:
            if target_state == RobotState.HIGH_LEVEL_STAND:
                self.log(12, 0)
                self.sport.BalanceStand()
                self.current_state = RobotState.HIGH_LEVEL_STAND
                self.stand_down = False
            elif target_state == RobotState.HIGH_LEVEL_DAMP:
                self.log(10, 0)
                self.sport.Damp()
                self.current_state = RobotState.HIGH_LEVEL_DAMP
                self.stand_down = False
            else:
                self.log(90, 2, param1=self.current_state.value, param2=target_state.value)
            return

        if self.current_state == RobotState.HIGH_LEVEL_DAMP:
            if target_state == RobotState.HIGH_LEVEL_STAND:
                self.transition_to_high_level_stand()
                self.current_state = RobotState.HIGH_LEVEL_STAND
            else:
                self.log(90, 2, param1=self.current_state.value, param2=target_state.value)
            return

        if self.current_state == RobotState.LOW_LEVEL_DAMP:
            if target_state in [RobotState.HIGH_LEVEL_STAND]:
                self.log(12, 0)
                self.stop_low_level_thread()
                self.ensure_high_level_mode()
                self.sport.StandUp()
                self.sport.BalanceStand()
                self.current_state = RobotState.HIGH_LEVEL_STAND
            else:
                self.log(90, 2, param1=self.current_state.value, param2=target_state.value)
            return

        if self.current_state == RobotState.LOW_LEVEL_STAND:
            if target_state == RobotState.LOW_LEVEL_RAISE_LEG:
                self.transition_to_low_level_raise_leg()
                self.current_state = RobotState.LOW_LEVEL_RAISE_LEG
            elif target_state == RobotState.HIGH_LEVEL_STAND:
                self.transition_from_low_to_high()
                self.current_state = RobotState.HIGH_LEVEL_STAND
            else:
                self.log(90, 2, param1=self.current_state.value, param2=target_state.value)
            return

        if self.current_state == RobotState.LOW_LEVEL_RAISE_LEG:
            if target_state == RobotState.LOW_LEVEL_STAND:
                self.transition_to_low_level_stand()
                self.current_state = RobotState.LOW_LEVEL_STAND
            else:
                self.log(90, 2, param1=self.current_state.value, param2=target_state.value)
            return

        self.log(94, 2, param1=self.current_state.value, param2=target_state.value)

    def transition_to_damp(self):
        if self.current_state in [RobotState.HIGH_LEVEL_STAND, RobotState.HIGH_LEVEL_DAMP]:
            self.transition_to_high_level_damp()
        elif self.current_state in [RobotState.LOW_LEVEL_STAND, RobotState.LOW_LEVEL_RAISE_LEG, RobotState.LOW_LEVEL_DAMP]:
            self.transition_to_low_level_damp()
        else:
            self.log(10, 1)
            self.transition_to_high_level_damp()
        clear_queue(self.command_queue)

    def transition_to_high_level_damp(self):
        self.log(10, 0)
        self.stop_low_level_thread()
        self.ensure_high_level_mode()
        self.sport.Damp()
        self.current_state = RobotState.HIGH_LEVEL_DAMP
        clear_queue(self.command_queue)

    def transition_to_low_level_damp(self):
        self.log(11, 0)
        self.stop_low_level_thread()
        self.ensure_low_level_mode()
        self.start_low_level_thread(self.maintain_low_level_damp)
        self.current_state = RobotState.LOW_LEVEL_DAMP
        clear_queue(self.command_queue)

    def transition_to_high_level_stand(self):
        self.log(12, 0)
        self.stop_low_level_thread()
        self.ensure_high_level_mode()
        self.sport.BalanceStand()
        self.current_pose = list(self.stand_pos)
        clear_queue(self.command_queue)

    def transition_to_low_level_stand(self):
        self.log(13, 0)
        self.stop_low_level_thread()
        self.ensure_low_level_mode()
        if self.current_state == RobotState.LOW_LEVEL_RAISE_LEG:
            pose_buffer = self.current_pose[:]
            stand_pos = self.stand_pos
            use_mirror = (self.last_leg_selection == 1)
            default_indices = [0,1,2,9,10,11]
            indices = [mirror_joint_index(i) if use_mirror else i for i in default_indices]
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
        clear_queue(self.command_queue)

    def transition_to_low_level_raise_leg(self):
        self.log(14, 0)
        self.stop_low_level_thread()
        self.start_low_level_thread(lambda: self.maintain_raise_leg_pose(self.last_leg_selection))
        clear_queue(self.command_queue)

    def transition_from_high_to_low(self):
        self.log(13, 0)
        self.sport.StandUp()
        time.sleep(0.6)
        self.stop_low_level_thread()
        self.ensure_low_level_mode()
        self.current_pose = list(self.stand_pos)
        self.start_low_level_thread(self.maintain_static_pose)
        clear_queue(self.command_queue)

    def transition_from_low_to_high(self):
        self.log(12, 0)
        self.stop_low_level_thread()
        _, result = self.msc.CheckMode()
        self.interpolate_pose(self.current_pose, self.lie_down_pos, 1500)
        self.current_pose = list(self.lie_down_pos)
        time.sleep(0.5)
        self.ensure_high_level_mode()
        self.sport.BalanceStand()
        self.current_pose = list(self.stand_pos)
        clear_queue(self.command_queue)

    def ensure_high_level_mode(self):
        _, result = self.msc.CheckMode()
        if result.get("name") != "ai":
            self.msc.SelectMode("ai")
            time.sleep(1.0)
            self.log(2, 0)
        else:
            self.log(2, 0)

    def ensure_low_level_mode(self):
        while True:
            self.msc.ReleaseMode()
            time.sleep(0.01)
            status, result = self.msc.CheckMode()
            if result.get("name", "") == "":
                self.log(2, 0)
                break

    def start_low_level_thread(self, target_func):
        if self.low_level_thread and self.low_level_thread.is_alive():
            self.stop_low_level_thread()
        self.low_level_stop_event.clear()
        self.low_level_thread = threading.Thread(target=target_func)
        self.low_level_thread.start()

    def stop_low_level_thread(self):
        if self.low_level_thread and self.low_level_thread.is_alive():
            self.low_level_stop_event.set()
            self.low_level_thread.join(timeout=1.0)
        self.low_level_thread = None

    def maintain_static_pose(self):
        self.log(13, 0)
        while not self.low_level_stop_event.is_set():
            self.send_low_level_pose_cmd(self.current_pose)
            time.sleep(0.002)

    def maintain_raise_leg_pose(self, leg_selection):
        self.log(30, 0)
        self.raise_leg_pose_init = True
        self.interpolate_pose(self.current_pose, self.stand_pos, 500)
        self.current_pose = list(self.stand_pos)
        def clamp_warning(index, new_val, min_val, max_val):
            if new_val < min_val or new_val > max_val:
                self.log(34, 2, param1=index, param2=new_val)
                return False
            return True
        self.interpolate_pose(self.current_pose, self.stand_pos, 250)
        self.current_pose = list(self.stand_pos)

        use_mirror = (leg_selection == 1)
        step1 = self.stand_pos[:]
        step1[mirror_joint_index(11) if use_mirror else 11] -= 0.3
        idx_9 = mirror_joint_index(9) if use_mirror else 9
        if use_mirror:
            step1[idx_9] -= 0.3
        else:
            step1[idx_9] += 0.3
        self.interpolate_pose(self.current_pose, step1, 650)

        step2 = step1[:]
        step2[mirror_joint_index(2) if use_mirror else 2] -= 0.8
        self.interpolate_pose(step1, step2, 250)

        step3 = step2[:]
        idx = mirror_joint_index(0) if use_mirror else 0
        if use_mirror:
            step3[idx] += 0.75
        else:
            step3[idx] -= 0.75
        self.interpolate_pose(step2, step3, 300)

        step4 = step3[:]
        step4[mirror_joint_index(1) if use_mirror else 1] -= 1.0
        self.interpolate_pose(step3, step4, 250)

        step5 = step4[:]
        step5[mirror_joint_index(2) if use_mirror else 2] = self.stand_pos[mirror_joint_index(2) if use_mirror else 2]
        self.interpolate_pose(step4, step5, 250)

        pose_buffer = step5[:]
        self.current_pose = list(pose_buffer)
        high_kp = [100.0]*12
        high_kd = [8.0]*12

        if use_mirror:
            # 抬左前腿
            for idx in [0, 1, 2]:
                high_kp[idx] = 100.0    # 右前腿
                high_kd[idx] = 8.0
            for idx in [3, 4, 5]:
                high_kp[idx] = 25.0   # 左前腿
                high_kd[idx] = 4.0
            for idx in [6, 7, 8]:
                high_kp[idx] = 160.0   # 左后腿
                high_kd[idx] = 10.0
            for idx in [9, 10, 11]:
                high_kp[idx] = 100.0   # 右后腿
                high_kd[idx] = 8.0
        else:
            # 抬右前腿
            for idx in [0, 1, 2]:
                high_kp[idx] = 25.0    # 右前腿
                high_kd[idx] = 4.0
            for idx in [3, 4, 5]:
                high_kp[idx] = 100.0   # 左前腿
                high_kd[idx] = 8.0
            for idx in [6, 7, 8]:
                high_kp[idx] = 100.0   # 左后腿
                high_kd[idx] = 8.0
            for idx in [9, 10, 11]:
                high_kp[idx] = 160.0   # 右后腿
                high_kd[idx] = 10.0
        self.raise_leg_pose_init = False

        # === 新增部分：单线程实时目标插值循环 ===
        ANGLE_TOLERANCE = 0.04
        last_target = [None, None]
        target_pose = pose_buffer[:]   # 初始化目标姿态就是当前pose

        while not self.low_level_stop_event.is_set():
            # 1. 接收新DDS目标（非阻塞）
            try:
                cmd: MyMotionCommand = self.command_queue.get(timeout=0.01)
                if cmd.command_type == 1:
                    xC, yC = cmd.angle1, cmd.angle2
                    xC, yC = map_unit_circle_to_radius2(xC, yC)

                    if yC < 0:
                        self.log(34, 2, param1=xC, param2=yC, extra="Y坐标为负，自动归零处理")
                        yC = 0

                    side = "L" if use_mirror else "R"
                    res_all = ik_leg(xC, yC, side)
                    if not res_all:
                        self.log(33, 2, param1=xC, param2=yC)
                        continue
                    a = res_all[0]['a_rad']
                    b = res_all[0]['b_rad']
                    joint1_idx = mirror_joint_index(1) if use_mirror else 1
                    joint2_idx = mirror_joint_index(2) if use_mirror else 2
                    target1 = a
                    target2 = -b   # 直接取-b作为目标关节2


                    if (last_target[0] is not None and
                        abs(target1 - last_target[0]) < ANGLE_TOLERANCE and
                        abs(target2 - last_target[1]) < ANGLE_TOLERANCE):
                        continue
                    last_target[0], last_target[1] = target1, target2
                    target_pose[joint1_idx] = target1
                    target_pose[joint2_idx] = target2
                    self.log(32, 0, param1=target1, param2=target2)
                else:
                    self.command_queue.put(cmd)
            except queue.Empty:
                pass

            # 2. 全关节单线程插值
            step_pose = []
            interp_rate = 0.01
            for i in range(12):
                d = target_pose[i] - pose_buffer[i]
                if abs(d) > interp_rate:
                    v = np.sign(d) * interp_rate
                else:
                    v = d
                step_pose.append(pose_buffer[i] + v)
            pose_buffer = step_pose

            # 3. 下发命令
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

        self.current_pose = list(pose_buffer)
        self.log(31, 0)




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
            self.low_cmd.motor_cmd[i].kd = 5.0
            self.low_cmd.motor_cmd[i].tau = 0.0
        self.low_cmd.crc = self.crc.Crc(self.low_cmd)
        self.low_cmd_publisher.Write(self.low_cmd)

    def interpolate_pose(self, start, end, duration_ms):
        steps = int(duration_ms / 2)
        for step in range(steps):
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
                self.log(10 + list(RobotState).index(self.current_state), 0)  # 每秒播报当前状态
                time.sleep(1)

        except KeyboardInterrupt:
            self.log(4, 0)
        self.shutdown()
        main_sm_thread.join()
        dds_thread.join()
        self.log(4, 0)

    def maintain_low_level_damp(self):
        while not self.low_level_stop_event.is_set():
            self.send_low_level_damp_cmd()
            time.sleep(0.01)

    def shutdown(self):
        self.running = False
        self.stop_low_level_thread()
        try:
            self.transition_to_damp()
        except Exception as e:
            self.log(96, 3, extra=str(e))

if __name__ == '__main__':
    controller = RobotController()
    controller.log(1, 0)
    controller.run()