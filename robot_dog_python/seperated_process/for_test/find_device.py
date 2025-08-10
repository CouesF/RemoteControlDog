import pyaudio
import sys

def list_speakers():
    """
    Lists all available audio output devices (speakers).
    """
    print("--- Querying for Audio Output Devices (Speakers) ---")
    
    # Use a try-finally block to ensure PyAudio is terminated correctly.
    pa = None
    try:
        pa = pyaudio.PyAudio()
        
        # Get the total number of audio devices.
        device_count = pa.get_device_count()
        
        # A list to hold the indices of found output devices.
        speaker_indices = []
        
        print(f"Found {device_count} total audio devices.\n")
        
        # Iterate through all devices to find the ones that are outputs.
        for i in range(device_count):
            # Get the device information dictionary.
            device_info = pa.get_device_info_by_index(i)
            
            # Check if the device has one or more output channels.
            # This is the primary way to identify a speaker or output device.
            if device_info.get('maxOutputChannels') > 0:
                speaker_indices.append(i)
                print(f"--- Speaker Found: Device Index {device_info.get('index')} ---")
                print(f"  Name: {device_info.get('name')}")
                print(f"  Host API: {pa.get_host_api_info_by_index(device_info.get('hostApi'))['name']}")
                print(f"  Max Output Channels: {device_info.get('maxOutputChannels')}")
                print(f"  Default Sample Rate: {device_info.get('defaultSampleRate')} Hz\n")

        if not speaker_indices:
            print("No audio output devices (speakers) were found.")
            
    except Exception as e:
        print(f"An error occurred: {e}")
        print("Please ensure the PortAudio library is installed correctly.")
        
    finally:
        # Terminate the PyAudio instance to release system resources.
        if pa:
            pa.terminate()
            print("--- Query Complete ---")

if __name__ == '__main__':
    # Add a check to guide the user if pyaudio is not installed.
    try:
        import pyaudio
    except ImportError:
        print("Error: The 'pyaudio' library is not installed.")
        print("On your Jetson Nano (Ubuntu), you can install it using:")
        print("sudo apt-get install python3-pyaudio")
        sys.exit(1)
        
    list_speakers()