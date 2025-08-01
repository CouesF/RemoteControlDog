import time
import sys
import os

from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelPublisher

sys.path.append("/home/d3lab/Projects/RemoteControlDog/robot_dog_python/communication")
from dds_data_structure import MyMotionCommand

def send_motion_command(command_type, state_enum=5, leg_selection=0, angle1=0.0, angle2=0.0,
                       x=0.0, y=0.0, r=0.0, command_id=0,
                       hl_roll=0.0, hl_pitch=0.0, hl_yaw=0.0, hl_bodyheight=0.0):
    msg = MyMotionCommand(
        command_type=command_type,
        state_enum=state_enum,
        leg_selection=leg_selection,
        angle1=angle1,
        angle2=angle2,
        x=x,
        y=y,
        r=r,
        command_id=command_id,
        hl_roll=hl_roll,
        hl_pitch=hl_pitch,
        hl_yaw=hl_yaw,
        hl_bodyheight=hl_bodyheight,
    )
    publisher.Write(msg)
    print(f"[Publisher] Sent: {msg}")

if __name__ == "__main__":
    ChannelFactoryInitialize(0, "enP8p1s0")
    publisher = ChannelPublisher("rt/my_motion_command", MyMotionCommand)
    publisher.Init()

    print("""=== MyMotionCommand Publisher ===
格式说明：
  0 h/l/s/d/p         # 状态切换：h=HIGH_LEVEL_STAND(5), l=LOW_LEVEL_STAND(7), s=LOW_LEVEL_RAISE_LEG(10), d=HIGH_LEVEL_DAMP(8), p=HIGH_LEVEL_STAND_DOWN(13)
  0 s l/r             # 进入抬腿，l=左前腿(LF), r=右前腿(RF)，必须加l/r
  1 angle1 angle2     # 设置RF_1 / RF_2目标角度（单位：rad）
  2 x y r             # 高层控制中行走命令（AI模式下使用）
  3 roll pitch yaw h  # 单独设置高层Euler和bodyheight（弧度，单位：米），无状态切换
  q                   # 退出程序

[特别说明]：趴下状态只能用 0 p 切换，不能再用 2 p、2 s！！
""")

    state_enum_map = {
        'h': 5,   # HIGH_LEVEL_STAND
        'l': 7,   # LOW_LEVEL_STAND
        's': 10,  # LOW_LEVEL_RAISE_LEG
        'd': 8,   # HIGH_LEVEL_DAMP
        'p': 13,  # HIGH_LEVEL_STAND_DOWN（趴下）
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

            if cmd_type == 0:
                # 0 s l/r
                if len(parts) == 3 and parts[1].lower() == 's' and parts[2].lower() in ['l', 'r']:
                    leg_selection = 1 if parts[2].lower() == 'l' else 0
                    send_motion_command(0, state_enum=10, leg_selection=leg_selection)
                elif len(parts) == 2 and parts[1].lower() == 's':
                    print("[Error] 抬腿指令需指定l或r，如 0 s l 或 0 s r")
                elif len(parts) == 2 and parts[1].lower() in state_enum_map:
                    send_motion_command(0, state_enum=state_enum_map[parts[1].lower()])
                else:
                    print("[Error] 状态切换格式错误，请使用 0 h/l/s/d/p 或 0 s l/r")

            elif cmd_type == 1:
                if len(parts) == 3:
                    try:
                        angle1 = float(parts[1])
                        angle2 = float(parts[2])
                        send_motion_command(1, angle1=angle1, angle2=angle2)
                    except Exception:
                        print("[Error] 抬腿控制格式错误，应为 1 angle1 angle2（单位：rad）")
                else:
                    print("[Error] 抬腿控制格式错误，仅支持 1 angle1 angle2")

            elif cmd_type == 2:
                if len(parts) == 4:
                    try:
                        x, y, r_ = float(parts[1]), float(parts[2]), float(parts[3])
                        send_motion_command(2, x=x, y=y, r=r_)
                    except Exception:
                        print("[Error] 高层运动控制格式应为 2 x y r")
                else:
                    print("[Error] 2 指令仅支持 2 x y r (高层行走)")

            elif cmd_type == 3:
                # 3 roll pitch yaw h
                if len(parts) == 5:
                    try:
                        roll, pitch, yaw, h = map(float, parts[1:5])
                        send_motion_command(3, hl_roll=roll, hl_pitch=pitch, hl_yaw=yaw, hl_bodyheight=h)
                    except Exception:
                        print("[Error] 3 指令格式应为 3 roll pitch yaw h")
                else:
                    print("[Error] 3 指令仅支持 3 roll pitch yaw h")


            else:
                print("[Error] 指令格式错误，请重试")

        except Exception as e:
            print(f"[Exception] {e}")
