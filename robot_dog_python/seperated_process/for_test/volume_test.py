import pyaudio
import numpy as np
from pydub import AudioSegment
import threading
import os
import sys
import time

def list_audio_devices():
    """
    Lists all available audio output devices that PyAudio can see.
    """
    p = pyaudio.PyAudio()
    print("--- Available Audio Output Devices ---")
    info = p.get_host_api_info_by_index(0)
    numdevices = info.get('deviceCount')
    for i in range(0, numdevices):
        device_info = p.get_device_info_by_index(i)
        if device_info.get('maxOutputChannels') > 0:
            print(f"Index: {i}, Name: {device_info.get('name')}")
    print("------------------------------------")
    p.terminate()


class AudioPlayer:
    """
    A class to play audio files in a separate thread with real-time volume control
    and specific device selection.
    """
    def __init__(self, file_path, device_index=2):
        """
        Initializes the audio player.

        Args:
            file_path (str): The path to the audio file.
            device_index (int, optional): The index of the output device to use. 
                                          Defaults to None (system default).
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Error: The file '{file_path}' was not found.")

        print("Loading audio file...")
        self.audio_segment = AudioSegment.from_file(file_path)
        
        self.sample_width = self.audio_segment.sample_width
        self.channels = self.audio_segment.channels
        self.frame_rate = self.audio_segment.frame_rate
        self.device_index = device_index
        
        if self.sample_width == 2:
            self.dtype = np.int16
        elif self.sample_width == 4:
            self.dtype = np.int32
        else:
            raise ValueError(f"Unsupported sample width: {self.sample_width}")

        self.audio_data = np.frombuffer(self.audio_segment.raw_data, dtype=self.dtype)
        
        self.volume = 1.0
        self.is_playing = threading.Event()
        self.lock = threading.Lock()
        self.playback_thread = None

    def _playback_task(self):
        """
        The internal method that runs in a separate thread to handle audio playback.
        """
        # Increased chunk size to reduce CPU overhead and prevent buffer underruns.
        chunk_size = 4096

        p = pyaudio.PyAudio()

        stream = p.open(format=p.get_format_from_width(self.sample_width),
                        channels=self.channels,
                        rate=self.frame_rate,
                        output=True,
                        output_device_index=self.device_index,
                        frames_per_buffer=chunk_size)
        
        device_name = "Default Device"
        if self.device_index is not None:
            device_name = p.get_device_info_by_index(self.device_index).get('name')
        print(f"Playback started on: {device_name}. Control volume from the main terminal.")
        
        try:
            for i in range(0, len(self.audio_data), chunk_size):
                if not self.is_playing.is_set():
                    break

                chunk = self.audio_data[i:i + chunk_size]

                with self.lock:
                    current_volume = self.volume

                adjusted_chunk = (chunk * current_volume).astype(self.dtype)
                stream.write(adjusted_chunk.tobytes())
        finally:
            stream.stop_stream()
            stream.close()
            p.terminate()
            print("\nPlayback stopped and resources released.")
            self.is_playing.clear()

    # The play, set_volume, stop, and is_active methods are unchanged.
    def play(self):
        if self.is_playing.is_set():
            print("Audio is already playing.")
            return
        self.is_playing.set()
        self.playback_thread = threading.Thread(target=self._playback_task)
        self.playback_thread.daemon = True
        self.playback_thread.start()

    def set_volume(self, volume_level):
        if not 0.0 <= volume_level <= 5.0:
            print("Warning: Volume should be between 0.0 and 5.0.")
            return
        with self.lock:
            self.volume = volume_level
        print(f"Volume set to {volume_level * 100:.0f}%")

    def stop(self):
        if self.is_playing.is_set():
            self.is_playing.clear()
            if self.playback_thread:
                self.playback_thread.join(timeout=2)

    def is_active(self):
        return self.is_playing.is_set()


if __name__ == "__main__":
    # --- STEP 1: Run once to see device list. Find the index for your USB device. ---
    list_audio_devices()

    # --- STEP 2: Set the target device index here. ---
    # Replace None with the integer index of your "USB PnP Audio Device".
    # For example, if the list shows "Index: 2, Name: USB PnP Audio Device",
    # set TARGET_DEVICE_INDEX = 2
    TARGET_DEVICE_INDEX = 2 # <-- EDIT THIS LINE

    # --- Configuration ---
    audio_file = "/home/d3lab/Projects/RemoteControlDog/robot_dog_python/seperated_process/audio/sparkle_8s_split.mp3"

    try:
        # Pass the selected device index to the player
        player = AudioPlayer(audio_file, device_index=TARGET_DEVICE_INDEX)
        player.play()

        print("\n--- Audio Control ---")
        print("Enter a number to set volume (e.g., 0.5 for 50%, 1.0 for 100%).")
        print("Type 'q' or 'quit' to exit.")
        print("---------------------\n")
        
        while player.is_active():
            try:
                command = input("Set volume or quit (q): ").strip().lower()
                if command in ('q', 'quit'):
                    player.stop()
                    break
                new_volume = float(command)
                player.set_volume(new_volume)
            except ValueError:
                print("Invalid input. Please enter a number for volume or 'q' to quit.")
            except KeyboardInterrupt:
                print("\nInterrupted by user.")
                player.stop()
                break
        
        time.sleep(0.5)
        print("Program finished.")

    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)