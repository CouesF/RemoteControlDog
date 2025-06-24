import time
import sys
import os
import threading

from unitree_sdk2py.core.channel import ChannelPublisher, ChannelFactoryInitialize
from unitree_sdk2py.idl.unitree_go.msg.dds_ import LowCmd_
from unitree_sdk2py.idl.default import unitree_go_msg_dds__LowCmd_
from unitree_sdk2py.utils.crc import CRC
from unitree_sdk2py.comm.motion_switcher.motion_switcher_client import MotionSwitcherClient
from unitree_sdk2py.go2.sport.sport_client import SportClient

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../unitree_example/go2/low_level")))
import unitree_legged_const as go2

def interpolate_pose(start, end, percent):
    return [(1 - percent) * s + percent * e for s, e in zip(start, end)]

def interpolate_selected_joints(start_pos, target, joint_indices, duration_ms, low_cmd, publisher, crc, kp_override=None, kd_override=None):
    for step in range(duration_ms):
        alpha = min(1.0, step / duration_ms)
        q_interp = interpolate_pose(start_pos, target, alpha)
        for i in range(12):
            low_cmd.motor_cmd[i].mode = 0x01
            low_cmd.motor_cmd[i].dq = 0
            low_cmd.motor_cmd[i].tau = 0
            low_cmd.motor_cmd[i].q = q_interp[i] if i in joint_indices else start_pos[i]
            low_cmd.motor_cmd[i].kp = kp_override[i] if kp_override else 100.0
            low_cmd.motor_cmd[i].kd = kd_override[i] if kd_override else 8.0
        low_cmd.crc = crc.Crc(low_cmd)
        publisher.Write(low_cmd)
        time.sleep(0.002)

def maintain_posture(target_pose, low_cmd, publisher, crc, stop_flag, kp_profile=None, kd_profile=None):
    while not stop_flag["stop"]:
        for j in range(12):
            low_cmd.motor_cmd[j].mode = 0x01
            low_cmd.motor_cmd[j].q = target_pose[j]
            low_cmd.motor_cmd[j].dq = 0
            low_cmd.motor_cmd[j].kp = kp_profile[j] if kp_profile else 100.0
            low_cmd.motor_cmd[j].kd = kd_profile[j] if kd_profile else 8.0
            low_cmd.motor_cmd[j].tau = 0
        low_cmd.crc = crc.Crc(low_cmd)
        publisher.Write(low_cmd)
        time.sleep(0.002)

if __name__ == '__main__':
    ChannelFactoryInitialize(0, "enP8p1s0")
    low_cmd = unitree_go_msg_dds__LowCmd_()
    crc = CRC()
    msc = MotionSwitcherClient(); msc.Init(); msc.SetTimeout(5.0)
    publisher = ChannelPublisher("rt/lowcmd", LowCmd_); publisher.Init()
    sport = SportClient(); sport.Init()

    sport.Damp()
    status, result = msc.CheckMode()
    if result['name'] != 'ai':
        print("[Error] 需手动切换至 AI 模式"); sys.exit(1)

    time.sleep(1); sport.StandUp()
    input("[User] 回车切换到低层模式")

    while True:
        msc.ReleaseMode(); time.sleep(0.01)
        status, result = msc.CheckMode()
        if result.get("name", "") == "": break

    stand_pos = [0.0, 0.67, -1.3] * 4
    stop_flag = {"stop": False}
    thread = threading.Thread(target=maintain_posture, args=(stand_pos, low_cmd, publisher, crc, stop_flag))
    thread.start()
    input("[User] 当前为标准站立，回车继续...")
    stop_flag["stop"] = True; thread.join()

    # 三条腿加硬配置
    high_kp = [100.0]*12; high_kd = [8.0]*12
    for i in [0,1,2, 3,4,5, 9,10,11]:  # LF, RF, RL
        high_kp[i] = 160.0
        high_kd[i] = 10.0

    # 弯曲左后腿并外摆
    step1 = stand_pos[:]
    step1[11] -= 0.3  # RL_2 calf 向上
    step1[9]  += 0.3  # RL_0 hip 外摆
    interpolate_selected_joints(stand_pos, step1, [9,11], 650, low_cmd, publisher, crc, high_kp, high_kd)

    # 保持 step1 姿态线程
    stop_flag_hold1 = {"stop": False}
    thread_hold1 = threading.Thread(target=maintain_posture, args=(step1, low_cmd, publisher, crc, stop_flag_hold1, high_kp, high_kd))
    thread_hold1.start()
    input("[User] 保持 RL 弯曲外摆姿态，按回车继续弯曲右前腿")
    stop_flag_hold1["stop"] = True
    thread_hold1.join()

    # 弯曲右前腿
    step2 = step1[:]
    step2[2] -= 0.8  # RF_2 calf 弯曲
    interpolate_selected_joints(step1, step2, [2], 250, low_cmd, publisher, crc, high_kp, high_kd)

    # === 新增动作：向前摆 thigh（关节1），再伸直 calf（关节2） ===
    step3 = step2[:]
    step3[1] -= 1.0  # RF_1 thigh 向前摆
    interpolate_selected_joints(step2, step3, [1], 250, low_cmd, publisher, crc, high_kp, high_kd)

    step4 = step3[:]
    step4[2] = stand_pos[2]  # RF_2 calf 伸直，回归站立角度
    interpolate_selected_joints(step3, step4, [2], 250, low_cmd, publisher, crc, high_kp, high_kd)

    # 保持 step4 姿态
    stop_flag_hold2 = {"stop": False}
    thread_hold2 = threading.Thread(target=maintain_posture, args=(step4, low_cmd, publisher, crc, stop_flag_hold2, high_kp, high_kd))
    thread_hold2.start()
    input("[User] 当前保持 RF 摆腿 + 伸直，按回车继续恢复正常站立...")
    stop_flag_hold2["stop"] = True
    thread_hold2.join()

    # === 新增：依次调整 RF_0 → RF_1 → RF_2 增加 0.1 ===
    step5 = step4[:]
    step5[0] -= 0.3  # RF_0 hip
    interpolate_selected_joints(step4, step5, [0], 350, low_cmd, publisher, crc, high_kp, high_kd)

    step6 = step5[:]
    step6[1] += 0.0  # RF_1 thigh
    interpolate_selected_joints(step5, step6, [1], 250, low_cmd, publisher, crc, high_kp, high_kd)

    step7 = step6[:]
    step7[2] += 0.0  # RF_2 calf
    interpolate_selected_joints(step6, step7, [2], 250, low_cmd, publisher, crc, high_kp, high_kd)

    # === 保持最终姿态（step7）线程 ===
    stop_flag_hold3 = {"stop": False}
    thread_hold3 = threading.Thread(target=maintain_posture, args=(step7, low_cmd, publisher, crc, stop_flag_hold3, high_kp, high_kd))
    thread_hold3.start()
    input("[User] 当前为 RF 三关节调整后姿态，回车继续恢复...")
    stop_flag_hold3["stop"] = True
    thread_hold3.join()


    # === 分阶段恢复：RF_0 → RF_1 → RF_2 → RL_0 → RL_1 → RL_2 ===
    restore_step1 = step7[:]
    restore_step1[0] = stand_pos[0]  # RF_0
    interpolate_selected_joints(step7, restore_step1, [0], 300, low_cmd, publisher, crc)

    restore_step2 = restore_step1[:]
    restore_step2[1] = stand_pos[1]  # RF_1
    interpolate_selected_joints(restore_step1, restore_step2, [1], 300, low_cmd, publisher, crc)

    restore_step3 = restore_step2[:]
    restore_step3[2] = stand_pos[2]  # RF_2
    interpolate_selected_joints(restore_step2, restore_step3, [2], 300, low_cmd, publisher, crc)

    restore_step4 = restore_step3[:]
    restore_step4[9] = stand_pos[9]  # RL_0
    interpolate_selected_joints(restore_step3, restore_step4, [9], 400, low_cmd, publisher, crc)

    restore_step5 = restore_step4[:]
    restore_step5[10] = stand_pos[10]  # RL_1
    interpolate_selected_joints(restore_step4, restore_step5, [10], 400, low_cmd, publisher, crc)

    restore_step6 = restore_step5[:]
    restore_step6[11] = stand_pos[11]  # RL_2
    interpolate_selected_joints(restore_step5, restore_step6, [11], 400, low_cmd, publisher, crc)


    # 全部腿硬度恢复
    stop_flag3 = {"stop": False}
    thread3 = threading.Thread(target=maintain_posture, args=(stand_pos, low_cmd, publisher, crc, stop_flag3))
    thread3.start()
    input("[User] 回车趴下")
    stop_flag3["stop"] = True; thread3.join()

    # 趴下姿势
    lie_down_pose = [-0.35, 1.36, -2.65, 0.35, 1.36, -2.65,
                     -0.5, 1.36, -2.65, 0.5, 1.36, -2.65]
    interpolate_selected_joints(stand_pos, lie_down_pose, list(range(12)), 1500, low_cmd, publisher, crc)
    ret, _ = msc.SelectMode("ai")
    print("[Done] 已切换回 AI 模式" if ret == 0 else f"[Error] 切换失败: {ret}")
