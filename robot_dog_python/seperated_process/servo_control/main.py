#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main.py
将电机位置写入与 Arduino 表情控制封装为函数，可反复调用
"""

from servo_controller import ServoController
from arduino import ArduinoController

# —— 串口配置 ——（根据实际修改）
SERVO_PORT   = '/dev/ttyACM0'
SERVO_BAUD   = 1_000_000
SERVO_TYPE   = 'STS'  # 或 'SCSCL'
ARDUINO_PORT = '/dev/ttyCH341USB0'
ARDUINO_BAUD = 115200

# main.py

def control_targets(m1: int, m2: int, expr: str,
                    sc: ServoController, ad: ArduinoController) -> None:
    """
    核心控制函数：
      - 将 motor1 设为 m1，将 motor2 设为 m2
      - 向 Arduino 发送表情字符 expr
    :param m1: 电机1目标位置 2048
    :param m2: 电机2目标位置 2048
    :param expr: 单字符表情（如 'c','l','r'）
    :param sc: 已初始化的 ServoController 实例
    :param ad: 已初始化的 ArduinoController 实例
    """
    # Define bounds for Motor 1 (ID 1)
    MIN_ALLOWED_POS_M1 = 1600  # 经测试，最大摇头角度幅度大约为39.375°
    MAX_ALLOWED_POS_M1 = 2496  # 为避免破坏结构，暂不进行下一步测试

    # Define bounds for Motor 2 (ID 2)
    MIN_ALLOWED_POS_M2 = 1660 # Example: Set your desired minimum for motor 2
    MAX_ALLOWED_POS_M2 = 2205 # Example: Set your desired maximum for motor 2

    # Check bounds for Motor 1
    if not (MIN_ALLOWED_POS_M1 <= m1 <= MAX_ALLOWED_POS_M1):
        raise ValueError(f"Motor 1 target position {m1} is out of the allowed range "
                         f"[{MIN_ALLOWED_POS_M1}, {MAX_ALLOWED_POS_M1}].")

    # Check bounds for Motor 2
    if not (MIN_ALLOWED_POS_M2 <= m2 <= MAX_ALLOWED_POS_M2):
        raise ValueError(f"Motor 2 target position {m2} is out of the allowed range "
                         f"[{MIN_ALLOWED_POS_M2}, {MAX_ALLOWED_POS_M2}].")

    # 写入电机目标位置
    sc.write_position(1, m1)
    sc.write_position(2, m2)
    print(f"✅ 电机1→{m1}, 电机2→{m2}")

    # 发送表情到 Arduino
    ad.set_expression(expr)
    print(f"✅ 屏幕表情→'{expr}'")


def main():
    # 初始化控制器
    try:
        sc = ServoController(SERVO_PORT, SERVO_BAUD, SERVO_TYPE)
    except Exception as e:
        print(f"[Error] 打开舵机串口失败：{e}")
        return

    try:
        ad = ArduinoController(ARDUINO_PORT, ARDUINO_BAUD)
    except Exception as e:
        print(f"[Error] 打开 Arduino 串口失败：{e}")
        sc.close()
        return

    print("输入格式：<电机1位置> <电机2位置> <表情字符>，如 “1000 2000 c”")
    print("输入 exit/Q/q 可退出。")

    try:
        while True:
            raw = input(">> ").strip()
            if raw.lower() in ('exit', 'q', 'quit'):
                print("退出程序。")
                break

            parts = raw.split()
            if len(parts) != 3:
                print("[输入错误] 请按格式输入：<整数> <整数> <单字符>")
                continue

            try:
                m1 = int(parts[0])
                m2 = int(parts[1])
                expr = parts[2]
                if len(expr) != 1:
                    raise ValueError("表情必须为单个字符")
            except ValueError as ve:
                print(f"[输入错误] {ve}")
                continue

            # 调用封装函数
            try:
                control_targets(m1, m2, expr, sc, ad)
            except Exception as ex:
                print(f"[运行异常] {ex}")

    except KeyboardInterrupt:
        print("\n用户中断，程序结束。")
    finally:
        sc.close()
        ad.close()


if __name__ == '__main__':
    main()
