import time
from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelPublisher, ChannelSubscriber
from unitree_sdk2py.idl.unitree_go.msg.dds_ import LowCmd_, LowState_
from unitree_sdk2py.idl.default import unitree_go_msg_dds__LowCmd_
from unitree_sdk2py.utils.crc import CRC
from unitree_sdk2py.comm.motion_switcher.motion_switcher_client import MotionSwitcherClient

def interpolate_pose(start, end, percent):
    return [(1 - percent) * s + percent * e for s, e in zip(start, end)]

def interpolate_all_joints(start_pos, target_pos, duration_ms, lowcmd, publisher, crc):
    for step in range(duration_ms):
        alpha = min(1.0, step / duration_ms)
        pose = interpolate_pose(start_pos, target_pos, alpha)
        for j in range(12):
            lowcmd.motor_cmd[j].mode = 0x01
            lowcmd.motor_cmd[j].q = pose[j]
            lowcmd.motor_cmd[j].dq = 0.0
            lowcmd.motor_cmd[j].kp = 100.0
            lowcmd.motor_cmd[j].kd = 8.0
            lowcmd.motor_cmd[j].tau = 0.0
        lowcmd.crc = crc.Crc(lowcmd)
        publisher.Write(lowcmd)
        time.sleep(0.002)

def run_lowlevel_damp_full():
    print("[Test] 检查并进入低层模式 → 站立 → 阻尼模式")

    ChannelFactoryInitialize(0, "enP8p1s0")

    # 初始化 lowcmd publisher
    publisher = ChannelPublisher("rt/lowcmd", LowCmd_)
    publisher.Init()
    lowcmd = unitree_go_msg_dds__LowCmd_()
    crc = CRC()

    # 初始化底层模式控制器
    msc = MotionSwitcherClient()
    msc.Init()
    msc.SetTimeout(5.0)

    # 若当前为 AI 模式，则切换到底层
    print("[Step 1] 检查当前模式...")
    _, result = msc.CheckMode()
    if result.get("name", "") != "":
        print("[Step 2] 当前为 AI 模式，开始切换到底层...")
        while True:
            msc.ReleaseMode()
            time.sleep(0.01)
            _, result = msc.CheckMode()
            if result.get("name", "") == "":
                print("[OK] 已进入低层模式")
                break

    # 获取当前姿态
    print("[Step 3] 获取当前姿态并准备站立...")
    sub = ChannelSubscriber("rt/lowstate", LowState_)
    sub.Init()
    time.sleep(0.05)
    state = sub.Read()
    initial_pose = [state.motor_state[i].q for i in range(12)]

    # 标准站立姿态
    standard_pose = [0.0, 0.67, -1.3] * 4

    # 插值切换
    print("[Step 4] 插值切换到标准站立...")
    interpolate_all_joints(initial_pose, standard_pose, duration_ms=800, lowcmd=lowcmd, publisher=publisher, crc=crc)

    # 保持一小段时间站立
    print("[Step 5] 保持站立姿态...")
    for _ in range(200):  # 大约 2 秒
        for j in range(12):
            lowcmd.motor_cmd[j].mode = 0x01
            lowcmd.motor_cmd[j].q = standard_pose[j]
            lowcmd.motor_cmd[j].dq = 0.0
            lowcmd.motor_cmd[j].kp = 100.0
            lowcmd.motor_cmd[j].kd = 8.0
            lowcmd.motor_cmd[j].tau = 0.0
        lowcmd.crc = crc.Crc(lowcmd)
        publisher.Write(lowcmd)
        time.sleep(0.01)

    # 进入阻尼
    print("[Step 6] 进入阻尼模式...")
    while True:
        for i in range(12):
            lowcmd.motor_cmd[i].mode = 0x01
            lowcmd.motor_cmd[i].q = 0.0
            lowcmd.motor_cmd[i].dq = 0.0
            lowcmd.motor_cmd[i].kp = 0.0
            lowcmd.motor_cmd[i].kd = 2.0
            lowcmd.motor_cmd[i].tau = 0.0
        lowcmd.crc = crc.Crc(lowcmd)
        publisher.Write(lowcmd)
        time.sleep(0.01)

if __name__ == "__main__":
    run_lowlevel_damp_full()
