import time

from unitree_sdk2py.core.channel import ChannelFactoryInitialize
from unitree_sdk2py.go2.sport.sport_client import SportClient

def main():
    # 1. 固定网卡名，无需输入参数
    netif = "enP8p1s0"

    # 2. 初始化 DDS 通道
    print(f"[INFO] 初始化 DDS 通道，网卡名：{netif}")
    ChannelFactoryInitialize(0, netif)
    
    # 3. 创建并初始化 SportClient
    client = SportClient()
    client.SetTimeout(10.0)
    client.Init()
    print("[INFO] SportClient 初始化完成。")
    print("请确保 Go2 已进入高层（AI/运动）模式！")
    print("按下对应键后回车可执行动作：")
    print("    b - BalanceStand (平衡站立)")
    print("    p - StandDown    (趴下/站低)")
    print("    r - RecoveryStand(恢复站立)")
    print("    u - StandUp      (站高)")
    print("    q - 退出程序")
    print("-" * 40)

    while True:
        cmd = input("请输入指令 (b/p/r/u/q): ").strip().lower()
        if cmd == 'b':
            ret = client.BalanceStand()
            print(f"[CMD] 执行 BalanceStand，返回值：{ret}")
        elif cmd == 'p':
            ret = client.StandDown()
            print(f"[CMD] 执行 StandDown，返回值：{ret}")
        elif cmd == 'r':
            ret = client.RecoveryStand()
            print(f"[CMD] 执行 RecoveryStand，返回值：{ret}")
        elif cmd == 'u':
            ret = client.StandUp()
            print(f"[CMD] 执行 StandUp，返回值：{ret}")
        elif cmd == 'q':
            print("退出程序")
            break
        else:
            print("无效指令，仅支持 b/p/r/u/q")
        time.sleep(1.0)  # 可选，防止指令过于密集

if __name__ == "__main__":
    main()
