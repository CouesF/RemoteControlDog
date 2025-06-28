import time
from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelPublisher
from unitree_sdk2py.idl.unitree_go.msg.dds_ import LowCmd_
from unitree_sdk2py.idl.default import unitree_go_msg_dds__LowCmd_
from unitree_sdk2py.utils.crc import CRC

def run_lowlevel_damp():
    print("[Test] 模拟进入低层阻尼模式（Damp）...")

    # 初始化 DDS 通道
    ChannelFactoryInitialize(0, "enP8p1s0")  
    publisher = ChannelPublisher("rt/lowcmd", LowCmd_)
    publisher.Init()

    low_cmd = unitree_go_msg_dds__LowCmd_()
    crc = CRC()

    while True:
        for i in range(12):
            low_cmd.motor_cmd[i].mode = 0x01     # 控制模式
            low_cmd.motor_cmd[i].q = 0.0         # 角度值无效
            low_cmd.motor_cmd[i].dq = 0.0        # 静止速度
            low_cmd.motor_cmd[i].kp = 0.0        # 无刚度
            low_cmd.motor_cmd[i].kd = 2.0        # 阻尼系数
            low_cmd.motor_cmd[i].tau = 0.0       # 力矩为 0

        low_cmd.crc = crc.Crc(low_cmd)
        publisher.Write(low_cmd)

        time.sleep(0.01)

if __name__ == "__main__":
    run_lowlevel_damp()
