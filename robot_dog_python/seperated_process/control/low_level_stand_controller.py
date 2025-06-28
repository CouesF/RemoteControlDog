from unitree_sdk2py.core.channel import ChannelPublisher, ChannelSubscriber
from unitree_sdk2py.idl.default import unitree_go_msg_dds__LowCmd_
from unitree_sdk2py.idl.unitree_go.msg.dds_ import LowState_
from unitree_sdk2py.utils.crc import CRC
from unitree_sdk2py.comm.motion_switcher.motion_switcher_client import MotionSwitcherClient
import time

def interpolate_pose(start, end, percent):
    return [(1 - percent) * s + percent * e for s, e in zip(start, end)]

def interpolate_all_joints(start_pos, target_pos, duration_ms, lowcmd, publisher, crc, exit_condition):
    for step in range(duration_ms):
        if exit_condition():
            print("[LowLevelStand] 状态已切换，提前中止插值动作")
            return
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
    from main_state_machine import get_current_state, FSMStateEnum

    def exit_requested():
        return get_current_state() != FSMStateEnum.LOW_LEVEL_STAND

    lowcmd = unitree_go_msg_dds__LowCmd_()
    publisher = ChannelPublisher("rt/lowcmd", type(lowcmd))
    publisher.Init()
    crc = CRC()

    # Step 1: 切换到底层控制模式
    msc = MotionSwitcherClient()
    msc.Init()
    msc.SetTimeout(5.0)
    status, result = msc.CheckMode()
    if result.get("name", "") != "":
        print("[LowLevelStand] 正在切换到底层控制模式...")
        while True:
            msc.ReleaseMode()
            time.sleep(0.01)
            status, result = msc.CheckMode()
            if result.get("name", "") == "":
                print("[LowLevelStand] 成功进入低层模式")
                break
            if exit_requested():
                print("[LowLevelStand] 状态切换，跳过控制模式切换")
                return

    # Step 2: 订阅 lowstate，获取当前关节姿态
    sub = ChannelSubscriber("rt/lowstate", LowState_)
    sub.Init()
    time.sleep(0.05)
    state = sub.Read()
    initial_pose = [state.motor_state[i].q for i in range(12)]

    # Step 3: 设置标准站立姿态
    standard_pose = [0.0, 0.67, -1.3] * 4

    # Step 4: 插值切换
    print("[LowLevelStand] 插值切换至标准站立姿态...")
    interpolate_all_joints(initial_pose, standard_pose, 600, lowcmd, publisher, crc, exit_requested)

    # Step 5: 保持标准站立姿态
    print("[LowLevelStand] 保持标准站立姿态中...（等待状态切换）")
    while not exit_requested():
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

    print("[LowLevelStand] 检测到状态切换，安全退出站立线程")
