from unitree_sdk2py.core.channel import ChannelPublisher
from unitree_sdk2py.idl.unitree_go.msg.dds_ import LowCmd_
from unitree_sdk2py.utils.crc import CRC
from unitree_sdk2py.comm.motion_switcher.motion_switcher_client import MotionSwitcherClient
import time

def run_lowlevel_stand_hold():
    """保持底层模式并持续发送标准站立姿态指令"""
    lowcmd = LowCmd_()
    publisher = ChannelPublisher("rt/lowcmd", LowCmd_)
    publisher.Init()
    crc = CRC()

    # 切换到底层模式（如果尚未切换）
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

    # 标准站立姿态
    stand_pose = [0.0, 0.67, -1.3] * 4

    print("[LowLevelStand] 保持标准站立姿态中... 按 Ctrl+C 退出")
    try:
        while True:
            for i in range(12):
                lowcmd.motor_cmd[i].mode = 0x01
                lowcmd.motor_cmd[i].q = stand_pose[i]
                lowcmd.motor_cmd[i].dq = 0.0
                lowcmd.motor_cmd[i].kp = 100.0
                lowcmd.motor_cmd[i].kd = 8.0
                lowcmd.motor_cmd[i].tau = 0.0
            lowcmd.crc = crc.Crc(lowcmd)
            publisher.Write(lowcmd)
            time.sleep(0.01)
    except KeyboardInterrupt:
        print("[LowLevelStand] 已中断退出")
