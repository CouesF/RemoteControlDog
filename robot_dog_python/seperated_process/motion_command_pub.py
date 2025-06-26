import time
import os
import sys
from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelPublisher

sys.path.append("/home/d3lab/Projects/RemoteControlDog/robot_dog_python/communication")
from dds_data_structure import MyMotionCommand

def send_motion_command(command_type, state_enum=5, angle1=0.0, angle2=0.0, x=0.0, y=0.0, r=0.0):
    msg = MyMotionCommand(
        command_type=command_type,
        state_enum=state_enum,
        angle1=angle1,
        angle2=angle2,
        x=x,
        y=y,
        r=r
    )
    publisher.Write(msg)
    print(f"[Publisher] Sent: {msg}")

if __name__ == "__main__":
    ChannelFactoryInitialize(0, "enP8p1s0")
    publisher = ChannelPublisher("rt/keyboard_control", MyMotionCommand)
    publisher.Init()

    print("=== MotionCommand Publisher ===")
    print("0: 状态切换  | 1: 抬腿控制  | 2: 导航控制")
    print("状态编号：5=HIGH_LEVEL, 6=LOW_LEVEL, 7=LOW_LEVEL_STAND, 8=DAMP")
    print("示例输入格式：0 5   or   1 1.2 -1.8   or   2 0.3 0 0")
    print("输入 q 退出")

    while True:
        try:
            user_input = input(">>> ").strip()
            if user_input.lower() == 'q':
                break

            parts = user_input.split()
            if not parts:
                continue

            cmd_type = int(parts[0])
            if cmd_type == 0 and len(parts) == 2:
                send_motion_command(0, state_enum=int(parts[1]))
            elif cmd_type == 1 and len(parts) == 3:
                send_motion_command(1, angle1=float(parts[1]), angle2=float(parts[2]))
            elif cmd_type == 2 and len(parts) == 4:
                send_motion_command(2, x=float(parts[1]), y=float(parts[2]), r=float(parts[3]))
            else:
                print("[Error] 格式错误，请重试")

        except Exception as e:
            print(f"[Exception] {e}")
