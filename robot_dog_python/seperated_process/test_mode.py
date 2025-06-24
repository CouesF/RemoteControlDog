from unitree_sdk2py.core.channel import ChannelFactoryInitialize
from unitree_sdk2py.comm.motion_switcher.motion_switcher_client import MotionSwitcherClient

if __name__ == "__main__":
    ChannelFactoryInitialize(0, "enP8p1s0")

    msc = MotionSwitcherClient()
    msc.Init()
    status, result = msc.CheckMode()
    print("当前控制模式：", result["name"])
