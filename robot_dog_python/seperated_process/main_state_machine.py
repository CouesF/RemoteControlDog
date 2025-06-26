import time
import threading
from enum import IntEnum
import sys
import os

from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelSubscriber

# 添加路径
sys.path.append("/home/d3lab/Projects/RemoteControlDog/robot_dog_python/communication")
from dds_data_structure import MotionCommand

# 控制模块
from control.high_level_controller import run_highlevel_behavior, run_damp
from control.low_level_controller import run_lowlevel_leg_control, lie_down_and_switch_to_ai
from control.low_level_stand_controller import run_lowlevel_stand_hold


class FSMStateEnum(IntEnum):
    HIGH_LEVEL = 5
    LOW_LEVEL = 6
    LOW_LEVEL_STAND = 7
    DAMP = 8

current_state = FSMStateEnum.HIGH_LEVEL
fsm_lock = threading.Lock()

def switch_state(state_enum: int):
    global current_state

    with fsm_lock:
        if state_enum == FSMStateEnum.DAMP:
            print("[FSM] 切换到 DAMP 模式")
            current_state = FSMStateEnum.DAMP
            return

        if current_state == FSMStateEnum.HIGH_LEVEL:
            if state_enum == FSMStateEnum.LOW_LEVEL_STAND:
                print("[FSM] HIGH_LEVEL → LOW_LEVEL_STAND")
                current_state = FSMStateEnum.LOW_LEVEL_STAND
            else:
                print(f"[FSM] 无法从 HIGH_LEVEL 切换到 {state_enum}")

        elif current_state == FSMStateEnum.LOW_LEVEL_STAND:
            if state_enum == FSMStateEnum.HIGH_LEVEL:
                print("[FSM] LOW_LEVEL_STAND → HIGH_LEVEL（将先趴下并切换AI）")
                current_state = FSMStateEnum.HIGH_LEVEL
                threading.Thread(target=lie_down_and_switch_to_ai).start()
            elif state_enum == FSMStateEnum.LOW_LEVEL:
                print("[FSM] LOW_LEVEL_STAND → LOW_LEVEL")
                current_state = FSMStateEnum.LOW_LEVEL
            else:
                print(f"[FSM] 无法从 LOW_LEVEL_STAND 切换到 {state_enum}")

        elif current_state == FSMStateEnum.LOW_LEVEL:
            if state_enum == FSMStateEnum.LOW_LEVEL_STAND:
                print("[FSM] LOW_LEVEL → LOW_LEVEL_STAND")
                current_state = FSMStateEnum.LOW_LEVEL_STAND
            else:
                print(f"[FSM] 无法从 LOW_LEVEL 切换到 {state_enum}")

        else:
            print(f"[FSM] 当前状态 {current_state.name} 不支持切换到 {state_enum}")

def listener_loop():
    subscriber = ChannelSubscriber("rt/keyboard_control", MotionCommand)
    subscriber.Init()

    while True:
        msg = subscriber.Read()
        if msg is None:
            time.sleep(0.01)
            continue

        with fsm_lock:
            state_now = current_state

        if msg.command_type == 0:
            switch_state(msg.state_enum)

        elif msg.command_type == 1 and state_now == FSMStateEnum.LOW_LEVEL:
            from control.low_level_controller import update_leg_angles
            update_leg_angles(msg.angle1, msg.angle2)

        elif msg.command_type == 2 and state_now == FSMStateEnum.HIGH_LEVEL:
            from control.high_level_controller import update_navigation_target
            update_navigation_target(msg.x, msg.y, msg.r)

def main_loop():
    while True:
        with fsm_lock:
            state_now = current_state

        print(f"[FSM] 当前状态: {state_now.name}")

        if state_now == FSMStateEnum.HIGH_LEVEL:
            run_highlevel_behavior()
        elif state_now == FSMStateEnum.LOW_LEVEL:
            run_lowlevel_leg_control()
        elif state_now == FSMStateEnum.LOW_LEVEL_STAND:
            run_lowlevel_stand_hold()
        elif state_now == FSMStateEnum.DAMP:
            run_damp()

        print("[FSM] 等待指令中...\n")
        time.sleep(1)

if __name__ == "__main__":
    ChannelFactoryInitialize(0, "enP8p1s0")
    threading.Thread(target=listener_loop, daemon=True).start()
    main_loop()
