#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dog_head_server.py (Updated)

This script acts as a server to control the robot dog's head.
It listens for commands over a network socket and controls the
servo motors and Arduino screen accordingly. This script should be
run on the computer directly connected to the hardware.

Changelog:
- Reworked shake function for a more fluid, continuous side-to-side sweep.
- Reworked nod and shake functions for a more natural, single-motion action.
- Utilized speed and acceleration parameters to create smoother movements.
- Fixed Arduino expression handling by removing l/r character swap.
- Corrected motor assignments: nod is Motor 2, shake is Motor 1.
- Increased amplitude of nod and shake motions for more expressive movement.
"""

import sys
import os
import time
import socket
import threading
import serial
from typing import Tuple

# --- SDK Import ---
try:
    from STservo_sdk import (PortHandler, sts, scscl, COMM_SUCCESS,
                             STS_GOAL_POSITION_L, STS_PRESENT_POSITION_L,
                             SCSCL_GOAL_POSITION_L, SCSCL_PRESENT_POSITION_L)
except ImportError:
    print("Error: The 'STservo_sdk' library is not found.")
    print("Please ensure it is installed and accessible in your PYTHONPATH.")
    sys.exit(1)

# --- Configuration Section ---

# Network Configuration
HOST = '0.0.0.0'  # Listen on all available network interfaces
PORT = 65432      # Port to listen on

# Hardware Configuration - **Please verify these ports are correct for your system**
SERVO_PORT = '/dev/ttyACM0'
SERVO_BAUD = 1_000_000
SERVO_TYPE = 'STS'
ARDUINO_PORT = '/dev/ttyCH341USB0' # Reverted to port from original file
ARDUINO_BAUD = 115200

# Motor Physical Limits & Conversion
DEG_TO_STEP = 4096 / 360  # ~11.377 steps per degree

# Motor 1 (Horizontal Shake) - Wider, symmetrical range
MIN_ALLOWED_STEP_M1 = 1600
MAX_ALLOWED_STEP_M1 = 2496
MIN_ALLOWED_DEG_M1 = (MIN_ALLOWED_STEP_M1 - 2048) / DEG_TO_STEP # ~-40 deg
MAX_ALLOWED_DEG_M1 = (MAX_ALLOWED_STEP_M1 - 2048) / DEG_TO_STEP # ~+40 deg

# Motor 2 (Vertical Nod) - Asymmetrical range
MIN_ALLOWED_STEP_M2 = 1660
MAX_ALLOWED_STEP_M2 = 2205
MIN_ALLOWED_DEG_M2 = (MIN_ALLOWED_STEP_M2 - 2048) / DEG_TO_STEP # ~-34 deg
MAX_ALLOWED_DEG_M2 = (MAX_ALLOWED_STEP_M2 - 2048) / DEG_TO_STEP # ~+13 deg


# --- Hardware Controller Classes ---

class ArduinoController:
    """Drives an Arduino screen by sending expression characters."""
    def __init__(self, port: str, baudrate: int, timeout: float = 1.0):
        try:
            self.ser = serial.Serial(port, baudrate, timeout=timeout)
            print(f"Arduino controller initialized on {port}.")
        except serial.SerialException as e:
            self.ser = None
            print(f"Warning: Failed to open Arduino port {port}: {e}. Screen control will be disabled.")

    def set_expression(self, expr: str):
        if not self.ser:
            return
        if not isinstance(expr, str) or len(expr) != 1:
            print(f"Warning: Invalid expression '{expr}'. Must be a single character.")
            return
        self.ser.write(expr.encode('utf-8'))
        self.ser.flush()

    def close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()


class ServoController:
    """A wrapper for the STservo_sdk to control STS and SCSCL series servos."""
    def __init__(self, port: str, baudrate: int, servo_type: str = 'STS'):
        self.port = port
        self.baud = baudrate
        self.ph = PortHandler(self.port)
        self.dev = None
        self._write_pos = None
        self._read_pos = None

        if servo_type.upper() == 'STS':
            self.dev = sts(self.ph)
            self._write_pos = self.dev.WritePosEx
            self._read_pos = self.dev.ReadPos
        elif servo_type.upper() == 'SCSCL':
            self.dev = scscl(self.ph)
            self._write_pos = self.dev.WritePos
            self._read_pos = self.dev.ReadPos
        else:
            raise ValueError("servo_type must be 'STS' or 'SCSCL'.")

        if not self.ph.openPort():
            raise IOError(f"Failed to open servo serial port {self.port}.")
        if not self.ph.setBaudRate(self.baud):
            self.ph.closePort()
            raise IOError(f"Failed to set baud rate {self.baud}.")
        print(f"Servo controller initialized on {self.port}.")

    def write_position(self, sid: int, pos_deg: float, speed: int = 2400, acc: int = 50):
        """
        Writes the target position in degrees, clamping to physical limits.
        Allows for specifying speed and acceleration.
        """
        if sid == 1:
            pos_deg = max(MIN_ALLOWED_DEG_M1, min(pos_deg, MAX_ALLOWED_DEG_M1))
            min_step, max_step = MIN_ALLOWED_STEP_M1, MAX_ALLOWED_STEP_M1
        elif sid == 2:
            pos_deg = max(MIN_ALLOWED_DEG_M2, min(pos_deg, MAX_ALLOWED_DEG_M2))
            min_step, max_step = MIN_ALLOWED_STEP_M2, MAX_ALLOWED_STEP_M2
        else:
            raise ValueError("Invalid servo ID.")

        pos_step = int(pos_deg * DEG_TO_STEP) + 2048
        pos_step = max(min_step, min(pos_step, max_step))

        r, err = self._write_pos(sid, pos_step, speed, acc)
        if r != COMM_SUCCESS:
            print(f"Warning: Servo {sid} TX failed: {self.dev.getTxRxResult(r)}")
        if err:
            print(f"Warning: Servo {sid} RX error: {self.dev.getRxPacketError(err)}")
        return pos_deg

    def read_position_deg(self, sid: int) -> float:
        """Reads the current position of the servo in degrees."""
        pos_step, r, err = self._read_pos(sid)
        if r != COMM_SUCCESS:
            raise RuntimeError(f"Servo {sid} read failed: {self.dev.getTxRxResult(r)}")
        if err:
            raise RuntimeError(f"Servo {sid} read error: {self.dev.getRxPacketError(err)}")
        return (pos_step - 2048) / DEG_TO_STEP

    def close(self):
        self.ph.closePort()

# --- Motion Functions ---

def nod_head(sc: ServoController):
    """
    Performs a more natural, single 'nod' motion (down and back up).
    This function controls MOTOR 2.
    """
    motor_id = 2
    amplitude = 20  # A significant but safe downward angle for the nod
    try:
        start_pos_deg = sc.read_position_deg(motor_id)
        print(f"Nodding with Motor {motor_id} from {start_pos_deg:.2f}°")
        
        down_pos_deg = start_pos_deg - amplitude
        
        # 1. Move down quickly with high acceleration
        sc.write_position(motor_id, down_pos_deg, speed=2800, acc=80)
        time.sleep(0.4)
        
        # 2. Return to start position more gently
        sc.write_position(motor_id, start_pos_deg, speed=2000, acc=40)
        time.sleep(0.4) # Wait for movement to complete

        return f"Nod (Motor {motor_id}) complete."
    except Exception as e:
        return f"Error during nod: {e}"

def shake_head(sc: ServoController):
    """
    Performs a more fluid, single 'shake' motion.
    The head moves to one side, sweeps quickly to the other, then returns to center.
    This function now controls MOTOR 1.
    """
    motor_id = 1
    amplitude = 30 # A wide amplitude for a clear shake
    try:
        start_pos_deg = sc.read_position_deg(motor_id)
        print(f"Shaking with Motor {motor_id} from {start_pos_deg:.2f}°")

        # Define the two extremes of the shake
        side1_pos_deg = start_pos_deg + amplitude
        side2_pos_deg = start_pos_deg - amplitude

        # 1. Move to the first side to begin the shake
        sc.write_position(motor_id, side1_pos_deg, speed=3000, acc=80)
        time.sleep(0.3)
        
        # 2. Sweep across to the other side without a noticeable pause.
        # This is the core 'shake' motion, using high speed and acceleration.
        sc.write_position(motor_id, side2_pos_deg, speed=4000, acc=120)
        time.sleep(0.4) # Allow time for the full sweep to complete
        
        # 3. Return to the center smoothly
        sc.write_position(motor_id, start_pos_deg, speed=2500, acc=50)
        time.sleep(0.4) # Wait for the movement to complete

        return f"Shake (Motor {motor_id}) complete."
    except Exception as e:
        return f"Error during shake: {e}"


def handle_client(conn, addr, sc: ServoController, ad: ArduinoController):
    """Handles an incoming client connection."""
    print(f"Connected by {addr}")
    with conn:
        try:
            data = conn.recv(1024).decode('utf-8').strip().lower()
            if not data: return

            parts = data.split()
            command = parts[0]
            response = ""

            print(f"Received command: '{data}'")

            if command == 'move' and len(parts) == 4:
                m1_deg, m2_deg, expr = float(parts[1]), float(parts[2]), parts[3]
                actual_m1 = sc.write_position(1, m1_deg)
                actual_m2 = sc.write_position(2, m2_deg)
                ad.set_expression(expr)
                response = f"Move complete. M1 set to {actual_m1:.2f}°, M2 to {actual_m2:.2f}°."
            elif command == 'nod':
                response = nod_head(sc)
            elif command == 'shake':
                response = shake_head(sc)
            else:
                response = "Error: Invalid command. Use 'move <m1> <m2> <expr>', 'nod', or 'shake'."

            print(f"Response: {response}")
            conn.sendall(response.encode('utf-8'))
        except Exception as e:
            print(f"Error handling client {addr}: {e}")
            conn.sendall(f"Server error: {e}".encode('utf-8'))


def main():
    """Initializes controllers and starts the server."""
    try:
        sc = ServoController(SERVO_PORT, SERVO_BAUD, SERVO_TYPE)
    except Exception as e:
        print(f"[Critical Error] Failed to initialize ServoController: {e}")
        return

    ad = ArduinoController(ARDUINO_PORT, ARDUINO_BAUD)
    
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen()
        print(f"--- Robot Head Server (Updated) ---")
        print(f"Listening for commands on {HOST}:{PORT}")
        print(f"Motor 1 (Shake) Limits: [{MIN_ALLOWED_DEG_M1:.1f}°, {MAX_ALLOWED_DEG_M1:.1f}°]")
        print(f"Motor 2 (Nod)   Limits: [{MIN_ALLOWED_DEG_M2:.1f}°, {MAX_ALLOWED_DEG_M2:.1f}°]")


        try:
            while True:
                conn, addr = s.accept()
                client_thread = threading.Thread(target=handle_client, args=(conn, addr, sc, ad))
                client_thread.start()
        except KeyboardInterrupt:
            print("\nServer shutting down.")
        finally:
            sc.close()
            ad.close()
            print("Controllers closed.")

if __name__ == '__main__':
    main()
