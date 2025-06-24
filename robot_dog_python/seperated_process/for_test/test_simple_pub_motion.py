import sys
import os
from time import sleep

# 添加 communication 路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../communication")))

from dds_data_structure import RaiseLegCommand
from unitree_sdk2py.core.channel import ChannelPublisher, ChannelFactoryInitialize

if __name__ == "__main__":
    ChannelFactoryInitialize()

    pub = ChannelPublisher("raise_leg_topic", RaiseLegCommand)
    pub.Init()

    # 示例指令：抬右前腿 FR（编号 0），持续 1500ms
    msg = RaiseLegCommand(command_id=1, leg_index=3, hold_time_ms=1000)
    pub.Write(msg)

    print(f"Published raise leg command: leg={msg.leg_index}, hold={msg.hold_time_ms} ms")
    sleep(1)
