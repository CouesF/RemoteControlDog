import time
import sys

from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelSubscriber
from unitree_sdk2py.idl.unitree_go.msg.dds_ import LowState_

DDS_NETWORK_INTERFACE = "enP8p1s0"

class MotorStateMonitor:
    def __init__(self):
        self.low_state = None
        # Directly include LegID to avoid external import
        self.LegID = {
            "FR_0": 0,  # Front right hip
            "FR_1": 1,  # Front right thigh
            "FR_2": 2,  # Front right calf
            "FL_0": 3,
            "FL_1": 4,
            "FL_2": 5,
            "RR_0": 6,
            "RR_1": 7,
            "RR_2": 8,
            "RL_0": 9,
            "RL_1": 10,
            "RL_2": 11,
        }
        self.motor_names = list(self.LegID.keys())

    def LowStateMessageHandler(self, msg: LowState_):
        """
        处理LowState消息的回调函数。
        """
        self.low_state = msg

    def get_motor_states(self):
        """
        获取并打印12个电机的当前状态（角度、速度、扭矩）。
        """
        if self.low_state is None:
            print("Waiting for motor state data...")
            return

        print("\n--- Go2 Motor States ---")
        for i in range(12):  # Go2机器狗有12个电机
            motor_id = self.motor_names[i] # 获取电机名称
            motor_state = self.low_state.motor_state[i]
            
            # 关节反馈位置（当前角度）
            q = motor_state.q
            # 关节反馈速度
            dq = motor_state.dq
            # 关节反馈力矩
            tau_est = motor_state.tau_est

            print(f"[{motor_id}]")
            print(f"  Current Angle (q): {q:.4f} rad")
            print(f"  Velocity (dq): {dq:.4f} rad/s")
            print(f"  Torque (tau_est): {tau_est:.4f} Nm")
        print("------------------------")

if __name__ == '__main__':
    # 初始化DDS通信
    # networkInterface参数可以根据需要进行修改
    ChannelFactoryInitialize(networkInterface=DDS_NETWORK_INTERFACE) #

    monitor = MotorStateMonitor()

    # 创建订阅者，订阅rt/lowstate话题
    # Init方法的第二个参数是回调函数，第三个参数是消息缓存队列的长度
    monitor_subscriber = ChannelSubscriber("rt/lowstate", LowState_) #
    monitor_subscriber.Init(monitor.LowStateMessageHandler, 10) #

    print("Monitoring Go2 motor states. Press Ctrl+C to exit.")

    try:
        while True:
            monitor.get_motor_states()
            time.sleep(1)  # 每秒更新一次显示
    except KeyboardInterrupt:
        print("\nExiting motor state monitor.")
    finally:
        # 在程序退出前关闭订阅者
        monitor_subscriber.CloseChannel() #