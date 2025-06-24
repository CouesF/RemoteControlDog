import time
import sys
import os

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from raise_leg_controller import main as raise_leg_main  # 假设上面代码保存在 raise_leg_controller.py 中


def start_raise_leg_sequence():
    print("[Runner] 开始调用 Raise Leg Controller 模块...")
    try:
        raise_leg_main()
    except KeyboardInterrupt:
        print("[Runner] 用户中断程序。")
    except Exception as e:
        print(f"[Runner] 程序执行出错: {e}")


if __name__ == '__main__':
    input("[Runner] 请确保机器人通电并处于 AI 模式，按回车开始调用 Raise Leg 动作模块...")
    start_raise_leg_sequence()
