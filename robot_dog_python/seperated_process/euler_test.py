import time
import threading

from unitree_sdk2py.core.channel import ChannelFactoryInitialize
from unitree_sdk2py.go2.sport.sport_client import SportClient
from unitree_sdk2py.comm.motion_switcher.motion_switcher_client import MotionSwitcherClient

ROLL_RANGE = (-0.75, 0.75)
PITCH_RANGE = (-0.75, 0.75)
YAW_RANGE = (-0.6, 0.6)
BODYHEIGHT_RANGE = (-0.18, 0.03)

class RobotTestDemo:
    def __init__(self, network_interface="enP8p1s0"):
        ChannelFactoryInitialize(0, network_interface)
        self.sport = SportClient()
        self.sport.SetTimeout(10.0)
        self.sport.Init()
        self.msc = MotionSwitcherClient()
        self.msc.Init()
        self.roll = 0.0
        self.pitch = 0.0
        self.yaw = 0.0
        self.bodyheight = 0.0
        self.running = True
        self.bs_active = False
        self.send_thread = None

    def select_mode(self):
        while True:
            s = input("请选择模式 (ai / normal / advanced): ").strip().lower()
            if s in ("ai", "normal", "advanced"):
                print(f"[INFO] 正在切换到 {s} 模式...")
                self.msc.SelectMode(s)
                time.sleep(1)
                status, result = self.msc.CheckMode()
                if result and isinstance(result, dict) and 'name' in result:
                    print(f"[INFO] 当前模式: {result.get('name')}")
                else:
                    print(f"[INFO] 当前模式未知（可能SDK不支持/未响应，status={status}，result={result}）")
                break
            else:
                print("[WARN] 请输入 ai / normal / advanced 之一")


    def send_balance_loop(self):
        while self.running and self.bs_active:
            self.sport.Euler(self.roll, self.pitch, self.yaw)
            self.sport.BodyHeight(self.bodyheight)
            time.sleep(0.01)

    def start_balance_stand(self):
        print("[INFO] 进入 balance stand，持续发送欧拉角与高度")
        self.bs_active = True
        self.sport.Euler(self.roll, self.pitch, self.yaw)
        self.sport.BodyHeight(self.bodyheight)
        self.sport.BalanceStand()
        self.send_thread = threading.Thread(target=self.send_balance_loop, daemon=True)
        self.send_thread.start()

    def stop_balance_stand(self):
        self.bs_active = False
        if self.send_thread and self.send_thread.is_alive():
            self.send_thread.join(timeout=0.2)
        print("[INFO] 已停止 balance stand 持续发送")

    def stand_down(self):
        print("[INFO] 执行 StandDown")
        self.stop_balance_stand()
        self.sport.StandDown()

    def update_euler_bodyheight(self, kind, value):
        if kind == "roll":
            value = max(ROLL_RANGE[0], min(ROLL_RANGE[1], value))
            self.roll = value
            print(f"[INFO] roll更新为 {value}")
        elif kind == "pitch":
            value = max(PITCH_RANGE[0], min(PITCH_RANGE[1], value))
            self.pitch = value
            print(f"[INFO] pitch更新为 {value}")
        elif kind == "yaw":
            value = max(YAW_RANGE[0], min(YAW_RANGE[1], value))
            self.yaw = value
            print(f"[INFO] yaw更新为 {value}")
        elif kind == "bodyheight":
            value = max(BODYHEIGHT_RANGE[0], min(BODYHEIGHT_RANGE[1], value))
            self.bodyheight = value
            print(f"[INFO] bodyheight更新为 {value}")

    def run(self):
        self.select_mode()
        print("\n请选择要执行的动作：\n1. balance stand\n2. stand down\n输入 1 或 2：")
        while True:
            act = input().strip()
            if act == "1":
                self.start_balance_stand()
                break
            elif act == "2":
                self.stand_down()
                break
            else:
                print("[WARN] 请输入 1 或 2")
        print('''
交互指令：
- roll x   （设置roll，x为数值）
- pitch x  （设置pitch，x为数值）
- yaw x    （设置yaw，x为数值）
- h x      （设置bodyheight，x为数值）
- d        （执行 stand down，停止持续发送）
- b        （重新 balance stand 并恢复持续发送）
- q        （退出程序）
当前所有姿态参数初始为0
''')
        try:
            while True:
                s = input("输入指令: ").strip()
                if s == "q":
                    break
                elif s == "d":
                    self.stand_down()
                elif s == "b":
                    self.start_balance_stand()
                elif s.startswith("roll "):
                    try:
                        val = float(s.split()[1])
                        self.update_euler_bodyheight("roll", val)
                    except:
                        print("[WARN] 格式: roll x")
                elif s.startswith("pitch "):
                    try:
                        val = float(s.split()[1])
                        self.update_euler_bodyheight("pitch", val)
                    except:
                        print("[WARN] 格式: pitch x")
                elif s.startswith("yaw "):
                    try:
                        val = float(s.split()[1])
                        self.update_euler_bodyheight("yaw", val)
                    except:
                        print("[WARN] 格式: yaw x")
                elif s.startswith("h "):
                    try:
                        val = float(s.split()[1])
                        self.update_euler_bodyheight("bodyheight", val)
                    except:
                        print("[WARN] 格式: h x")
                else:
                    print("[WARN] 未知指令。支持: roll/pitch/yaw/h/d/b/q")
        finally:
            print("[INFO] 程序退出，恢复balance stand，所有值归零")
            self.roll = self.pitch = self.yaw = self.bodyheight = 0.0
            self.start_balance_stand()
            time.sleep(0.3)
            self.stop_balance_stand()

if __name__ == "__main__":
    import sys
    netif = sys.argv[1] if len(sys.argv) > 1 else "enP8p1s0"
    demo = RobotTestDemo(netif)
    demo.run()
