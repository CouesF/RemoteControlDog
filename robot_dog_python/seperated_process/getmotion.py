import time
from unitree_sdk2py.core.channel import ChannelSubscriber, ChannelFactoryInitialize
from unitree_sdk2py.idl.unitree_go.msg.dds_ import LowState_

# 12关节对应的名称列表
joint_names = [
    "FR_0 (Right Front Hip)",
    "FR_1 (Right Front Thigh)",
    "FR_2 (Right Front Calf)",
    "FL_0 (Left Front Hip)",
    "FL_1 (Left Front Thigh)",
    "FL_2 (Left Front Calf)",
    "RR_0 (Right Rear Hip)",
    "RR_1 (Right Rear Thigh)",
    "RR_2 (Right Rear Calf)",
    "RL_0 (Left Rear Hip)",
    "RL_1 (Left Rear Thigh)",
    "RL_2 (Left Rear Calf)"
]

def read_and_print_joint_states():
    ChannelFactoryInitialize(0, "enP8p1s0")
    sub = ChannelSubscriber("rt/lowstate", LowState_)
    sub.Init()

    print("Waiting for joint state message...\n")
    while True:
        msg = sub.Read()
        if msg:
            print("Received joint states:\n")
            for i in range(12):
                motor = msg.motor_state[i]
                print(f"{joint_names[i]}:\n"
                    f"  Position (q): {motor.q:.3f} rad\n"
                    f"  Velocity (dq): {motor.dq:.3f} rad/s\n"
                    f"  Torque (tau): {motor.tau_est:.3f} Nm\n")
            print("=== End of Snapshot ===")
            break
        time.sleep(0.01)

if __name__ == "__main__":
    read_and_print_joint_states()
