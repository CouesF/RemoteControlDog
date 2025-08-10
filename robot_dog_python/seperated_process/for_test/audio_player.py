# /home/d3lab/Projects/RemoteControlDog/robot_dog_python/seperated_process/main_audio_player.py

import os
import pygame
import time

SCRIPT_DIRECTORY = os.path.dirname(os.path.realpath(__file__))
AUDIO_DIRECTORY = os.path.join(SCRIPT_DIRECTORY, 'audio')


class AudioPlayer:
    """
    A class to handle audio playback including selecting, playing, 
    pausing, and stopping audio files.
    """

    def __init__(self):
        """Initializes the pygame mixer."""
        try:
            pygame.mixer.init()
            print("AudioPlayer initialized successfully.")
        except pygame.error as e:
            print(f"Error initializing pygame mixer: {e}")
            print("Please ensure your Jetson Nano's audio output is configured correctly.")
            exit()
            
        self.current_file = None
        self.paused = False

    def list_audio_files(self):
        """Lists supported audio files in the audio directory."""
        supported_formats = ('.mp3', '.wav', '.ogg')
        try:
            # Use the dynamically generated path
            files = [f for f in os.listdir(AUDIO_DIRECTORY) if f.endswith(supported_formats)]
            return files
        except FileNotFoundError:
            # The error message now uses the dynamic path variable
            print(f"Error: Audio directory not found at '{AUDIO_DIRECTORY}'")
            return []

    def select_and_load(self, filename):
        """Loads a selected audio file for playback."""
        # Use the dynamically generated path
        filepath = os.path.join(AUDIO_DIRECTORY, filename)
        if not os.path.exists(filepath):
            print(f"Error: File '{filename}' not found.")
            return False
            
        try:
            pygame.mixer.music.load(filepath)
            self.current_file = filename
            self.paused = False
            print(f"Loaded: {self.current_file}")
            return True
        except pygame.error as e:
            print(f"Error loading file {filename}: {e}")
            return False

    def play(self):
        """Plays the loaded audio file or resumes if paused."""
        if not self.current_file:
            print("No audio file is loaded. Please select a file first.")
            return

        if not pygame.mixer.music.get_busy() and not self.paused:
            print(f"Playing: {self.current_file}")
            pygame.mixer.music.play()
        elif self.paused:
            print(f"Resuming: {self.current_file}")
            pygame.mixer.music.unpause()
            self.paused = False

    def pause(self):
        """Pauses the currently playing audio."""
        if pygame.mixer.music.get_busy() and not self.paused:
            pygame.mixer.music.pause()
            self.paused = True
            print("Playback paused.")
        else:
            print("Nothing is currently playing or it's already paused.")
            
    def stop(self):
        """Stops playback and unloads the file."""
        if self.current_file:
            print(f"Stopping and unloading: {self.current_file}")
            pygame.mixer.music.stop()
            pygame.mixer.music.unload()
            self.current_file = None
            self.paused = False
        else:
            print("No audio file is loaded to stop.")

# The rest of the script (main_cli function and the __main__ block)
# remains exactly the same and does not need to be changed.

def main_cli():
    """Main function to run the command-line interface for the audio player."""
    player = AudioPlayer()
    
    while True:
        print("\n--- Audio Player Menu ---")
        if player.current_file:
            print(f"Current File: {player.current_file}")
            if pygame.mixer.music.get_busy():
                status = "Paused" if player.paused else "Playing"
                print(f"Status: {status}")
            else:
                status = "Stopped (Loaded)"
                print(f"Status: {status}")
        else:
            print("No file loaded.")

        print("\nOptions:")
        print("1. Select Audio File")
        print("2. Play / Resume")
        print("3. Pause")
        print("4. Stop")
        print("5. Exit")
        
        choice = input("Enter your choice [1-5]: ")

        if choice == '1':
            audio_files = player.list_audio_files()
            if not audio_files:
                print("No audio files found in the directory.")
                continue
            
            print("\nAvailable audio files:")
            for i, f in enumerate(audio_files):
                print(f"  {i+1}: {f}")
            
            try:
                file_choice = int(input(f"Select a file [1-{len(audio_files)}]: "))
                if 1 <= file_choice <= len(audio_files):
                    selected_file = audio_files[file_choice - 1]
                    player.select_and_load(selected_file)
                else:
                    print("Invalid selection.")
            except (ValueError, IndexError):
                print("Invalid input. Please enter a number from the list.")

        elif choice == '2':
            player.play()
        
        elif choice == '3':
            player.pause()
            
        elif choice == '4':
            player.stop()

        elif choice == '5':
            player.stop()
            print("Exiting player.")
            break
            
        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    main_cli()