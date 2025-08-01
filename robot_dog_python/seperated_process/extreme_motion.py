import time
import sys
import os
import threading

from unitree_sdk2py.core.channel import ChannelPublisher, ChannelFactoryInitialize
from unitree_sdk2py.idl.unitree_go.msg.dds_ import LowCmd_
from unitree_sdk2py.idl.default import unitree_go_msg_dds__LowCmd_
from unitree_sdk2py.utils.crc import CRC
from unitree_sdk2py.comm.motion_switcher.motion_switcher_client import MotionSwitcherClient
from unitree_sdk2py.go2.sport.sport_client import SportClient

def interpolate_pose(start, end, percent):
    return [(1 - percent) * s + percent * e for s, e in zip(start, end)]

def interpolate_to_pose(start_pos, target_pos, duration_ms, low_cmd, publisher, crc, kp=100.0, kd=8.0):
    steps = duration_ms
    for step in range(steps):
        alpha = step / float(steps)
        q_interp = interpolate_pose(start_pos, target_pos, alpha)
        for i in range(12):
            low_cmd.motor_cmd[i].mode = 0x01
            low_cmd.motor_cmd[i].dq = 0
            low_cmd.motor_cmd[i].tau = 0
            low_cmd.motor_cmd[i].q = q_interp[i]
            low_cmd.motor_cmd[i].kp = kp
            low_cmd.motor_cmd[i].kd = kd
        low_cmd.crc = crc.Crc(low_cmd)
        publisher.Write(low_cmd)
        time.sleep(0.002)
    # 最后发一帧确保到位
    for i in range(12):
        low_cmd.motor_cmd[i].q = target_pos[i]
    low_cmd.crc = crc.Crc(low_cmd)
    publisher.Write(low_cmd)

def maintain_posture(target_pose, low_cmd, publisher, crc, stop_flag, kp=100.0, kd=8.0):
    while not stop_flag["stop"]:
        for i in range(12):
            low_cmd.motor_cmd[i].mode = 0x01
            low_cmd.motor_cmd[i].q = target_pose[i]
            low_cmd.motor_cmd[i].dq = 0
            low_cmd.motor_cmd[i].kp = kp
            low_cmd.motor_cmd[i].kd = kd
            low_cmd.motor_cmd[i].tau = 0
        low_cmd.crc = crc.Crc(low_cmd)
        publisher.Write(low_cmd)
        time.sleep(0.002)

if __name__ == '__main__':
    # 1. 初始化 DDS
    ChannelFactoryInitialize(0, "enP8p1s0")
    low_cmd = unitree_go_msg_dds__LowCmd_()
    crc = CRC()
    msc = MotionSwitcherClient(); msc.Init(); msc.SetTimeout(5.0)
    publisher = ChannelPublisher("rt/lowcmd", LowCmd_); publisher.Init()
    sport = SportClient(); sport.Init()

    # 2. 进入 AI StandUp
    sport.Damp()
    status, result = msc.CheckMode()
    if result.get("name", "") != "ai":
        print("[Error] 请手动切换至 AI 模式"); sys.exit(1)
    time.sleep(1)
    sport.StandUp()
    input("[User] AI模式已StandUp，回车切换到低层模式")

    # 3. 切换到低层模式
    while True:
        msc.ReleaseMode(); time.sleep(0.01)
        status, result = msc.CheckMode()
        if result.get("name", "") == "": break

    # 4. 站立位
    stand_pos = [0.0, 0.67, -1.3] * 4
    stop_flag = {"stop": False}
    thread = threading.Thread(target=maintain_posture, args=(stand_pos, low_cmd, publisher, crc, stop_flag))
    thread.start()
    input("[User] 当前为标准站立，回车切换到扩展站立...")
    stop_flag["stop"] = True; thread.join()

    # 5. 插值到扩展站立
    step2 = [0, 0.8, -1.4, 0, 0.8, -1.4, 0, 1.2, -1.9, 0, 1.2, -1.9]
    interpolate_to_pose(stand_pos, step2, 800, low_cmd, publisher, crc)
    stop_flag2 = {"stop": False}
    thread2 = threading.Thread(target=maintain_posture, args=(step2, low_cmd, publisher, crc, stop_flag2))
    thread2.start()
    input("[User] 当前为扩展站立，回车切换到趴下...")
    stop_flag2["stop"] = True; thread2.join()

    # 6. 插值到趴下
    lie_down_pos = [-0.35, 1.36, -2.65, 0.35, 1.36, -2.65, -0.5, 1.36, -2.65, 0.5, 1.36, -2.65]
    interpolate_to_pose(step2, lie_down_pos, 1000, low_cmd, publisher, crc)
    stop_flag3 = {"stop": False}
    thread3 = threading.Thread(target=maintain_posture, args=(lie_down_pos, low_cmd, publisher, crc, stop_flag3))
    thread3.start()
    input("[User] 已到趴下姿态，回车结束")
    stop_flag3["stop"] = True; thread3.join()

    print("[Done] 动作流程全部完成，推荐手动切回 AI 模式。")
