import time
import sys
import os
import threading

from unitree_sdk2py.core.channel import ChannelPublisher, ChannelFactoryInitialize
from unitree_sdk2py.idl.unitree_go.msg.dds_ import LowCmd_, LowState_
from unitree_sdk2py.idl.default import unitree_go_msg_dds__LowCmd_
from unitree_sdk2py.utils.crc import CRC
from unitree_sdk2py.comm.motion_switcher.motion_switcher_client import MotionSwitcherClient
from unitree_sdk2py.go2.sport.sport_client import SportClient

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../unitree_example/go2/low_level")))
import unitree_legged_const as go2

# 插值函数
def interpolate_pose(start, end, percent):
    return [(1 - percent) * s + percent * e for s, e in zip(start, end)]

def interpolate_to_target(start_pos, target, duration_ms, low_cmd, publisher, crc):
    for step in range(duration_ms):
        alpha = min(1.0, step / duration_ms)
        q_interp = interpolate_pose(start_pos, target, alpha)
        for i in range(12):
            low_cmd.motor_cmd[i].mode = 0x01
            low_cmd.motor_cmd[i].q = q_interp[i]
            low_cmd.motor_cmd[i].dq = 0
            low_cmd.motor_cmd[i].kp = 100.0
            low_cmd.motor_cmd[i].kd = 8.0
            low_cmd.motor_cmd[i].tau = 0
        low_cmd.crc = crc.Crc(low_cmd)
        publisher.Write(low_cmd)
        time.sleep(0.002)
    return target

# 独立线程持续发 StandUp 指令（用于切换期间保持站立）
def continuous_standup(sport_client, stop_flag):
    while not stop_flag["stop"]:
        try:
            print("[Thread] 发送 StandUp 指令")
            print(sport_client.StandUp())
        except Exception:
            pass  # 底层模式下调用会报错，忽略即可
        time.sleep(0.05)

if __name__ == '__main__':
    print("[Main] 初始化 ChannelFactory...")
    ChannelFactoryInitialize(0, "enP8p1s0")

    low_cmd = unitree_go_msg_dds__LowCmd_()
    crc = CRC()
    msc = MotionSwitcherClient()
    msc.Init()
    msc.SetTimeout(5.0)
    publisher = ChannelPublisher("rt/lowcmd", LowCmd_)
    publisher.Init()

    sport = SportClient()
    sport.Init()

    print("[Action] 设置阻尼模式")
    sport.Damp()

    status, result = msc.CheckMode()
    if result['name'] != 'ai':
        print("[Error] 请手动切换到 AI 模式后重启程序")
        sys.exit(1)

    time.sleep(1)

    print("[Action] 执行 StandUp")
    sport.StandUp()

    input("[User] 按下回车继续，准备进入低层模式")

    while True:
        msc.ReleaseMode()
        time.sleep(0.01)
        status, result = msc.CheckMode()
        if result.get("name", "") == "":
            print("[Main] 已切换到低层模式")
            break
        print("[Main] 当前仍为高层模式，重试中...")

    # 保持站立姿势 10 秒
    stand_pos = [0.0, 0.67, -1.3] * 4
    print("[Action] 保持站立姿势 10 秒")
    for _ in range(500 * 6):
        for j in range(12):
            low_cmd.motor_cmd[j].mode = 0x01
            low_cmd.motor_cmd[j].q = stand_pos[j]
            low_cmd.motor_cmd[j].dq = 0
            low_cmd.motor_cmd[j].kp = 100
            low_cmd.motor_cmd[j].kd = 8
            low_cmd.motor_cmd[j].tau = 0
        low_cmd.crc = crc.Crc(low_cmd)
        publisher.Write(low_cmd)
        time.sleep(0.002)

    print("[Action] 保持低层控制不释放，直接尝试切换到 normal 模式")
    time.sleep(0.05)

    stop_flag = {"stop": False}
    thread = threading.Thread(target=continuous_standup, args=(sport, stop_flag))
    thread.start()
    time.sleep(2)
    ret1, _ = msc.SelectMode("normal")
    if ret1 == 0:
        print("[Action] 切换到 normal 成功，准备切换到 AI 模式")
        time.sleep(2)
        stop_flag["stop"] = True  # 在成功切换到 normal 后终止线程
        thread.join()

        time.sleep(6)
        ret2, _ = msc.SelectMode("ai")
        if ret2 == 0:
            print("[Action] 已成功切换至 AI 模式")
        else:
            print(f"[Error] 切换到 AI 模式失败，返回码: {ret2}")
    else:
        print(f"[Error] 切换到 normal 模式失败，返回码: {ret1}")
        stop_flag["stop"] = True
        thread.join()

    print("[Done] 程序结束")