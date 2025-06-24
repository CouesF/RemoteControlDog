#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
arduino.py
用于驱动 Arduino 屏幕，发送表情字符到 Arduino
"""

import serial

class ArduinoController:
    def __init__(self,
                 port: str = '/dev/ttyCH341USB0',
                 baudrate: int = 115200,
                 timeout: float = 1.0):
        """
        初始化串口，连接到 Arduino。
        :param port: 串口设备，例如 'COM4'
        :param baudrate: 波特率，例如 115200
        :param timeout: 超时时间（秒）
        """
        try:
            self.ser = serial.Serial(port, baudrate, timeout=timeout)
        except serial.SerialException as e:
            raise RuntimeError(f"无法打开 Arduino 串口 {port}: {e}")

    def set_expression(self, expr: str):
        """
        发送单字符到 Arduino，根据 Arduino 程序切换屏幕表情。
        :param expr: 单个字符，例如 'c', 'l', 'r' 等
        """
        if not isinstance(expr, str) or len(expr) != 1:
            raise ValueError("表情字符必须为单个字符")
        self.ser.write(expr.encode('utf-8'))
        self.ser.flush()

    def close(self):
        """关闭串口连接"""
        if self.ser and self.ser.is_open:
            self.ser.close()


if __name__ == '__main__':
    # 简单测试
    ad = ArduinoController()
    for ch in ['c', 'l', 'r']:
        print(f"发送表情 {ch}")
        ad.set_expression(ch)
        input("按任意键继续")
    ad.close()
