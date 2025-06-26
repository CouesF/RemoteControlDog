#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dog_head_client.py

A command-line client to send control requests to the dog_head_server.
"""

import socket
import sys

# --- Configuration ---
# Change this to the IP address of the computer running the server.
# If running on the same machine, 'localhost' is fine.
SERVER_HOST = 'localhost'
SERVER_PORT = 65432

def send_command(command: str) -> str:
    """
    Connects to the server, sends a single command, and returns the response.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((SERVER_HOST, SERVER_PORT))
            s.sendall(command.encode('utf-8'))
            response = s.recv(1024).decode('utf-8')
            return response
    except ConnectionRefusedError:
        return f"Error: Connection refused. Is the server script running on {SERVER_HOST}?"
    except Exception as e:
        return f"An error occurred: {e}"

def print_help():
    """Prints the command instructions."""
    print("\n--- Robot Control Client ---")
    print("Available commands:")
    print("  move <m1_deg> <m2_deg> <expr>")
    print("    - Sets motor positions in degrees and screen expression.")
    print("    - Example: 'move 0 -10 c' -> M1 to 0°, M2 to -10°, screen to 'center'.")
    print("\n  nod")
    print("    - Makes the head perform a nodding motion.")
    print("\n  shake")
    print("    - Makes the head perform a shaking motion.")
    print("\n  help")
    print("    - Shows this help message.")
    print("\n  exit or quit")
    print("    - Exits the client program.")
    print("----------------------------")

def main():
    """Main user input loop for the client."""
    print_help()
    while True:
        try:
            raw_input = input(">> ").strip()
            if not raw_input:
                continue

            if raw_input.lower() in ('exit', 'q', 'quit'):
                print("Exiting client.")
                break
            
            if raw_input.lower() == 'help':
                print_help()
                continue

            response = send_command(raw_input)
            print(f"Server: {response}")

        except KeyboardInterrupt:
            print("\nExiting client.")
            break
        except Exception as e:
            print(f"[Client Error] {e}")


if __name__ == '__main__':
    main()
