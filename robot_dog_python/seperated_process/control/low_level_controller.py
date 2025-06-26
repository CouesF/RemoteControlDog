
import time
import sys
import os
import threading

from unitree_sdk2py.core.channel import ChannelPublisher, ChannelFactoryInitialize, ChannelSubscriber
from unitree_sdk2py.idl.unitree_go.msg.dds_ import LowCmd_
from unitree_sdk2py.idl.default import unitree_go_msg_dds__LowCmd_
from unitree_sdk2py.utils.crc import CRC
from unitree_sdk2py.comm.motion_switcher.motion_switcher_client import MotionSwitcherClient
from unitree_sdk2py.go2.sport.sport_client import SportClient

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../communication")))
from dds_data_structure import MyMotionCommand

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../unitree_example/go2/low_level")))
import unitree_legged_const as go2


def interpolate_pose(start, end, percent):
    return [(1 - percent) * s + percent * e for s, e in zip(start, end)]


def interpolate_selected_joints(start_pos, target, joint_indices, duration_ms, low_cmd, publisher, crc, kp_override=None, kd_override=None):
    for step in range(duration_ms):
        alpha = min(1.0, step / duration_ms)
        q_interp = interpolate_pose(start_pos, target, alpha)
        for i in range(12):
            low_cmd.motor_cmd[i].mode = 0x01
            low_cmd.motor_cmd[i].dq = 0
            low_cmd.motor_cmd[i].tau = 0
            low_cmd.motor_cmd[i].q = q_interp[i] if i in joint_indices else start_pos[i]
            low_cmd.motor_cmd[i].kp = kp_override[i] if kp_override else 100.0
            low_cmd.motor_cmd[i].kd = kd_override[i] if kd_override else 8.0
        low_cmd.crc = crc.Crc(low_cmd)
        publisher.Write(low_cmd)
        time.sleep(0.002)


def maintain_posture(target_pose, low_cmd, publisher, crc, stop_flag, kp_profile=None, kd_profile=None):
    while not stop_flag["stop"]:
        for j in range(12):
            low_cmd.motor_cmd[j].mode = 0x01
            low_cmd.motor_cmd[j].q = target_pose[j]
            low_cmd.motor_cmd[j].dq = 0
            low_cmd.motor_cmd[j].kp = kp_profile[j] if kp_profile else 100.0
            low_cmd.motor_cmd[j].kd = kd_profile[j] if kd_profile else 8.0
            low_cmd.motor_cmd[j].tau = 0
        low_cmd.crc = crc.Crc(low_cmd)
        publisher.Write(low_cmd)
        time.sleep(0.002)


def maintain_dynamic_pose(shared_pose, low_cmd, publisher, crc, stop_flag, kp_profile, kd_profile):
    while not stop_flag["stop"]:
        for j in range(12):
            low_cmd.motor_cmd[j].mode = 0x01
            low_cmd.motor_cmd[j].q = shared_pose[j]
            low_cmd.motor_cmd[j].dq = 0
            low_cmd.motor_cmd[j].kp = kp_profile[j]
            low_cmd.motor_cmd[j].kd = kd_profile[j]
            low_cmd.motor_cmd[j].tau = 0
        low_cmd.crc = crc.Crc(low_cmd)
        publisher.Write(low_cmd)
        time.sleep(0.002)


def clamp_warning(index, new_val, min_val, max_val):
    if new_val < min_val or new_val > max_val:
        print(f"[Warning] 关节 {index} 的角度 {new_val:.2f} 超出范围 [{min_val}, {max_val}]，忽略")
        return False
    return True


def move_joint(index, target):
    while abs(pose_buffer[index] - target) > 0.05:
        pose_buffer[index] += 0.1 if pose_buffer[index] < target else -0.1
        pose_buffer[index] = min(max(pose_buffer[index], min(target, pose_buffer[index])), max(target, pose_buffer[index]))
        time.sleep(0.05)


def run_lowlevel_leg_control():
    global pose_buffer
    ChannelFactoryInitialize(0, "enP8p1s0")
    low_cmd = unitree_go_msg_dds__LowCmd_()
    crc = CRC()
    msc = MotionSwitcherClient(); msc.Init(); msc.SetTimeout(5.0)
    publisher = ChannelPublisher("rt/lowcmd", LowCmd_); publisher.Init()
    sport = SportClient(); sport.Init()

    sport.StandUp(); time.sleep(1.0)
    while True:
        msc.ReleaseMode(); time.sleep(0.01)
        if msc.CheckMode()[1].get("name", "") == "":
            break

    stand_pos = [0.0, 0.67, -1.3] * 4
    stop_flag = {"stop": False}
    thread = threading.Thread(target=maintain_posture, args=(stand_pos, low_cmd, publisher, crc, stop_flag))
    thread.start(); time.sleep(1.5); stop_flag["stop"] = True; thread.join()

    high_kp = [160.0 if i in [0,1,2,3,4,5,9,10,11] else 100.0 for i in range(12)]
    high_kd = [10.0 if i in [0,1,2,3,4,5,9,10,11] else 8.0 for i in range(12)]

    step1 = stand_pos[:]; step1[11] -= 0.3; step1[9] += 0.3
    interpolate_selected_joints(stand_pos, step1, [9,11], 650, low_cmd, publisher, crc, high_kp, high_kd)

    thread_hold1 = threading.Thread(target=maintain_posture, args=(
        step1, low_cmd, publisher, crc, {"stop": False}, high_kp, high_kd))
    thread_hold1.start(); time.sleep(1.0); thread_hold1._args[4]["stop"] = True; thread_hold1.join()

    steps = [
        ([2], -0.8), ([0], -0.8), ([1], -1.0), ([2], stand_pos[2])
    ]
    prev = step1[:]
    for idxs, val in steps:
        next_pose = prev[:]
        for i in idxs: next_pose[i] = val
        interpolate_selected_joints(prev, next_pose, idxs, 300, low_cmd, publisher, crc, high_kp, high_kd)
        prev = next_pose
    pose_buffer = prev[:]

    adjusting = {"running": True}
    subscriber = ChannelSubscriber("rt/keyboard_control", MyMotionCommand); subscriber.Init()

    def receive_command_with_target():
        while adjusting["running"]:
            msg = subscriber.Read()
            if msg is None: time.sleep(0.01); continue
            if msg.command_type == 0 and msg.state_enum == 7:
                print("[DDS] 收到退出指令"); adjusting["running"] = False; break
            if clamp_warning(1, msg.angle1, -1.5, 3.4): move_joint(1, msg.angle1)
            if clamp_warning(2, msg.angle2, -2.7, -0.8): move_joint(2, msg.angle2)

    stop_flag_dyn = {"stop": False}
    thread_dyn_pose = threading.Thread(target=maintain_dynamic_pose, args=(pose_buffer, low_cmd, publisher, crc, stop_flag_dyn, high_kp, high_kd))
    thread_cmd = threading.Thread(target=receive_command_with_target)
    thread_dyn_pose.start(); thread_cmd.start(); thread_cmd.join()
    stop_flag_dyn["stop"] = True; thread_dyn_pose.join()

    for idx in [0,1,2,9,10,11]:
        updated = pose_buffer[:]; updated[idx] = stand_pos[idx]
        interpolate_selected_joints(pose_buffer, updated, [idx], 300, low_cmd, publisher, crc)
        pose_buffer = updated

    thread3 = threading.Thread(target=maintain_posture, args=(stand_pos, low_cmd, publisher, crc, {"stop": False}))
    thread3.start()
    print("[LOWLEVEL] 控制流程完成，进入稳定站立状态")

def lie_down_and_switch_to_ai():
    """
    从底层模式下执行趴下，然后切换回 AI 模式（用于 s → h 的过渡）
    """

    msc = MotionSwitcherClient(); msc.Init(); msc.SetTimeout(5.0)
    low_cmd = unitree_go_msg_dds__LowCmd_()
    publisher = ChannelPublisher("rt/lowcmd", LowCmd_); publisher.Init()
    crc = CRC()

    stand_pose = [0.0, 0.67, -1.3] * 4
    lie_down_pose = [-0.35, 1.36, -2.65,
                      0.35, 1.36, -2.65,
                     -0.5, 1.36, -2.65,
                      0.5, 1.36, -2.65]

    print("[FSM] 执行趴下动作...")
    interpolate_selected_joints(stand_pose, lie_down_pose, list(range(12)), 1500, low_cmd, publisher, crc)

    print("[FSM] 尝试切换回 AI 模式...")
    ret, _ = msc.SelectMode("ai")
    if ret == 0:
        print("[FSM] 已成功切换回 AI 模式")
    else:
        print(f"[FSM] 切换 AI 模式失败: 错误码 {ret}")

    time.sleep(2.0)