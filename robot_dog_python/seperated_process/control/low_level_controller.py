# 文件: control/low_level_controller.py

import time, sys, threading
from unitree_sdk2py.core.channel import ChannelPublisher, ChannelFactoryInitialize, ChannelSubscriber
from unitree_sdk2py.idl.unitree_go.msg.dds_ import LowCmd_
from unitree_sdk2py.idl.default import unitree_go_msg_dds__LowCmd_
from unitree_sdk2py.utils.crc import CRC
from unitree_sdk2py.comm.motion_switcher.motion_switcher_client import MotionSwitcherClient
from unitree_sdk2py.go2.sport.sport_client import SportClient

sys.path.append("/home/d3lab/Projects/RemoteControlDog/robot_dog_python/communication")
from dds_data_structure import MyMotionCommand

pose_buffer = []

def interpolate_pose(start, end, percent):
    return [(1 - percent) * s + percent * e for s, e in zip(start, end)]

def interpolate_selected_joints(start_pos, target, joint_indices, duration_ms, low_cmd, publisher, crc, kp_override=None, kd_override=None):
    for step in range(duration_ms):
        alpha = min(1.0, step / duration_ms)
        q_interp = interpolate_pose(start_pos, target, alpha)
        for i in range(12):
            low_cmd.motor_cmd[i].mode = 0x01
            low_cmd.motor_cmd[i].q = q_interp[i] if i in joint_indices else start_pos[i]
            low_cmd.motor_cmd[i].dq = 0.0
            low_cmd.motor_cmd[i].kp = kp_override[i] if kp_override else 100.0
            low_cmd.motor_cmd[i].kd = kd_override[i] if kd_override else 8.0
            low_cmd.motor_cmd[i].tau = 0.0
        low_cmd.crc = crc.Crc(low_cmd)
        publisher.Write(low_cmd)
        time.sleep(0.002)

def maintain_dynamic_pose(shared_pose, low_cmd, publisher, crc, stop_flag, kp_profile, kd_profile):
    while not stop_flag["stop"]:
        for j in range(12):
            low_cmd.motor_cmd[j].mode = 0x01
            low_cmd.motor_cmd[j].q = shared_pose[j]
            low_cmd.motor_cmd[j].dq = 0.0
            low_cmd.motor_cmd[j].kp = kp_profile[j]
            low_cmd.motor_cmd[j].kd = kd_profile[j]
            low_cmd.motor_cmd[j].tau = 0.0
        low_cmd.crc = crc.Crc(low_cmd)
        publisher.Write(low_cmd)
        time.sleep(0.002)

def move_joint(index, target):
    while abs(pose_buffer[index] - target) > 0.05:
        pose_buffer[index] += 0.1 if pose_buffer[index] < target else -0.1
        time.sleep(0.05)

def clamp_warning(index, val, lo, hi):
    if val < lo or val > hi:
        print(f"[Warning] 超出限制: 关节 {index}={val:.2f} 超出范围 [{lo}, {hi}]")
        return False
    return True

def run_lowlevel_leg_control():
    global pose_buffer
    print("[LOW_LEVEL] 执行自动抬腿 + DDS 姿态监听...")
    msc = MotionSwitcherClient(); msc.Init(); msc.SetTimeout(5.0)
    sport = SportClient(); sport.Init(); sport.StandUp()
    time.sleep(1.0)
    while True:
        msc.ReleaseMode(); time.sleep(0.01)
        if msc.CheckMode()[1].get("name", "") == "": break

    publisher = ChannelPublisher("rt/lowcmd", LowCmd_); publisher.Init()
    low_cmd = unitree_go_msg_dds__LowCmd_()
    crc = CRC()

    stand = [0.0, 0.67, -1.3] * 4
    high_kp = [160.0 if i in [0,1,2,3,4,5,9,10,11] else 100.0 for i in range(12)]
    high_kd = [10.0 if i in [0,1,2,3,4,5,9,10,11] else 8.0 for i in range(12)]

    step1 = stand[:]; step1[11] -= 0.3; step1[9] += 0.3
    interpolate_selected_joints(stand, step1, [9,11], 650, low_cmd, publisher, crc, high_kp, high_kd)

    step2 = step1[:]; step2[2] -= 0.8
    interpolate_selected_joints(step1, step2, [2], 250, low_cmd, publisher, crc, high_kp, high_kd)
    step3 = step2[:]; step3[0] -= 0.8
    interpolate_selected_joints(step2, step3, [0], 250, low_cmd, publisher, crc, high_kp, high_kd)
    step4 = step3[:]; step4[1] -= 1.0
    interpolate_selected_joints(step3, step4, [1], 250, low_cmd, publisher, crc, high_kp, high_kd)
    step5 = step4[:]; step5[2] = stand[2]
    interpolate_selected_joints(step4, step5, [2], 250, low_cmd, publisher, crc, high_kp, high_kd)

    pose_buffer = step5[:]
    adjusting = {"running": True}
    subscriber = ChannelSubscriber("rt/keyboard_control", MyMotionCommand)


    def receive_dds_command():
        while adjusting["running"]:
            msg = subscriber.Read()
            if not msg: time.sleep(0.01); continue
            if msg.command_type == 1 and msg.command_id == ord("q"):
                print("[DDS] 收到退出信号，恢复站姿")
                adjusting["running"] = False
                break
            if clamp_warning(1, msg.joint1_target, -1.5, 3.4): move_joint(1, msg.joint1_target)
            if clamp_warning(2, msg.joint2_target, -2.7, -0.8): move_joint(2, msg.joint2_target)

    stop_flag = {"stop": False}
    t_pose = threading.Thread(target=maintain_dynamic_pose, args=(pose_buffer, low_cmd, publisher, crc, stop_flag, high_kp, high_kd))
    t_cmd = threading.Thread(target=receive_dds_command)
    t_pose.start(); t_cmd.start()
    t_cmd.join(); stop_flag["stop"] = True; t_pose.join()

    for idx in [0,1,2,9,10,11]:
        restore = pose_buffer[:]; restore[idx] = stand[idx]
        interpolate_selected_joints(pose_buffer, restore, [idx], 300, low_cmd, publisher, crc)
        pose_buffer = restore[:]

    print("[LOW_LEVEL] 姿态恢复完毕，维持标准站立")


def lie_down_and_switch_to_ai():
    """
    从底层模式下执行趴下动作，并切换回 AI 模式
    """
    print("[LOW_LEVEL] 执行趴下动作并切换至 AI 模式")

    msc = MotionSwitcherClient(); msc.Init(); msc.SetTimeout(5.0)
    publisher = ChannelPublisher("rt/lowcmd", LowCmd_); publisher.Init()
    low_cmd = unitree_go_msg_dds__LowCmd_()
    crc = CRC()

    stand_pose = [0.0, 0.67, -1.3] * 4
    lie_down_pose = [
        -0.35, 1.36, -2.65,   # RF
         0.35, 1.36, -2.65,   # LF
        -0.5,  1.36, -2.65,   # RR
         0.5,  1.36, -2.65    # LR
    ]

    interpolate_selected_joints(
        stand_pose, lie_down_pose,
        joint_indices=list(range(12)),
        duration_ms=1500,
        low_cmd=low_cmd,
        publisher=publisher,
        crc=crc
    )

    time.sleep(0.5)
    ret, _ = msc.SelectMode("ai")
    if ret == 0:
        print("[LOW_LEVEL] 已成功切换回 AI 模式")
    else:
        print(f"[LOW_LEVEL] 切换 AI 模式失败，错误码: {ret}")
