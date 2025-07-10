#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
process_manager_client.py (v6)

Client with robust, list-free, atomic status updates and initial state display.
"""
import sys
import os
import time
import threading
import subprocess
from cyclonedds.domain import DomainParticipant
from cyclonedds.topic import Topic
from cyclonedds.pub import DataWriter
from cyclonedds.sub import DataReader

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from communication.dds_data_structure import ProcessCommand, ProcessAction, ProcessStatus, ScriptStatus

PROCESS_COMMAND_TOPIC = "ProcessCommand"
PROCESS_STATUS_TOPIC = "ProcessStatus"
SERVER_SCRIPT_NAME = "main_process_manager.py"
# The client now also knows the list of scripts to display their initial state
SCRIPTS_TO_MANAGE = (
    "main_camera_gateway.py", "main_control_gateway.py", "main_dog_body_control.py",
    "main_dog_head_control.py", "main_dog_status.py", "main_jetson_power_server.py",
    "main_speech_synthesis.py", "main_state_machine.py",
)

client_running = True
# This dictionary will store the latest status of each script
script_statuses = {}

def print_status_table():
    """Prints a formatted table from the collected status dictionary."""
    global script_statuses
    print("\n--- System Status ---")
    # Sort by script name for a consistent display
    sorted_names = sorted(script_statuses.keys())
    for name in sorted_names:
        s = script_statuses[name]
        status_line = f"  - {s.script_name:<30} | Status: {s.status:<10}"
        if s.status == "RUNNING":
            status_line += f"| PID: {s.pid}"
        print(status_line)
    print("---------------------")
    print(">> ", end="", flush=True)

def status_listener(subscriber: DataReader):
    """
    Waits for a complete ProcessStatus message, unpacks the manual fields,
    and then prints the status table.
    """
    global client_running, script_statuses
    print("-> Status listener started.")
    while client_running:
        for msg in subscriber.take():
            # Manually unpack the fields from the message into a list
            status_objects = [
                msg.cam_gateway, msg.ctrl_gateway, msg.body_ctrl, msg.head_ctrl,
                msg.dog_status, msg.power_srv, msg.speech_synth, msg.state_machine
            ]
            # Update the local dictionary with the fresh data
            for status_obj in status_objects:
                script_statuses[status_obj.script_name] = status_obj
            # Print the complete table now that all data is updated
            print_status_table()
        time.sleep(0.2)
    print("\n-> Status listener stopped.")

def print_help():
    print("\n--- Multi-Process Manager Client ---")
    print("  status                  - Request a live status update")
    print("  start/stop/restart all  - Control all scripts at once")
    print("  start/stop/restart <script_name> - Control a single script")
    print("  shutdown                - Stop the management server itself")
    print("  exit                    - Close this client (and the server)")
    print("------------------------------------")

def launch_server():
    # ... (function is unchanged)
    server_script_path = os.path.join(os.path.dirname(__file__), SERVER_SCRIPT_NAME)
    if not os.path.exists(server_script_path): return None
    try:
        server_process = subprocess.Popen([sys.executable, server_script_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return server_process
    except Exception: return None

def main():
    global client_running, script_statuses
    server_process, listener, writer = None, None, None

    try:
        # **MODIFICATION**: Populate initial status before doing anything else
        print("--- Initializing Client ---")
        for name in SCRIPTS_TO_MANAGE:
            script_statuses[name] = ScriptStatus(script_name=name, status="STOPPED", pid=0)
        
        server_process = launch_server()
        if not server_process: print("-> CRITICAL: Could not start server. Exiting."); return
        print(f"-> ACTION: Launched server (PID: {server_process.pid})")
        print("-> Waiting 3s for server to initialize...")
        time.sleep(3)

        participant = DomainParticipant(); cmd_topic = Topic(participant, PROCESS_COMMAND_TOPIC, ProcessCommand)
        status_topic = Topic(participant, PROCESS_STATUS_TOPIC, ProcessStatus); writer = DataWriter(participant, cmd_topic)
        reader = DataReader(participant, status_topic); listener = threading.Thread(target=status_listener, args=(reader,))
        listener.daemon = True; listener.start(); print_help()
        
        # Display the initial "STOPPED" status and request a live update
        print_status_table()
        print("-> Requesting live status from server...")
        writer.write(ProcessCommand(action=ProcessAction.STATUS_ALL.value))

        while True:
            parts = input(">> ").strip().lower().split()
            if not parts: continue
            command = parts[0]; target = parts[1] if len(parts) > 1 else None
            msg = ProcessCommand(timestamp=int(time.time_ns())); send_command = True
            if command == "exit": break
            elif command == "help": print_help(); send_command = False
            elif command == "status":
                print("-> Requesting live status update... Table will appear shortly.")
                msg.action = ProcessAction.STATUS_ALL.value
            elif command == "shutdown": msg.action = ProcessAction.SHUTDOWN_SERVER.value
            elif command == "start" and target == "all": msg.action = ProcessAction.START_ALL.value
            elif command == "stop" and target == "all": msg.action = ProcessAction.STOP_ALL.value
            elif command == "restart" and target == "all": msg.action = ProcessAction.RESTART_ALL.value
            elif command in ("start", "stop", "restart") and target:
                msg.action = {"start": ProcessAction.START, "stop": ProcessAction.STOP, "restart": ProcessAction.RESTART}[command]
                msg.target_script = target
            else: print("Unknown command. Type 'help'."); send_command = False
            if send_command: writer.write(msg)
            if msg.action == ProcessAction.SHUTDOWN_SERVER.value:
                print("-> Server shutdown initiated. Exiting client..."); time.sleep(1); break
    except (KeyboardInterrupt, EOFError): print("\n-> Client interrupted. Initiating shutdown...")
    finally:
        client_running = False
        if listener and listener.is_alive(): listener.join(timeout=1)
        if server_process and server_process.poll() is None:
            if writer:
                try: writer.write(ProcessCommand(action=ProcessAction.SHUTDOWN_SERVER.value)); time.sleep(1.5)
                except Exception: pass
            if server_process.poll() is None:
                try: server_process.terminate(); server_process.wait(timeout=2)
                except Exception: server_process.kill()
        print("\n-> Client and server shut down.")

if __name__ == '__main__':
    main()