#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dog_head_client_dds.py

A command-line client to send control requests to the head control server via DDS.
It publishes 'HeadCommand' messages.

Changelog:
- Fixed DDS serialization error by using 'int' for the action field.
- Updated to use individual pitch/yaw fields in HeadCommand DDS message.
"""

import sys
import os
import time
import math

# --- DDS Imports ---
current_script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_script_dir)
communication_dir_path = os.path.join(parent_dir, 'communication')
sys.path.append(communication_dir_path)
try:
    from dds_data_structure import HeadCommand, HeadAction
    from unitree_sdk2py.core.channel import ChannelPublisher, ChannelFactoryInitialize
except ImportError as e:
    print(f"Error: A required library is not found. {e}")
    print("Please ensure unitree_sdk2py and dds_data_structure.py are accessible.")
    sys.exit(1)


# --- Configuration ---
DDS_NETWORK_INTERFACE = "enP8p1s0"
HEAD_COMMAND_TOPIC = "HeadCommand"


def print_help():
    """Prints the command instructions."""
    print("\n--- Robot Control Client (DDS) ---")
    print("Available commands:")
    print("  move <yaw_deg> <pitch_deg> <expr>")
    print("    - Sets motor positions in degrees and screen expression.")
    print("    - Yaw controls Motor 1 (side-to-side).")
    print("    - Pitch controls Motor 2 (up-down).")
    print("    - Example: 'move 0 -10 c' -> Yaw to 0°, Pitch to -10°, screen to 'center'.")
    print("\n  nod")
    print("    - Sends a command to make the head nod.")
    print("\n  shake")
    print("    - Sends a command to make the head shake.")
    print("\n  help")
    print("    - Shows this help message.")
    print("\n  exit or quit")
    print("    - Exits the client program.")
    print("------------------------------------")

def main():
    """Main user input loop for the DDS client."""
    pub = None
    try:
        print(f"Initializing DDS on network interface: {DDS_NETWORK_INTERFACE}")
        ChannelFactoryInitialize(networkInterface=DDS_NETWORK_INTERFACE)
        pub = ChannelPublisher(HEAD_COMMAND_TOPIC, HeadCommand)
        pub.Init()
    except Exception as e:
        print(f"FATAL: DDS initialization failed: {e}")
        return

    print_help()
    while True:
        try:
            raw_input = input(">> ").strip().lower()
            if not raw_input: continue

            if raw_input in ('exit', 'q', 'quit'):
                print("Exiting client.")
                break
            
            if raw_input == 'help':
                print_help()
                continue
            
            msg_to_publish = HeadCommand()
            msg_to_publish.timestamp = time.time_ns()
            parts = raw_input.split()
            command = parts[0]
            
            command_sent = False
            if command == 'move' and len(parts) == 4:
                try:
                    yaw = float(parts[1])
                    pitch = float(parts[2])
                    expr = parts[3]
                    
                    # Set action using the integer value of the enum
                    msg_to_publish.action = HeadAction.MOVE_DIRECT.value
                    msg_to_publish.pitch_deg = pitch
                    msg_to_publish.yaw_deg = yaw
                    msg_to_publish.expression_char = expr
                    command_sent = True
                except (ValueError, IndexError):
                    print("Invalid format for 'move'. Use: move <yaw_deg> <pitch_deg> <char>")
            
            elif command == 'nod':
                msg_to_publish.action = HeadAction.NOD.value
                command_sent = True

            elif command == 'shake':
                msg_to_publish.action = HeadAction.SHAKE.value
                command_sent = True
            
            else:
                print("Unknown command. Type 'help' for a list of commands.")

            if command_sent:
                pub.Write(msg_to_publish)
                print(f"Published '{command}' command to DDS topic '{HEAD_COMMAND_TOPIC}'.")

        except KeyboardInterrupt:
            print("\nExiting client.")
            break
        except Exception as e:
            print(f"[Client Error] {e}")
    
        finally:
            # if pub:
                # pub.Close()
            print("DDS publisher closed.")

if __name__ == '__main__':
    main()
