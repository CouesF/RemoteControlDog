import sys
import os
from time import sleep

# 添加 communication 模块路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../communication")))

# 导入测试结构
from dds_data_structure import SimpleIntTest
from unitree_sdk2py.core.channel import ChannelPublisher, ChannelFactoryInitialize

if __name__ == "__main__":
    # 初始化 DDS 工厂
    ChannelFactoryInitialize()

    # 创建 Publisher（topic 名可自定义）
    pub = ChannelPublisher("simple_int_topic", SimpleIntTest)
    pub.Init()

    # 构造消息
    msg = SimpleIntTest(command_id=42, value=999)

    # 发布
    pub.Write(msg)
    print(f"Published: command_id={msg.command_id}, value={msg.value}")

    sleep(1)
