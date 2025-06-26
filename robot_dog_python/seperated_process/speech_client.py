# speech_client.py
import time
import sys
import os
import threading
import uuid

# --- FIX FOR CROSS-DIRECTORY IMPORT ---
# This assumes your 'communication' directory is one level above this script's directory.
# Adjust the path if your project structure is different.
try:
    current_script_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_script_dir)
    communication_dir_path = os.path.join(parent_dir, 'communication')
    if communication_dir_path not in sys.path:
        sys.path.append(communication_dir_path)
    from dds_data_structure import SpeechControl, SpeechStatus
except ImportError:
    print("Error: Could not import 'SpeechControl' or 'SpeechStatus'.")
    print("Please ensure that:")
    print("1. Your 'communication' directory is correctly located.")
    print("2. 'dds_data_structure.py' exists within it and defines both 'SpeechControl' and 'SpeechStatus' classes.")
    sys.exit(1)
# --- END OF FIX ---


from unitree_sdk2py.core.channel import ChannelPublisher, ChannelSubscriber, ChannelFactoryInitialize

# --- CONFIGURATION ---
DDS_NETWORK_INTERFACE = "enP8p1s0"  # Match this with your other DDS scripts

class SpeechClient:
    """
    A DDS client to send commands to the speech synthesis script and receive status updates.
    """
    def __init__(self):
        """
        Initializes DDS communication, setting up a publisher for commands and a
        subscriber for status messages.
        """
        print(f"Initializing DDS on network interface: {DDS_NETWORK_INTERFACE}")
        try:
            ChannelFactoryInitialize(networkInterface=DDS_NETWORK_INTERFACE)
        except Exception as e:
            print(f"Fatal Error: Failed to initialize DDS. Check the network interface. Error: {e}")
            sys.exit(1)

        # Publisher to send control commands (say, stop, etc.)
        self.control_pub = ChannelPublisher("SpeechControl", SpeechControl)
        self.control_pub.Init()

        # Subscriber to receive status updates (e.g., "speaking", "finished")
        self.status_sub = ChannelSubscriber("SpeechStatus", SpeechStatus)
        self.status_sub.Init()

        print("DDS Initialized. Speech client is ready.")

        # A separate thread to continuously listen for status messages
        self.is_running = True
        self.listener_thread = threading.Thread(target=self._listen_for_status, daemon=True)
        self.listener_thread.start()

    def _listen_for_status(self):
        """
        Private method that runs in a background thread to read and print status messages.
        """
        print("[Status Listener] Started. Waiting for status messages...")
        while self.is_running:
            try:
                # Read from the subscriber with a 1-second timeout
                status_msg = self.status_sub.Read(1)
                if status_msg:
                    # A new status message has been received
                    print(f"\n[STATUS UPDATE] ID: {status_msg.task_id} | Status: {status_msg.status} | Message: {status_msg.message}")
                    # Reprint the input prompt to keep the UI clean
                    print("Enter command > ", end="", flush=True)

            except Exception as e:
                # This helps catch DDS errors that might not be fatal
                if "take sample error" not in str(e):
                    print(f"\n[Status Listener] Error reading DDS message: {e}")
            
            time.sleep(0.1) # Small delay to prevent high CPU usage

    def say(self, text: str) -> str:
        """
        Publishes a command to synthesize and speak the given text.

        Args:
            text: The sentence to be spoken.

        Returns:
            The unique task ID for this speech request.
        """
        if not text:
            print("Cannot send empty text.")
            return ""
            
        # Generate a unique ID to track this specific request
        task_id = str(uuid.uuid4())[:8]
        print(f"Sending SAY command (ID: {task_id}): '{text}'")
        
        # Create the DDS message object
        msg = SpeechControl()
        msg.task_id = task_id
        msg.text_to_speak = text
        msg.stop_speaking = False # Ensure this is false for a new request
        msg.volume = -1 # Use -1 to indicate no volume change
        
        # Publish the message
        self.control_pub.Write(msg)
        return task_id

    def stop(self):
        """
        Publishes a command to immediately stop any ongoing speech.
        """
        print("Sending STOP command...")
        msg = SpeechControl()
        msg.stop_speaking = True
        msg.text_to_speak = "" # Clear text
        msg.task_id = "stop_command"
        msg.volume = -1
        self.control_pub.Write(msg)

    def pause(self):
        """
        Pauses the speech. For the current implementation, this is the same as stop.
        """
        print("Sending PAUSE command (acts as STOP).")
        self.stop()

    def set_volume(self, volume: int):
        """
        Publishes a command to set the synthesizer's volume.

        Args:
            volume: The desired volume, from 0 to 100.
        """
        vol = max(0, min(100, volume)) # Clamp volume between 0 and 100
        print(f"Sending SET VOLUME command: {vol}%")
        msg = SpeechControl()
        msg.volume = vol
        msg.text_to_speak = ""
        msg.stop_speaking = False
        msg.task_id = "volume_command"
        self.control_pub.Write(msg)

    def close(self):
        """
        Properly shuts down the client and DDS resources.
        """
        print("Shutting down speech client...")
        self.is_running = False
        self.listener_thread.join(timeout=2)
        self.control_pub.Close()
        self.status_sub.Close()
        print("Shutdown complete.")

def main_interactive_loop():
    """
    The main function to run the client in an interactive command-line mode.
    """
    client = SpeechClient()
    
    # --- Instructions for required changes in other files ---
    print("\n" + "="*60)
    print("IMPORTANT SETUP INSTRUCTIONS:")
    print("1. In 'dds_data_structure.py', ensure 'SpeechControl' and 'SpeechStatus' are defined.")
    print("   See comments in this script for the required class structure.")
    print("2. In 'main_speech_synthesis.py', you MUST add a 'ChannelPublisher' for 'SpeechStatus'")
    print("   and publish status messages during its operation.")
    print("="*60 + "\n")
    
    try:
        while True:
            cmd_input = input("Enter command (say <text>, stop, pause, volume <0-100>, exit) > ").strip()
            parts = cmd_input.split(" ", 1)
            command = parts[0].lower()

            if command == "say":
                if len(parts) > 1 and parts[1]:
                    client.say(parts[1])
                else:
                    print("Usage: say <text to speak>")
            elif command == "stop":
                client.stop()
            elif command == "pause":
                client.pause()
            elif command == "volume":
                if len(parts) > 1 and parts[1].isdigit():
                    client.set_volume(int(parts[1]))
                else:
                    print("Usage: volume <percentage between 0 and 100>")
            elif command == "exit":
                print("Exiting...")
                break
            elif not command:
                continue
            else:
                print(f"Unknown command: '{command}'")
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
    finally:
        client.close()

if __name__ == "__main__":
    main_interactive_loop()
