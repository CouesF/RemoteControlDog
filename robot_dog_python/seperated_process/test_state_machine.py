import time
import threading
from enum import IntEnum
import sys
import os

from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelSubscriber, ChannelPublisher

# 添加路径
sys.path.append("/home/d3lab/Projects/RemoteControlDog/robot_dog_python/communication")
from dds_data_structure import MyMotionCommand

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


def get_current_state():
    with fsm_lock:
        return current_state


def switch_state(state_enum: int):
    global current_state

    with fsm_lock:
        if state_enum == FSMStateEnum.DAMP:
            print("[FSM] 当前状态:", current_state.name)
            print("[FSM] 尝试切换到 DAMP 模式...")

            try:
                if current_state == FSMStateEnum.HIGH_LEVEL:
                    from unitree_sdk2py.go2.sport.sport_client import SportClient
                    sport = SportClient(); sport.Init(); sport.Damp()
                    print("[FSM] 已从 HIGH_LEVEL 成功切入 DAMP")
                elif current_state in [FSMStateEnum.LOW_LEVEL, FSMStateEnum.LOW_LEVEL_STAND]:
                    from unitree_sdk2py.comm.motion_switcher.motion_switcher_client import MotionSwitcherClient
                    msc = MotionSwitcherClient(); msc.Init(); msc.SetTimeout(5.0)
                    ret, _ = msc.SelectMode("damp")
                    if ret == 0:
                        print("[FSM] 已从底层成功切入 DAMP")
                    else:
                        print(f"[FSM] 切换失败，错误码: {ret}")
                        return
                else:
                    print("[FSM] 当前状态不支持切入 DAMP")
                    return

                current_state = FSMStateEnum.DAMP

            except Exception as e:
                print(f"[FSM] 切入 DAMP 模式失败: {e}")
            return

        if current_state == FSMStateEnum.HIGH_LEVEL:
            if state_enum == FSMStateEnum.LOW_LEVEL_STAND:
                print("[FSM] HIGH_LEVEL → LOW_LEVEL_STAND")
                current_state = FSMStateEnum.LOW_LEVEL_STAND
            else:
                print(f"[FSM] 无法从 HIGH_LEVEL 切换到 {state_enum}")

        elif current_state == FSMStateEnum.LOW_LEVEL_STAND:
            if state_enum == FSMStateEnum.HIGH_LEVEL:
                print("[FSM] LOW_LEVEL_STAND → HIGH_LEVEL：将先趴下并切 AI")
                lie_down_and_switch_to_ai()
                current_state = FSMStateEnum.HIGH_LEVEL

            elif state_enum == FSMStateEnum.LOW_LEVEL:
                print("[FSM] LOW_LEVEL_STAND → LOW_LEVEL")
                current_state = FSMStateEnum.LOW_LEVEL

            elif state_enum == FSMStateEnum.DAMP:
                print("[FSM] LOW_LEVEL_STAND → DAMP：将先趴下并切 AI 再切阻尼")

                from control.low_level_controller import lie_down_and_switch_to_ai
                from unitree_sdk2py.comm.motion_switcher.motion_switcher_client import MotionSwitcherClient

                lie_down_and_switch_to_ai()
                time.sleep(2.0)

                msc = MotionSwitcherClient(); msc.Init(); msc.SetTimeout(5.0)
                ret, _ = msc.SelectMode("damp")
                if ret == 0:
                    print("[FSM] 已成功切换到 DAMP")
                    current_state = FSMStateEnum.DAMP
                else:
                    print(f"[FSM] 切换 DAMP 失败，错误码: {ret}")


        elif current_state == FSMStateEnum.LOW_LEVEL:
            if state_enum == FSMStateEnum.LOW_LEVEL_STAND:
                print("[FSM] LOW_LEVEL → LOW_LEVEL_STAND")
                current_state = FSMStateEnum.LOW_LEVEL_STAND
            else:
                print(f"[FSM] 无法从 LOW_LEVEL 切换到 {state_enum}")

        else:
            print(f"[FSM] 当前状态 {current_state.name} 不支持切换到 {state_enum}")

def listener_loop():
    subscriber = ChannelSubscriber("rt/keyboard_control", MyMotionCommand)
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
    last_state = None
    active_thread = None

    def run_behavior(state):
        if state == FSMStateEnum.HIGH_LEVEL:
            run_highlevel_behavior()
        elif state == FSMStateEnum.LOW_LEVEL:
            run_lowlevel_leg_control()
        elif state == FSMStateEnum.LOW_LEVEL_STAND:
            run_lowlevel_stand_hold()
        elif state == FSMStateEnum.DAMP:
            run_damp()

    while True:
        with fsm_lock:
            state_now = current_state

        if state_now != last_state:
            print(f"[FSM] 状态变化：{last_state} → {state_now}")

            # 如果前一个行为线程还活着，标记它应该退出
            if active_thread and active_thread.is_alive():
                print("[FSM] 停止旧状态行为线程（注意：必须行为函数支持退出机制）")

            # 启动新状态线程
            active_thread = threading.Thread(target=run_behavior, args=(state_now,))
            active_thread.start()

            last_state = state_now

        time.sleep(0.2)


if __name__ == "__main__":
    ChannelFactoryInitialize(0, "enP8p1s0")

    # 使用 ChannelPublisher 注册 MyMotionCommand 类型
    dummy_publisher = ChannelPublisher("rt/keyboard_control", MyMotionCommand)
    dummy_publisher.Init()

    threading.Thread(target=listener_loop, daemon=True).start()
    main_loop()
