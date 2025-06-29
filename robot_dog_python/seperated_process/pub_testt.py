import time
import sys
import os

from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelPublisher

# 修改为你本地 communication 路径
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
    publisher = ChannelPublisher("rt/my_motion_command", MyMotionCommand)
    publisher.Init()

    print("""=== MyMotionCommand Publisher ===
格式说明：
  0 h/l/s/d     # 状态切换：h=HIGH_LEVEL_STAND(5), l=LOW_LEVEL_STAND(7), s=LOW_LEVEL_RAISE_LEG(10), d=自动DAMP(8)
  1 q           # 退出抬腿模式
  1 angle1 angle2   # 设置RF_1 / RF_2目标角度（单位：rad）
  2 x y r       # 高层控制中行走命令（AI模式下使用）
  q             # 退出程序
""")

    state_enum_map = {
        'h': 5,   # HIGH_LEVEL_STAND
        'l': 7,   # LOW_LEVEL_STAND
        's': 10,  # LOW_LEVEL_RAISE_LEG
        'd': 8    # HIGH_LEVEL_DAMP（程序内部会自动判断切 HIGH / LOW）
    }

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
                state_char = parts[1].lower()
                if state_char in state_enum_map:
                    send_motion_command(0, state_enum=state_enum_map[state_char])
                else:
                    print("[Error] 无效状态字符，请使用 h/l/s/d")

            elif cmd_type == 1:
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
