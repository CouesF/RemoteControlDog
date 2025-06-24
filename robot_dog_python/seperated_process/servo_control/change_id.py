#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""change_id_once.py  ——  单次改 ID 小脚本"""

from servo_controller import ServoController   # 复用刚才封装
import sys, time

PORT      = '/dev/ttyACM0'   # ⇦ 改成实际串口
BAUD      = 1_000_000
OLD_ID    = 1
NEW_ID    = 2

ctl = ServoController(PORT, BAUD, 'STS')

print(f"步骤 0：Ping 旧 ID={OLD_ID}")
print("✓ Online" if ctl.ping(OLD_ID) else "✗ 无响应，停止")
if not ctl.ping(OLD_ID):
    ctl.close(); sys.exit(1)

print("步骤 1~5：执行改 ID 流程")
ctl.change_id(OLD_ID, NEW_ID)
ctl.close()

print("\n>>> 现在断电重启舵机，再运行以下命令验证：")
print(f"    python -c \"from servo_controller import ServoController as C; "
      f"c=C('{PORT}',{BAUD},'STS'); print(c.ping({NEW_ID})); c.close()\"")
