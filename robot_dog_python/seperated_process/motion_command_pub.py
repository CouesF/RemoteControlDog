import time
import os
import sys

from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelPublisher

sys.path.append("/home/d3lab/Projects/RemoteControlDog/robot_dog_python/communication")
from dds_data_structure import MyMotionCommand

def send_motion_command(command_type, state_enum=5, angle1=0.0, angle2=0.0, x=0.0, y=0.0, r=0.0, command_id=0):
    msg = MyMotionCommand(
        command_type=command_type,
        state_enum=state_enum,
        angle1=angle1,
        angle2=angle2,
        x=x,
        y=y,
        r=r,
        command_id=command_id
    )
    publisher.Write(msg)
    print(f"[Publisher] Sent: {msg}")

if __name__ == "__main__":
    ChannelFactoryInitialize(0, "enP8p1s0")
    publisher = ChannelPublisher("rt/keyboard_control", MyMotionCommand)
    publisher.Init()

    print("=== MotionCommand Publisher ===")
    print("0: 状态切换  | 1: 抬腿控制  | 2: 导航控制")
    print("输入示例：0 s   |   1 1.2 -1.8   |   1 q   |   2 0.3 0 0")
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
                # 状态切换
                state_char = parts[1].lower()
                state_enum_map = {'h': 5, 'l': 6, 's': 7, 'd': 8}
                if state_char in state_enum_map:
                    send_motion_command(0, state_enum=state_enum_map[state_char])
                else:
                    print("[Error] 无效的状态字符，请使用 h/l/s/d")

            elif cmd_type == 1:
                # 抬腿控制：支持两种模式（角度控制 或 q 退出）
                if len(parts) == 2 and parts[1].lower() == 'q':
                    send_motion_command(1, command_id=ord('q'))
                elif len(parts) == 3:
                    angle1 = float(parts[1])
                    angle2 = float(parts[2])
                    send_motion_command(1, angle1=angle1, angle2=angle2)
                else:
                    print("[Error] 抬腿控制格式错误，应为 1 q 或 1 angle1 angle2")

            elif cmd_type == 2 and len(parts) == 4:
                x, y, r = float(parts[1]), float(parts[2]), float(parts[3])
                send_motion_command(2, x=x, y=y, r=r)

            else:
                print("[Error] 指令格式错误，请重试")

        except Exception as e:
            print(f"[Exception] {e}")
