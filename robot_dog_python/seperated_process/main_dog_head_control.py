#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dog_head_server_dds.py

This script acts as a server to control the robot dog's head.
It subscribes to DDS commands and controls the servo motors and
Arduino screen accordingly. This script should be run on the computer
directly connected to the hardware.

Changelog:
- Fixed DDS serialization error by using 'int' for the action field.
- Updated to use individual pitch/yaw fields in HeadCommand DDS message.
- Replaced socket communication with DDS subscriber model.
"""

import sys
import os
import time
import serial
import math
from typing import List

# --- SDK & DDS Imports ---
current_script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_script_dir)
communication_dir_path = os.path.join(parent_dir, 'communication')
sys.path.append(communication_dir_path)
try:
    from dds_data_structure import HeadCommand, HeadAction
    from unitree_sdk2py.core.channel import ChannelSubscriber, ChannelFactoryInitialize
    from STservo_sdk import (PortHandler, sts, scscl, COMM_SUCCESS)
except ImportError as e:
    print(f"Error: A required library is not found. {e}")
    print("Please ensure unitree_sdk2py, STservo_sdk, and dds_data_structure.py are accessible.")
    sys.exit(1)

# --- Configuration Section ---

DDS_NETWORK_INTERFACE = "enP8p1s0"
HEAD_COMMAND_TOPIC = "HeadCommand"
SERVO_PORT = '/dev/ttyACM0'
SERVO_BAUD = 1_000_000
SERVO_TYPE = 'STS'
ARDUINO_PORT = '/dev/ttyCH341USB0'
ARDUINO_BAUD = 115200
DEG_TO_STEP = 4096 / 360
MIN_ALLOWED_DEG_M1, MAX_ALLOWED_DEG_M1 = -40.0, 40.0
MIN_ALLOWED_STEP_M1, MAX_ALLOWED_STEP_M1 = 1600, 2496
MIN_ALLOWED_DEG_M2, MAX_ALLOWED_DEG_M2 = -34.0, 13.0
MIN_ALLOWED_STEP_M2, MAX_ALLOWED_STEP_M2 = 1660, 2205

# --- Hardware Controller Classes ---

class ArduinoController:
    def __init__(self, port: str, baudrate: int, timeout: float = 1.0):
        try:
            self.ser = serial.Serial(port, baudrate, timeout=timeout)
            print(f"Arduino controller initialized on {port}.")
        except serial.SerialException as e:
            self.ser = None
            print(f"Warning: Failed to open Arduino port {port}: {e}. Screen control disabled.")

    def set_expression(self, expr: str):
        if not self.ser or not isinstance(expr, str) or len(expr) != 1: return
        self.ser.write(expr.encode('utf-8'))
        self.ser.flush()

    def close(self):
        if self.ser and self.ser.is_open: self.ser.close()

class ServoController:
    def __init__(self, port: str, baudrate: int, servo_type: str = 'STS'):
        self.port, self.baud = port, baudrate
        self.ph = PortHandler(self.port)
        if servo_type.upper() == 'STS': self.dev, self._write_pos, self._read_pos = sts(self.ph), sts(self.ph).WritePosEx, sts(self.ph).ReadPos
        elif servo_type.upper() == 'SCSCL': self.dev, self._write_pos, self._read_pos = scscl(self.ph), scscl(self.ph).WritePos, scscl(self.ph).ReadPos
        else: raise ValueError("servo_type must be 'STS' or 'SCSCL'.")
        if not self.ph.openPort() or not self.ph.setBaudRate(self.baud): raise IOError(f"Failed to init servo hardware on {port}.")
        print(f"Servo controller initialized on {self.port}.")

    def write_position(self, sid: int, pos_deg: float, speed: int = 2400, acc: int = 50):
        if sid == 1: pos_deg, min_step, max_step = max(MIN_ALLOWED_DEG_M1, min(pos_deg, MAX_ALLOWED_DEG_M1)), MIN_ALLOWED_STEP_M1, MAX_ALLOWED_STEP_M1
        elif sid == 2: pos_deg, min_step, max_step = max(MIN_ALLOWED_DEG_M2, min(pos_deg, MAX_ALLOWED_DEG_M2)), MIN_ALLOWED_STEP_M2, MAX_ALLOWED_STEP_M2
        else: raise ValueError("Invalid servo ID.")
        pos_step = max(min_step, min(int(pos_deg * DEG_TO_STEP) + 2048, max_step))
        self._write_pos(sid, pos_step, speed, acc)
        return pos_deg

    def read_position_deg(self, sid: int) -> float:
        pos_step, r, err = self._read_pos(sid)
        if r != COMM_SUCCESS or err != 0: raise RuntimeError(f"Servo {sid} read failed.")
        return (pos_step - 2048) / DEG_TO_STEP

    def close(self): self.ph.closePort()

# --- Motion Functions ---

def nod_head(sc: ServoController):
    motor_id, amplitude = 2, 20
    try:
        start_pos_deg = sc.read_position_deg(motor_id)
        down_pos_deg = start_pos_deg - amplitude
        sc.write_position(motor_id, down_pos_deg, speed=2800, acc=80)
        time.sleep(0.4)
        sc.write_position(motor_id, start_pos_deg, speed=2000, acc=40)
        time.sleep(0.4)
        print("Nod complete.")
    except Exception as e: print(f"Error during nod: {e}")

def shake_head(sc: ServoController):
    motor_id, amplitude = 1, 30
    try:
        start_pos_deg = sc.read_position_deg(motor_id)
        side1_pos_deg, side2_pos_deg = start_pos_deg + amplitude, start_pos_deg - amplitude
        sc.write_position(motor_id, side1_pos_deg, speed=3000, acc=80)
        time.sleep(0.3)
        sc.write_position(motor_id, side2_pos_deg, speed=4000, acc=120)
        time.sleep(0.4)
        sc.write_position(motor_id, start_pos_deg, speed=2500, acc=50)
        time.sleep(0.4)
        print("Shake complete.")
    except Exception as e: print(f"Error during shake: {e}")

# --- Main DDS Subscriber Logic ---

def main():
    sc, ad, sub = None, None, None
    try:
        sc = ServoController(SERVO_PORT, SERVO_BAUD, SERVO_TYPE)
        ad = ArduinoController(ARDUINO_PORT, ARDUINO_BAUD)
        print(f"Initializing DDS on network interface: {DDS_NETWORK_INTERFACE}")
        ChannelFactoryInitialize(networkInterface=DDS_NETWORK_INTERFACE)
        sub = ChannelSubscriber(HEAD_COMMAND_TOPIC, HeadCommand)
        sub.Init()
        
        print(f"--- Robot Head Server (DDS) ---")
        print(f"Listening for commands on DDS topic: '{HEAD_COMMAND_TOPIC}'")
        print("Press Ctrl+C to stop.")

        while True:
            msg = sub.Read(100)
            if msg:
                # Use the integer value of the enum for comparison
                action_name = HeadAction(msg.action).name if msg.action in HeadAction._value2member_map_ else "UNKNOWN"
                print(f"Received command: {action_name}, Yaw: {msg.yaw_deg:.1f}°, Pitch: {msg.pitch_deg:.1f}°, Expr: '{msg.expression_char}'")

                if msg.action == HeadAction.MOVE_DIRECT.value:
                    sc.write_position(1, msg.yaw_deg)
                    sc.write_position(2, msg.pitch_deg)
                    ad.set_expression(msg.expression_char)
                elif msg.action == HeadAction.NOD.value:
                    nod_head(sc)
                elif msg.action == HeadAction.SHAKE.value:
                    shake_head(sc)
            
    except KeyboardInterrupt:
        print("\nServer shutting down.")
    except Exception as e:
        import traceback
        print(f"\nAn unexpected error occurred: {e}")
        traceback.print_exc()
    finally:
        # if sub: sub.Close()
        # if sc: sc.close()
        # if ad: ad.close()
        print("Controllers and DDS closed.")

if __name__ == '__main__':
    main()
