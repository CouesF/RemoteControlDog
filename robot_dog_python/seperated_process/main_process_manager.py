#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main_process_manager.py (Server v6)

Features robust logging and sends a single atomic status update
with manually defined fields instead of a list.
"""
import sys
import os
import time
import subprocess
import signal
from cyclonedds.domain import DomainParticipant
from cyclonedds.topic import Topic
from cyclonedds.pub import DataWriter
from cyclonedds.sub import DataReader

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from communication.dds_data_structure import ProcessCommand, ProcessAction, ScriptStatus, ProcessStatus

PROCESS_COMMAND_TOPIC = "ProcessCommand"
PROCESS_STATUS_TOPIC = "ProcessStatus"
SCRIPTS_TO_MANAGE = {
    "main_camera_gateway.py": "cam_gateway",
    "main_control_gateway.py": "ctrl_gateway",
    "main_dog_body_control.py": "body_ctrl",
    "main_dog_head_control.py": "head_ctrl",
    "main_dog_status.py": "dog_status",
    "main_jetson_power_server.py": "power_srv",
    "main_speech_synthesis.py": "speech_synth",
}
managed_processes = {}
server_running = True
LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")

def launch_script(script_name: str):
    # ... (this function is unchanged from the previous version)
    if (script_name in managed_processes) and (managed_processes[script_name].poll() is None): return
    script_path = os.path.join(os.path.dirname(__file__), script_name)
    if not os.path.exists(script_path): return

    os.makedirs(LOG_DIR, exist_ok=True)
    log_file_path = os.path.join(LOG_DIR, f"{script_name}.log")
    log_file = open(log_file_path, "a", buffering=1)
    log_file.write(f"\n--- SESSION STARTED AT {time.ctime()} ---\n")
    process = subprocess.Popen([sys.executable, script_path], stdout=log_file, stderr=subprocess.STDOUT)
    managed_processes[script_name] = process
    process.log_file = log_file

def terminate_script(script_name: str):
    # ... (this function is unchanged from the previous version)
    if script_name in managed_processes and managed_processes[script_name].poll() is None:
        process = managed_processes[script_name]
        process.terminate()
        try: process.wait(timeout=2)
        except subprocess.TimeoutExpired: process.kill()
        if hasattr(process, 'log_file'):
            process.log_file.write(f"--- SESSION ENDED AT {time.ctime()} ---\n"); process.log_file.close()
        del managed_processes[script_name]

def publish_full_status(writer: DataWriter):
    """Builds and sends a single status report with manually-defined fields."""
    status_msg = ProcessStatus(timestamp=int(time.time_ns()))
    
    for script_name, field_name in SCRIPTS_TO_MANAGE.items():
        if (script_name in managed_processes) and (managed_processes[script_name].poll() is None):
            process = managed_processes[script_name]
            status_obj = ScriptStatus(script_name=script_name, status="RUNNING", pid=process.pid)
        else:
            status_obj = ScriptStatus(script_name=script_name, status="STOPPED", pid=0)
        # Set the corresponding attribute on the ProcessStatus object
        setattr(status_msg, field_name, status_obj)
    
    writer.write(status_msg)

def shutdown_handler(signum, frame): global server_running; server_running = False

def main():
    # ... (The main function is effectively unchanged, as the logic relies on the helpers)
    global server_running; signal.signal(signal.SIGINT, shutdown_handler)
    participant = DomainParticipant()
    cmd_topic = Topic(participant, PROCESS_COMMAND_TOPIC, ProcessCommand)
    status_topic = Topic(participant, PROCESS_STATUS_TOPIC, ProcessStatus)
    reader = DataReader(participant, cmd_topic)
    writer = DataWriter(participant, status_topic)
    print(f"--- Multi-Process Manager Server ---")
    print(f"-> Managing {len(SCRIPTS_TO_MANAGE)} scripts. Waiting for commands...")
    try:
        while server_running:
            for msg in reader.take():
                action = ProcessAction(msg.action); target = msg.target_script
                if action == ProcessAction.START: launch_script(target)
                elif action == ProcessAction.STOP: terminate_script(target)
                elif action == ProcessAction.RESTART: terminate_script(target); time.sleep(0.2); launch_script(target)
                elif action == ProcessAction.START_ALL: [launch_script(s) for s in SCRIPTS_TO_MANAGE]
                elif action == ProcessAction.STOP_ALL: [terminate_script(s) for s in list(managed_processes.keys())]
                elif action == ProcessAction.RESTART_ALL: [terminate_script(s) for s in list(managed_processes.keys())]; time.sleep(0.5); [launch_script(s) for s in SCRIPTS_TO_MANAGE]
                elif action == ProcessAction.SHUTDOWN_SERVER: server_running = False
                publish_full_status(writer)
            time.sleep(0.1)
    except Exception as e: print(f"An unexpected error occurred: {e}")
    finally:
        print("-> Server shutting down..."); [terminate_script(s) for s in list(managed_processes.keys())]; print("-> Server closed.")

if __name__ == '__main__':
    main()