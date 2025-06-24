import time
import sys
import os
import select

from unitree_sdk2py.core.channel import ChannelPublisher, ChannelSubscriber, ChannelFactoryInitialize
from unitree_sdk2py.idl.unitree_go.msg.dds_ import LowCmd_, LowState_
from unitree_sdk2py.idl.default import unitree_go_msg_dds__LowCmd_, unitree_go_msg_dds__LowState_
from unitree_sdk2py.utils.crc import CRC
from unitree_sdk2py.comm.motion_switcher.motion_switcher_client import MotionSwitcherClient

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../unitree_example/go2/low_level")))
import unitree_legged_const as go2

def interpolate_pose(start, end, percent):
    return [(1 - percent) * s + percent * e for s, e in zip(start, end)]

def interpolate_to_target(start_pos, target, duration_ms, low_cmd, publisher, crc):
    for step in range(duration_ms):
        alpha = min(1.0, step / duration_ms)
        q_interp = interpolate_pose(start_pos, target, alpha)
        for i in range(20):
            if i < 12:
                low_cmd.motor_cmd[i].q = q_interp[i]
                low_cmd.motor_cmd[i].dq = 0
                low_cmd.motor_cmd[i].kp = 80.0
                low_cmd.motor_cmd[i].kd = 10.0
                low_cmd.motor_cmd[i].tau = 0
            else:
                low_cmd.motor_cmd[i].q = go2.PosStopF
                low_cmd.motor_cmd[i].dq = go2.VelStopF
                low_cmd.motor_cmd[i].kp = 0
                low_cmd.motor_cmd[i].kd = 0
                low_cmd.motor_cmd[i].tau = 0
        low_cmd.crc = crc.Crc(low_cmd)
        publisher.Write(low_cmd)
        time.sleep(0.002)
    return target

def down_command(low_cmd):
    target = [0.0, 0.67, -1.3] * 4
    for i in range(20):
        if i < 12:
            low_cmd.motor_cmd[i].mode = 0x01
            low_cmd.motor_cmd[i].q = target[i]
            low_cmd.motor_cmd[i].dq = 0
            low_cmd.motor_cmd[i].kp = 80
            low_cmd.motor_cmd[i].kd = 10
            low_cmd.motor_cmd[i].tau = 0
        else:
            low_cmd.motor_cmd[i].q = go2.PosStopF
            low_cmd.motor_cmd[i].dq = go2.VelStopF
            low_cmd.motor_cmd[i].kp = 0
            low_cmd.motor_cmd[i].kd = 0
            low_cmd.motor_cmd[i].tau = 0

if __name__ == '__main__':
    print("[Main] 初始化 ChannelFactory...")
    ChannelFactoryInitialize(0, "enP8p1s0")

    low_cmd = unitree_go_msg_dds__LowCmd_()
    crc = CRC()

    publisher = ChannelPublisher("rt/lowcmd", LowCmd_)
    publisher.Init()

    for i in range(20):
        low_cmd.motor_cmd[i].mode = 0x01
        low_cmd.motor_cmd[i].q = go2.PosStopF
        low_cmd.motor_cmd[i].dq = go2.VelStopF
        low_cmd.motor_cmd[i].kp = 0
        low_cmd.motor_cmd[i].kd = 0
        low_cmd.motor_cmd[i].tau = 0

    msc = MotionSwitcherClient()
    msc.SetTimeout(5.0)
    msc.Init()

    status, result = msc.CheckMode()
    print(f"[Main] 当前运控模式: {result['name']}")
    if result["name"] != "ai":
        print("请手动切换至 AI 模式后重新运行程序。")
        sys.exit(1)

    shared = {"got_state": False, "state": [0.0] * 12}
    def on_state(msg: LowState_):
        for i in range(12):
            shared["state"][i] = msg.motor_state[i].q
        shared["got_state"] = True

    subscriber = ChannelSubscriber("rt/lowstate", LowState_)
    subscriber.Init(on_state, 1)
    while not shared["got_state"]:
        time.sleep(0.01)
    ai_pos = shared["state"][:]

    print("[Main] 切换前先发送当前姿态以维持站立")
    for _ in range(100):
        for i in range(20):
            if i < 12:
                low_cmd.motor_cmd[i].mode = 0x01
                low_cmd.motor_cmd[i].q = ai_pos[i]
                low_cmd.motor_cmd[i].dq = 0
                low_cmd.motor_cmd[i].kp = 80.0
                low_cmd.motor_cmd[i].kd = 10.0
                low_cmd.motor_cmd[i].tau = 0
            else:
                low_cmd.motor_cmd[i].q = go2.PosStopF
                low_cmd.motor_cmd[i].dq = go2.VelStopF
                low_cmd.motor_cmd[i].kp = 0
                low_cmd.motor_cmd[i].kd = 0
                low_cmd.motor_cmd[i].tau = 0
        low_cmd.crc = crc.Crc(low_cmd)
        publisher.Write(low_cmd)
        time.sleep(0.005)

    input("[Main] 准备切换到低层控制 + 执行站立动作，按回车继续...")

    while True:
        code = msc.ReleaseMode()
        time.sleep(1)
        status, result = msc.CheckMode()
        if result.get("name", "") == "":
            print("[Main] 已成功切换到低层控制模式")
            break
        else:
            print(f"[Main] 当前仍为高层模式: {result['name']}，重试中...")

    target_1 = [
        0.0, 0.9, -1.8,
        0.0, 0.9, -1.8,
       -0.2, 0.9, -1.8,
        0.2, 0.9, -1.8
    ]

    print("[Action] 执行接递站立")
    start_pos = interpolate_to_target(ai_pos, target_1, 1000, low_cmd, publisher, crc)

    print("[Action] 站立持续，直到用户按下回车...")
    try:
        while True:
            for i in range(20):
                if i < 12:
                    low_cmd.motor_cmd[i].q = target_1[i]
                    low_cmd.motor_cmd[i].dq = 0
                    low_cmd.motor_cmd[i].kp = 80.0
                    low_cmd.motor_cmd[i].kd = 10.0
                    low_cmd.motor_cmd[i].tau = 0
                else:
                    low_cmd.motor_cmd[i].q = go2.PosStopF
                    low_cmd.motor_cmd[i].dq = go2.VelStopF
                    low_cmd.motor_cmd[i].kp = 0
                    low_cmd.motor_cmd[i].kd = 0
                    low_cmd.motor_cmd[i].tau = 0
            low_cmd.crc = crc.Crc(low_cmd)
            publisher.Write(low_cmd)
            time.sleep(0.01)

            if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
                input("\n[User] 检测到回车键按下，站立持续结束\n")
                break
    except KeyboardInterrupt:
        pass

    input("[Main] 准备执行躺下，按回车继续...")
    
    # 躺下这里目前还没调过，最好不要随便执行

    print("[Action] 进行躺下")
    down_command(low_cmd)
    for _ in range(200):
        low_cmd.crc = crc.Crc(low_cmd)
        publisher.Write(low_cmd)
        time.sleep(0.01)
    print("[Action] 躺下完成")
