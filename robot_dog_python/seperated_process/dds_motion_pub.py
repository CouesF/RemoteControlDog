import time
import sys
import os
from unitree_sdk2py.core.channel import ChannelPublisher, ChannelFactoryInitialize

# 添加 communication 路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../communication")))
from dds_data_structure import RaiseLegCommand

# 初始化
ChannelFactoryInitialize(0, "enP8p1s0")
publisher = ChannelPublisher("rt/keyboard_control", RaiseLegCommand)
publisher.Init()

def send_command(j1: float, j2: float):
    msg = RaiseLegCommand()
    msg.command_id = 0               # 非 q 指令，填 0
    msg.joint1_target = j1
    msg.joint2_target = j2
    publisher.Write(msg)
    print(f"[Sent] 目标角度 joint1: {j1:.2f}, joint2: {j2:.2f}")

print("[INFO] 输入两个角度 (joint1 joint2)，如 1.0 -1.5；输入 q 退出")

while True:
    inp = input(">>> ").strip().lower()
    if inp == 'q':
        msg = RaiseLegCommand()
        msg.command_id = ord('q')
        publisher.Write(msg)
        print("[Exit] 已发送退出信号")
        break
    try:
        j1_str, j2_str = inp.split()
        j1 = float(j1_str)
        j2 = float(j2_str)
        send_command(j1, j2)
    except ValueError:
        print("[Warning] 输入格式错误，应为两个浮点数或 q")
