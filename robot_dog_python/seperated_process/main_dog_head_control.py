#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
robot_control.py
A single-file script to control servo motors and an Arduino screen.

This script combines the functionality of:
- servo_controller.py: For controlling STS/SCSCL servo motors.
- arduino.py: For sending expressions to an Arduino-driven screen.
- main.py: The main application logic to accept user input and control the hardware.
"""

import sys
import os
import time
import glob
import serial
from typing import Tuple, Optional

# Attempt to import the STservo_sdk. This is a required external library.
# sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "/servo_control")))
# try:
from STservo_sdk import (PortHandler, sts, scscl,
                             COMM_SUCCESS,
                             STS_OFS_L, STS_GOAL_POSITION_L,
                             STS_PRESENT_POSITION_L,
                             SCSCL_GOAL_POSITION_L, SCSCL_PRESENT_POSITION_L)
'''
except ImportError:
    print("Error: The 'STservo_sdk' library is not installed.")
    print("Please install it from the manufacturer to run this script.")
    sys.exit(1)
    '''

# --- Configuration Section ---
# Adjust these values based on your hardware setup
SERVO_PORT = '/dev/ttyACM0'
SERVO_BAUD = 1_000_000
SERVO_TYPE = 'STS'  # Can be 'STS' or 'SCSCL'
ARDUINO_PORT = '/dev/ttyCH341USB0'
ARDUINO_BAUD = 115200

# Motor position boundaries to prevent physical damage
# Bounds for Motor 1 (ID 1)
MIN_ALLOWED_POS_M1 = 1600
MAX_ALLOWED_POS_M1 = 2496

# Bounds for Motor 2 (ID 2)
MIN_ALLOWED_POS_M2 = 1660
MAX_ALLOWED_POS_M2 = 2205

# Conversion factor for STS servos
DEG_TO_STEP = 4096 / 360  # ~11.377 steps per degree

# -----------------------------------------------------------------------------
# Class: ArduinoController
# -----------------------------------------------------------------------------
class ArduinoController:
    """Drives an Arduino screen by sending expression characters."""

    def __init__(self,
                 port: str = '/dev/ttyCH341USB0',
                 baudrate: int = 115200,
                 timeout: float = 1.0):
        """
        Initializes the serial connection to the Arduino.
        :param port: The serial port device (e.g., 'COM4' or '/dev/ttyUSB0').
        :param baudrate: The communication baud rate.
        :param timeout: Read timeout in seconds.
        """
        try:
            self.ser = serial.Serial(port, baudrate, timeout=timeout)
        except serial.SerialException as e:
            raise RuntimeError(f"Failed to open Arduino serial port {port}: {e}")

    def set_expression(self, expr: str):
        """
        Sends a single character to the Arduino to change the screen expression.
        :param expr: A single character, e.g., 'c', 'l', 'r'.
        """
        if not isinstance(expr, str) or len(expr) != 1:
            raise ValueError("Expression must be a single character.")
        self.ser.write(expr.encode('utf-8'))
        self.ser.flush()

    def close(self):
        """Closes the serial connection."""
        if self.ser and self.ser.is_open:
            self.ser.close()

# -----------------------------------------------------------------------------
# Class: ServoController
# -----------------------------------------------------------------------------
class ServoController:
    """
    A wrapper for the STservo_sdk to control STS and SCSCL series servos.
    Supports Ping, ID change, position read/write, and mode switching.
    """

    def __init__(self,
                 port: str,
                 baudrate: int = 1_000_000,
                 servo_type: str = 'STS'):
        """
        Initializes the servo controller and opens the serial port.
        """
        self.port = port
        self.baud = baudrate
        self.ph = PortHandler(self.port)

        if servo_type.upper() == 'STS':
            self.dev = sts(self.ph)
            self.ADDR_GOAL = STS_GOAL_POSITION_L
            self.ADDR_POS = STS_PRESENT_POSITION_L
            self._write_pos = self.dev.WritePosEx
            self._read_pos = self.dev.ReadPos
        elif servo_type.upper() == 'SCSCL':
            self.dev = scscl(self.ph)
            self.ADDR_GOAL = SCSCL_GOAL_POSITION_L
            self.ADDR_POS = SCSCL_PRESENT_POSITION_L
            self._write_pos = self.dev.WritePos
            self._read_pos = self.dev.ReadPos
        else:
            raise ValueError("servo_type must be 'STS' or 'SCSCL'.")

        if not self.ph.openPort():
            raise IOError(f"Failed to open servo serial port {self.port}.")
        if not self.ph.setBaudRate(self.baud):
            self.ph.closePort()
            raise IOError(f"Failed to set baud rate {self.baud}.")

    def write_position(self, sid: int, pos: int, speed: int = 2400, acc: int = 50):
        """
        Writes the target position to the servo.
        Position is absolute (0-4095).
        """
        r, err = self._write_pos(sid, pos, speed, acc)
        if r != COMM_SUCCESS:
            raise RuntimeError(self.dev.getTxRxResult(r))
        if err:
            raise RuntimeError(self.dev.getRxPacketError(err))

    def read_position(self, sid: int) -> int:
        """Reads the current position of the servo."""
        pos, r, err = self._read_pos(sid)
        if r != COMM_SUCCESS:
            raise RuntimeError(self.dev.getTxRxResult(r))
        if err:
            raise RuntimeError(self.dev.getRxPacketError(err))
        return pos

    def close(self):
        """Closes the port."""
        self.ph.closePort()

# -----------------------------------------------------------------------------
# Main Application Logic
# -----------------------------------------------------------------------------
def control_targets(m1: int, m2: int, expr: str,
                    sc: ServoController, ad: ArduinoController):
    """
    Core control function:
      - Sets motor 1 to position m1 and motor 2 to position m2.
      - Sends an expression character to the Arduino.
    :param m1: Target position for motor 1.
    :param m2: Target position for motor 2.
    :param expr: Single character expression ('c', 'l', 'r', etc.).
    :param sc: Initialized ServoController instance.
    :param ad: Initialized ArduinoController instance.
    """
    # Check bounds for Motor 1
    if not (MIN_ALLOWED_POS_M1 <= m1 <= MAX_ALLOWED_POS_M1):
        raise ValueError(f"Motor 1 target {m1} is out of allowed range "
                         f"[{MIN_ALLOWED_POS_M1}, {MAX_ALLOWED_POS_M1}].")

    # Check bounds for Motor 2
    if not (MIN_ALLOWED_POS_M2 <= m2 <= MAX_ALLOWED_POS_M2):
        raise ValueError(f"Motor 2 target {m2} is out of allowed range "
                         f"[{MIN_ALLOWED_POS_M2}, {MAX_ALLOWED_POS_M2}].")

    # Write target positions to servos
    sc.write_position(1, m1)
    sc.write_position(2, m2)
    print(f"✅ Motors -> ID 1: {m1}, ID 2: {m2}")

    # Send expression to Arduino
    ad.set_expression(expr)
    print(f"✅ Screen -> Expression: '{expr}'")


def main():
    """
    Initializes controllers and runs the main user input loop.
    """
    # Initialize controllers
    try:
        sc = ServoController(SERVO_PORT, SERVO_BAUD, SERVO_TYPE)
    except Exception as e:
        print(f"[Error] Failed to initialize ServoController: {e}")
        return

    try:
        ad = ArduinoController(ARDUINO_PORT, ARDUINO_BAUD)
    except Exception as e:
        print(f"[Error] Failed to initialize ArduinoController: {e}")
        sc.close()
        return

    print("--- Robot Control Interface ---")
    print("Enter commands in the format: <motor1_pos> <motor2_pos> <expression>")
    print("Example: '2048 2048 c'")
    print("Type 'exit' or 'q' to quit.")

    try:
        while True:
            raw_input = input(">> ").strip()
            if raw_input.lower() in ('exit', 'q', 'quit'):
                print("Exiting program.")
                break

            parts = raw_input.split()
            if len(parts) != 3:
                print("[Input Error] Please use the format: <int> <int> <char>")
                continue

            try:
                m1 = int(parts[0])
                m2 = int(parts[1])
                expr = parts[2]
                if len(expr) != 1:
                    raise ValueError("The expression must be a single character.")
            except ValueError as ve:
                print(f"[Input Error] {ve}")
                continue

            # Call the core control function
            try:
                control_targets(m1, m2, expr, sc, ad)
            except Exception as ex:
                print(f"[Runtime Error] {ex}")

    except KeyboardInterrupt:
        print("\nUser interrupted. Shutting down.")
    finally:
        # Ensure resources are released
        sc.close()
        ad.close()
        print("Controllers closed.")


if __name__ == '__main__':
    main()