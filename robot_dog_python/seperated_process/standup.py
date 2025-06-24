import time
from unitree_sdk2py.core.channel import ChannelFactoryInitialize
from unitree_sdk2py.go2.sport.sport_client import SportClient

# 初始化 DDS 通道
ChannelFactoryInitialize(0, "enP8p1s0")  # 👈 替换为你自己的网卡名

# 初始化运动控制客户端
client = SportClient()
client.Init()

# 调用恢复站立（如果有电机或 IMU 错误）
print("[INFO] 执行 RecoveryStand()...")
client.RecoveryStand()
time.sleep(1.0)

# 调用站立指令（关节锁定、站高）
print("[INFO] 执行 StandUp()...")
client.StandUp()

print("[INFO] 站立命令已发送完成。狗应该在高层模式下站起。")
