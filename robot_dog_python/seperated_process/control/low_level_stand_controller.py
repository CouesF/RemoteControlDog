from unitree_sdk2py.core.channel import ChannelPublisher
from unitree_sdk2py.idl.default import unitree_go_msg_dds__LowCmd_
from unitree_sdk2py.utils.crc import CRC
from unitree_sdk2py.comm.motion_switcher.motion_switcher_client import MotionSwitcherClient
import time

def interpolate_pose(start, end, percent):
    return [(1 - percent) * s + percent * e for s, e in zip(start, end)]

def interpolate_all_joints(start_pos, target_pos, duration_ms, lowcmd, publisher, crc):
    for step in range(duration_ms):
        alpha = min(1.0, step / duration_ms)
        pose = interpolate_pose(start_pos, target_pos, alpha)
        for j in range(12):
            lowcmd.motor_cmd[j].mode = 0x01
            lowcmd.motor_cmd[j].q = pose[j]
            lowcmd.motor_cmd[j].dq = 0
            lowcmd.motor_cmd[j].kp = 100.0
            lowcmd.motor_cmd[j].kd = 8.0
            lowcmd.motor_cmd[j].tau = 0
        lowcmd.crc = crc.Crc(lowcmd)
        publisher.Write(lowcmd)
        time.sleep(0.002)

def run_lowlevel_stand_hold():
    """进入低层模式后，先平滑插值切换为标准站立姿态，再持续保持姿态"""
    lowcmd = unitree_go_msg_dds__LowCmd_()
    publisher = ChannelPublisher("rt/lowcmd", type(lowcmd))
    publisher.Init()
    crc = CRC()

    # 检查并切换到底层模式
    msc = MotionSwitcherClient(); msc.Init(); msc.SetTimeout(5.0)
    status, result = msc.CheckMode()
    if result.get("name", "") != "":
        print("[LowLevelStand] 正在切换到底层控制模式...")
        while True:
            msc.ReleaseMode(); time.sleep(0.01)
            status, result = msc.CheckMode()
            if result.get("name", "") == "":
                print("[LowLevelStand] 成功进入低层模式")
                break

    # 获取初始关节角度（估算值）
    initial_pose = [lowcmd.motor_cmd[i].q for i in range(12)]
    standard_pose = [0.0, 0.67, -1.3] * 4

    print("[LowLevelStand] 插值切换至标准站立姿态...")
    interpolate_all_joints(initial_pose, standard_pose, 600, lowcmd, publisher, crc)

    print("[LowLevelStand] 保持标准站立姿态...")
    while True:
        for i in range(12):
            lowcmd.motor_cmd[i].mode = 0x01
            lowcmd.motor_cmd[i].q = standard_pose[i]
            lowcmd.motor_cmd[i].dq = 0
            lowcmd.motor_cmd[i].kp = 100.0
            lowcmd.motor_cmd[i].kd = 8.0
            lowcmd.motor_cmd[i].tau = 0
        lowcmd.crc = crc.Crc(lowcmd)
        publisher.Write(lowcmd)
        time.sleep(0.01)
