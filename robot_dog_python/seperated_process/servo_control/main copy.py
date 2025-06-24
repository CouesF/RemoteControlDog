#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main.py
交互菜单：Ping / 改 ID / 读写位置 / 清零
"""

import sys
from servo_controller import ServoController

# ------------------- 修改这里 ------------------- #
DEFAULT_PORT = '/dev/ttyACM0'   # ↙ 根据实际情况改
DEFAULT_BAUD = 1_000_000
SERVO_TYPE   = 'STS'                    # 'STS' 或 'SCSCL'
# ------------------------------------------------ #

def choose_port() -> str:
    ports = ServoController.list_ports()
    if not ports:
        print("⚠️  没发现任何串口，请检查连接。")
        sys.exit(1)
    print("可用串口：")
    for i, p in enumerate(ports):
        print(f"  {i}: {p}")
    idx = input(f"选择编号 (默认 {DEFAULT_PORT}): ").strip()
    if idx == '':
        return DEFAULT_PORT
    try:
        return ports[int(idx)]
    except (ValueError, IndexError):
        print("输入无效"); sys.exit(1)

def menu():
    print("\n=== STServo 控制台 ===")
    print("1  Ping 舵机")
    print("2  修改舵机 ID")
    print("3  读取当前位置")
    print("4  写入目标位置")
    print("5  清零 (Offset=0)")
    print("6  切步进模式")
    print("7  相对旋转 ±°")      # ← 新
    print("8  切绝对位置模式 (mode 0)")
    print("q  退出")
    print("======================")

def main():
    port = choose_port()
    sc = ServoController(port, DEFAULT_BAUD, SERVO_TYPE)
    try:
        while True:
            menu()
            cmd = input("选项: ").strip().lower()
            if cmd == 'q':
                break
            elif cmd == '1':
                sid = int(input("舵机 ID: "))
                print("✓ Online" if sc.ping(sid) else "✗ 无响应")
            elif cmd == '2':
                old = int(input("旧 ID: "))
                new = int(input("新 ID: "))
                sc.change_id(old, new)
                print("ID 修改成功，断电后生效。")
            elif cmd == '3':
                sid = int(input("舵机 ID: "))
                print("当前位置 =", sc.read_position(sid))
            elif cmd == '4':
                sid = int(input("舵机 ID: "))
                pos = int(input("目标位置 (0-4095): "))
                sc.write_position(sid, pos)
                print("已发送。")
            elif cmd == '5':
                sid = int(input("舵机 ID: "))
                sc.clear_zero(sid)
            elif cmd == '6':
                sid = int(input("舵机 ID: "))
                sc.enable_step_mode(sid)

            elif cmd == '7':
                sid  = int(input("舵机 ID: "))
                deg  = float(input("输入角度(正=顺时针, 负=逆时针): "))
                vel  = float(input("速度 °/s (回车默认180): ") or 180)
                sc.rotate_deg(sid, deg, vel)
                print("已发送相对旋转指令")
            elif cmd == '8':
                sid = int(input("舵机 ID: "))
                sc.enable_absolute_mode(sid)
            else:
                print("无效选项")
    finally:
        sc.close()
        print("串口已关闭，再见！")

if __name__ == '__main__':
    main()
