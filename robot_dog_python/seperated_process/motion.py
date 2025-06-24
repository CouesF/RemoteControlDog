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

def interpolate_pose(start, end, percent):
    return [(1 - percent) * s + percent * e for s, e in zip(start, end)]

def interpolate_selected_joints(start_pos, target, joint_indices, duration_ms, low_cmd, publisher, crc):
    for step in range(duration_ms):
        alpha = min(1.0, step / duration_ms)
        q_interp = interpolate_pose(start_pos, target, alpha)
        for i in range(12):
            low_cmd.motor_cmd[i].mode = 0x01
            low_cmd.motor_cmd[i].dq = 0
            low_cmd.motor_cmd[i].tau = 0
            if i in joint_indices:
                low_cmd.motor_cmd[i].q = q_interp[i]
            else:
                low_cmd.motor_cmd[i].q = start_pos[i]
            low_cmd.motor_cmd[i].kp = 100.0
            low_cmd.motor_cmd[i].kd = 8.0
        low_cmd.crc = crc.Crc(low_cmd)
        publisher.Write(low_cmd)
        time.sleep(0.002)

def maintain_posture(target_pose, low_cmd, publisher, crc, stop_flag):
    while not stop_flag["stop"]:
        for j in range(12):
            low_cmd.motor_cmd[j].mode = 0x01
            low_cmd.motor_cmd[j].q = target_pose[j]
            low_cmd.motor_cmd[j].dq = 0
            low_cmd.motor_cmd[j].kp = 100.0
            low_cmd.motor_cmd[j].kd = 8.0
            low_cmd.motor_cmd[j].tau = 0
        low_cmd.crc = crc.Crc(low_cmd)
        publisher.Write(low_cmd)
        time.sleep(0.002)

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

    stand_pos = [0.0, 0.67, -1.3] * 4

    lift_leg_pos = stand_pos[:]
    lift_leg_pos[11] += 0.3
    print("[Action] 轻微抬起左后腿")
    interpolate_selected_joints(stand_pos, lift_leg_pos, [11], 600, low_cmd, publisher, crc)

    move_leg_pos = lift_leg_pos[:]
    move_leg_pos[9] += 0.4
    move_leg_pos[10] += 0.3
    print("[Action] 移动左后腿至目标位置")
    interpolate_selected_joints(lift_leg_pos, move_leg_pos, [9, 10], 800, low_cmd, publisher, crc)

    final_leg_pos = move_leg_pos[:]
    final_leg_pos[11] = stand_pos[11]
    print("[Action] 放下左后腿")
    interpolate_selected_joints(move_leg_pos, final_leg_pos, [11], 600, low_cmd, publisher, crc)

    # === 保持姿态线程1 ===
    stop_flag1 = {"stop": False}
    thread1 = threading.Thread(target=maintain_posture, args=(final_leg_pos, low_cmd, publisher, crc, stop_flag1))
    thread1.start()
    print("[Hold] 左后腿放下后保持站立，按下回车继续执行缓冲动作...")
    input()
    stop_flag1["stop"] = True
    thread1.join()

    # === 新增：右前腿动作 ===
    fr_lift_pos = stand_pos[:]
    fr_lift_pos[5] -= 0.3     # FR_2 calf 抬起更多，拉直小腿
    fr_lift_pos[4] -= 0.1     # FR_1 thigh 稍稍收回，使脚向前抬起
    print("[Action] 抬起右前腿指向前方")
    interpolate_selected_joints(final_leg_pos, fr_lift_pos, [4, 5], 600, low_cmd, publisher, crc)

    print("[Action] 放下右前腿")
    interpolate_selected_joints(fr_lift_pos, final_leg_pos, [4, 5], 600, low_cmd, publisher, crc)

    # === 保持站立线程2 ===
    stop_flag2 = {"stop": False}
    thread2 = threading.Thread(target=maintain_posture, args=(final_leg_pos, low_cmd, publisher, crc, stop_flag2))
    thread2.start()
    print("[Hold] 站立，按下回车执行缓冲动作...")
    input()
    stop_flag2["stop"] = True
    thread2.join()

    # 缓冲回收
    buffer_lift_pos = final_leg_pos[:]
    buffer_lift_pos[11] += 0.3
    print("[Buffer] 再次抬起左后腿用于缓冲")
    interpolate_selected_joints(final_leg_pos, buffer_lift_pos, [11], 600, low_cmd, publisher, crc)

    buffer_retract_pos = buffer_lift_pos[:]
    buffer_retract_pos[9] = stand_pos[9]
    buffer_retract_pos[10] = stand_pos[10]
    print("[Buffer] 回收左后腿 RL_0, RL_1")
    interpolate_selected_joints(buffer_lift_pos, buffer_retract_pos, [9, 10], 800, low_cmd, publisher, crc)

    final_return_pos = buffer_retract_pos[:]
    final_return_pos[11] = stand_pos[11]
    print("[Buffer] 最终放下 RL_2，完成缓冲回收")
    interpolate_selected_joints(buffer_retract_pos, final_return_pos, [11], 600, low_cmd, publisher, crc)

    print("[Final] 稳定一次整体标准站立姿势")
    interpolate_selected_joints(final_return_pos, stand_pos, list(range(12)), 1000, low_cmd, publisher, crc)

    # === 保持姿态线程3 ===
    stop_flag3 = {"stop": False}
    thread3 = threading.Thread(target=maintain_posture, args=(stand_pos, low_cmd, publisher, crc, stop_flag3))
    thread3.start()
    print("[Hold] 当前为标准站立，按下回车准备趴下...")
    input()
    stop_flag3["stop"] = True
    thread3.join()

    # 趴下动作
    lie_down_pose = [-0.35, 1.36, -2.65, 0.35, 1.36, -2.65,
                     -0.5, 1.36, -2.65, 0.5, 1.36, -2.65]
    print("[Action] 平滑过渡到趴下姿势")
    interpolate_selected_joints(stand_pos, lie_down_pose, list(range(12)), 1500, low_cmd, publisher, crc)

    print("[Done] 动作完成，准备切换回 AI 模式")
    time.sleep(0.1)
    ret2, _ = msc.SelectMode("ai")
    if ret2 == 0:
        print("[Action] 已成功切换至 AI 模式")
    else:
        print(f"[Error] 切换到 AI 模式失败，返回码: {ret2}")

    print("[Done] 程序结束")
