#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
servo_controller.py
基于官方 STservo_sdk 的简单封装：支持 Ping、改 ID、读/写位置、清零。
"""

import glob
from typing import Tuple, Optional

from STservo_sdk import (PortHandler, sts, scscl,  # 驱动类
                         COMM_SUCCESS,              # 返回码
                         STS_OFS_L, STS_GOAL_POSITION_L,
                         STS_PRESENT_POSITION_L,
                         SCSCL_GOAL_POSITION_L, SCSCL_PRESENT_POSITION_L)

DEG_TO_STEP = 4096 / 360        # ≈ 11.377… 步/度

class ServoController:

    def enable_absolute_mode(self, sid: int,
                             min_angle: int = 0,
                             max_angle: int = 4095):
        """
        把舵机切回 Mode-0（绝对位置伺服）。
        可顺便恢复最小/最大角限制。
        """
        LOCK, MODE, MIN, MAX = 0x37, 0x21, 0x09, 0x0B

        # 1) 解锁
        self.dev.write1ByteTxOnly(sid, LOCK, 0)

        # 2) 恢复角度限制
        self.dev.write2ByteTxOnly(sid, MIN, min_angle)
        self.dev.write2ByteTxOnly(sid, MAX, max_angle)

        # 3) 设置模式 = 0
        self.dev.write1ByteTxOnly(sid, MODE, 0)

        # 4) ACTION → EEPROM
        self.dev.action(sid)

        # 5) 锁回
        self.dev.write1ByteTxOnly(sid, LOCK, 1)

        print("✔ 已切换回绝对位置模式 (mode 0)")
    
    ...
    # ========== ① 把舵机切到 mode 3 ==========
    def enable_step_mode(self, sid: int):
        """
        把 0x21 运行模式设为 3（步进伺服），并把最小/最大角限制清零。
        会自动解锁/上锁 EEPROM。
        """
        LOCK_ADDR = 0x37
        MODE_ADDR = 0x21
        MIN_ADDR  = 0x09
        MAX_ADDR  = 0x0B

        # 解锁
        self.dev.write1ByteTxOnly(sid, LOCK_ADDR, 0)

        # 设最小/最大角 = 0
        self.dev.write2ByteTxOnly(sid, MIN_ADDR, 0)
        self.dev.write2ByteTxOnly(sid, MAX_ADDR, 0)

        # 写运行模式 = 3
        self.dev.write1ByteTxOnly(sid, MODE_ADDR, 3)

        # ACTION 落 EEPROM
        self.dev.action(sid)

        # 上锁
        self.dev.write1ByteTxOnly(sid, LOCK_ADDR, 1)

        print("✔ 已切换到步进伺服模式 (mode 3)")

    # ========== ② 角度 → 带符号“步” ==========
    @staticmethod
    def deg_to_signed_steps(deg: float) -> int:
        steps = int(round(deg * DEG_TO_STEP))
        if steps == 0:
            raise ValueError("角度太小，计算步数为 0")
        if steps >  32766 or steps < -32766:
            raise ValueError("步数超出 -32766~+32766 范围")
        return steps

    # ========== ③ 相对旋转 ==========
    def rotate_deg(self, sid: int, deg: float,
                   speed_deg_s: float = 180, acc_raw: int = 50):
        """
        输入 ±°，舵机会按给定方向转对应角度然后停止。
        默认速度 = 180 °/s，可自行调。
        """
        steps = self.deg_to_signed_steps(deg)
        speed_steps = self.deg_to_signed_steps(speed_deg_s)

        # WritePosEx(acc, pos_l, pos_h, time_l, time_h, speed_l, speed_h)
        pos_u16   = steps & 0xFFFF
        speed_u16 = speed_steps & 0xFFFF
        r, err = self.dev.WritePosEx(sid, pos_u16, speed_u16, acc_raw)
        if r != COMM_SUCCESS:
            raise RuntimeError(self.dev.getTxRxResult(r))
        if err:
            raise RuntimeError(self.dev.getRxPacketError(err))



    # ---------- 内部工具 ---------- #
    """
    支持两类舵机：
        servo_type = 'STS'   ➟ STS 系列（零点寄存器 OFS_L/H）
        servo_type = 'SCSCL' ➟ SCSCL 系列
    """
    def __init__(self,
                 port: str,
                 baudrate: int = 1_000_000,
                 servo_type: str = 'STS'):
        self.port = port
        self.baud = baudrate
        self.ph   = PortHandler(self.port)
        # 选择协议类
        if servo_type.upper() == 'STS':
            self.dev = sts(self.ph)
            self.ADDR_GOAL  = STS_GOAL_POSITION_L
            self.ADDR_POS   = STS_PRESENT_POSITION_L
            self.ADDR_ZERO  = STS_OFS_L          # 零点寄存器
            self._write_pos = self.dev.WritePosEx
            self._read_pos  = self.dev.ReadPos
        elif servo_type.upper() == 'SCSCL':
            self.dev = scscl(self.ph)
            self.ADDR_GOAL  = SCSCL_GOAL_POSITION_L
            self.ADDR_POS   = SCSCL_PRESENT_POSITION_L
            self.ADDR_ZERO  = None               # SCSCL 没有 OFS
            self._write_pos = self.dev.WritePos
            self._read_pos  = self.dev.ReadPos
        else:
            raise ValueError("servo_type 只能是 'STS' 或 'SCSCL'")

        # 开串口
        if not self.ph.openPort():
            raise IOError(f"❌ 无法打开串口 {self.port}")
        if not self.ph.setBaudRate(self.baud):
            self.ph.closePort()
            raise IOError(f"❌ 设置波特率 {self.baud} 失败")

    # ---------- 基础功能 ---------- #
    def ping(self, sid: int) -> bool:
        _, r, _ = self.dev.ping(sid)
        return r == COMM_SUCCESS

    def change_id(self, old: int, new: int) -> None:
        """
        STS 机型改 ID (0x05) — 按官方流程:
        ① 解锁(0x37 ← 0) → ② REG_WRITE 新 ID
        ③ ACTION 落 EEPROM → ④ 读回确认
        ⑤ 锁回(0x37 ← 1)
        """
        ID_ADDR   = 0x05          # ← 你表里明确写的
        LOCK_ADDR = 0x37          # ← SRAM区锁标志

        # 1. 解锁
        res, err = self.dev.write1ByteTxRx(old, LOCK_ADDR, 0)
        if res != COMM_SUCCESS:
            raise RuntimeError(self.dev.getTxRxResult(res))
        if err:
            raise RuntimeError(self.dev.getRxPacketError(err))

        # 2. REG_WRITE 把新 ID 写缓存
        res, err = self.dev.regWriteTxRx(old, ID_ADDR, 1, [new])
        if res != COMM_SUCCESS:
            raise RuntimeError(self.dev.getTxRxResult(res))
        if err:
            raise RuntimeError(self.dev.getRxPacketError(err))

        # 3. ACTION 让缓存刷新进 EEPROM
        res = self.dev.action(old)
        if res != COMM_SUCCESS:
            raise RuntimeError(self.dev.getTxRxResult(res))

        # ※ EEPROM 写入需要一小段时间，这里给 50 ms 缓冲
        import time; time.sleep(0.05)

        # 4. 读回确认
        read_back, res, err = self.dev.read1ByteTxRx(old, ID_ADDR)
        if res != COMM_SUCCESS:
            raise RuntimeError(self.dev.getTxRxResult(res))
        if err:
            raise RuntimeError(self.dev.getRxPacketError(err))
        if read_back != new:
            raise RuntimeError(f"EEPROM 未写成功，读回 ID = {read_back}")

        # 5. 锁回
        self.dev.write1ByteTxRx(new, LOCK_ADDR, 1)  # ⚠ 用新 ID

        print(f"✔ ID 已改为 {new}（已落 EEPROM）。请断电重上电后用新 ID Ping。")


    def read_position(self, sid: int) -> int:
        pos, r, err = self._read_pos(sid)
        if r != COMM_SUCCESS:
            raise RuntimeError(self.dev.getTxRxResult(r))
        if err:
            raise RuntimeError(self.dev.getRxPacketError(err))
        return pos

# servo_controller.py

    def write_position(self, sid: int,
                       pos: int, speed: int = 2400, acc: int = 50) -> None:
        """
        • pos >= 0 : 直接写绝对位置 0-4095
        • pos <  0 : 解释为“相对当前位置的偏移量”
        """
        # Define your minimum and maximum allowed positions
        MIN_ALLOWED_POS = 1600 # Example: set your desired minimum
        MAX_ALLOWED_POS = 2496 # Example: set your desired maximum

        if pos < 0:
            pos = self._calc_target(sid, pos)     # Turn into absolute target

        # Add the boundary check here
        if not (MIN_ALLOWED_POS <= pos <= MAX_ALLOWED_POS):
            raise ValueError(f"Target position {pos} is out of the allowed range "
                             f"[{MIN_ALLOWED_POS}, {MAX_ALLOWED_POS}].")

        r, err = self._write_pos(sid, pos, speed, acc)
        if r != COMM_SUCCESS:
            raise RuntimeError(self.dev.getTxRxResult(r))
        if err:
            raise RuntimeError(self.dev.getRxPacketError(err))


    def clear_zero(self, sid: int) -> None:
        if self.ADDR_ZERO is None:
            print("该型号无零点寄存器，跳过。")
            return
        r, err = self.dev.write2ByteTxRx(sid, self.ADDR_ZERO, 0)
        if r != COMM_SUCCESS:
            raise RuntimeError(self.dev.getTxRxResult(r))
        if err:
            raise RuntimeError(self.dev.getRxPacketError(err))

    def set_zero_at(self, sid: int, target_raw: int):
        """
        把当前物理位置的编码值设为 target_raw（0-4095）。
        会自动计算 offset 并写入 0x1F/0x20。
        """
        ID_ADDR   = 0x05
        LOCK_ADDR = 0x37
        OFS_ADDR  = 0x1F   # 位置校正低字节
        assert 0 <= target_raw <= 4095, "target_raw 必须在 0~4095"

        # ① 读取当前位置
        cur, res, err = self.dev.read2ByteTxRx(sid, 0x38)  # 0x38 = 当前位置
        if res != COMM_SUCCESS:
            raise RuntimeError(self.dev.getTxRxResult(res))
        if err:
            raise RuntimeError(self.dev.getRxPacketError(err))

        # ② 计算 offset = target - cur  (循环 4096)
        offset = (target_raw - cur) % 4096
        if offset > 2047:              # 映射到 -2047~+2047
            offset -= 4096             # 负数

        # ③ 将 offset 按 STS 格式(12bit，bit11为符号) 打包
        ofs_val = self.dev.sts_toscs(offset, 11)

        # ④ 解锁 EEPROM
        self.dev.write1ByteTxOnly(sid, LOCK_ADDR, 0)

        # ⑤ REG_WRITE offset → ACTION
        self.dev.regWriteTxOnly(sid, OFS_ADDR, 2,
                                [ofs_val & 0xFF, (ofs_val >> 8) & 0xFF])
        self.dev.action(sid)           # 写入 EEPROM
        time.sleep(0.05)

        # ⑥ 读回确认
        back, res, err = self.dev.read2ByteTxRx(sid, OFS_ADDR)
        if res != COMM_SUCCESS:
            raise RuntimeError(self.dev.getTxRxResult(res))
        if back != ofs_val:
            raise RuntimeError("写 Offset 失败，读回值不符")

        # ⑦ 锁回
        self.dev.write1ByteTxOnly(sid, LOCK_ADDR, 1)

        print(f"✔ Offset 写入 {offset}（十进制），"
              f"现在物理编码 {target_raw} 将呈现为 0 步")



    # ---------- 清理 ---------- #
    def close(self):
        self.ph.closePort()

    # ---------- 辅助 ----------- #
    @staticmethod
    def list_ports() -> list:
        """简易枚举串口（macOS / Linux）。"""
        return sorted(glob.glob('/dev/tty.usb*') +
                      glob.glob('/dev/ttyUSB*')   +
                      glob.glob('COM[0-9]*'))
