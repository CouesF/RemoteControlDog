import sounddevice as sd
import soundfile as sf
import numpy as np
from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import threading
import queue
import time

app = Flask(__name__)
# Allow CORS for development purposes. In production, specify your frontend origin.
socketio = SocketIO(app, cors_allowed_origins="*")

# Audio recording parameters
FS = 16000  # Sampling rate
CHANNELS = 1 # Mono audio
DTYPE = 'int16' # Data type for audio samples

# Global variables for recording control
recording_active = False
audio_queue = queue.Queue() # Queue to store audio blocks for streaming
full_recording_data = [] # List to store all recorded data for saving to file
stream_thread = None
input_stream = None # Global to hold the sounddevice InputStream

def audio_callback(indata, frames, time_info, status):
    """
    This callback function is called by sounddevice for each audio block.
    It puts the audio data into a queue for processing by another thread
    and also stores it for the final recording file.
    """
    if status:
        print(f"Audio callback status: {status}")
    if recording_active:
        audio_queue.put(indata.copy())
        full_recording_data.append(indata.copy())

def stream_audio_to_clients():
    """
    This function runs in a separate thread and sends audio data
    from the queue to connected clients via WebSockets.
    """
    global recording_active
    while recording_active:
        try:
            # Get block with a short timeout to prevent indefinite blocking
            audio_block = audio_queue.get(timeout=0.1)
            # Convert numpy array to bytes for transmission over WebSocket
            # Each int16 sample is 2 bytes, so .tobytes() works directly.
            audio_bytes = audio_block.tobytes()
            socketio.emit('audio_data', audio_bytes, namespace='/audio')
            audio_queue.task_done()
        except queue.Empty:
            # If queue is empty, wait a bit before checking again
            time.sleep(0.01)
        except Exception as e:
            print(f"Error in streaming thread: {e}")
            # Consider more robust error handling here, potentially stopping recording
            break

@app.route('/')
def index():
    return render_template('record_template.html')

@socketio.on('connect', namespace='/audio')
def test_connect():
    print('Client connected to /audio namespace')
    emit('response', {'data': 'Connected to audio server'})

@socketio.on('disconnect', namespace='/audio')
def test_disconnect():
    print('Client disconnected from /audio namespace')

@socketio.on('start_recording', namespace='/audio')
def start_recording_command():
    global recording_active, stream_thread, input_stream, full_recording_data

    if recording_active:
        emit('status', {'message': 'Recording already active.'})
        return

    print("Received start_recording command.")
    full_recording_data = [] # Clear previous recording data
    # Ensure the queue is empty before starting
    while not audio_queue.empty():
        audio_queue.get()
        audio_queue.task_done()

    try:
        # Initialize the input stream
        input_stream = sd.InputStream(samplerate=FS, channels=CHANNELS,
                                      dtype=DTYPE, callback=audio_callback)
        input_stream.start()
        recording_active = True
        print("Recording started.")
        emit('status', {'message': 'Recording started.'})

        # Start the thread for streaming audio to clients
        stream_thread = threading.Thread(target=stream_audio_to_clients)
        stream_thread.daemon = True # Allow the main program to exit even if thread is running
        stream_thread.start()

    except Exception as e:
        print(f"Error starting recording: {e}")
        emit('status', {'message': f'Error starting recording: {e}'})
        recording_active = False # Reset flag if error occurred

@socketio.on('stop_recording', namespace='/audio')
def stop_recording_command():
    global recording_active, stream_thread, input_stream

    if not recording_active:
        emit('status', {'message': 'No active recording to stop.'})
        return

    print("Received stop_recording command.")
    recording_active = False # Signal the threads to stop

    # Wait for the streaming thread to finish processing its current queue
    if stream_thread and stream_thread.is_alive():
        audio_queue.join() # Wait until all items in the queue have been consumed
        stream_thread.join(timeout=2) # Give a short time for the thread to terminate
        if stream_thread.is_alive():
            print("Warning: Streaming thread did not terminate gracefully.")
        else:
            print("Streaming thread terminated.")

    if input_stream:
        input_stream.stop()
        input_stream.close()
        input_stream = None # Clear the stream object
        print("Input stream stopped and closed.")

    # Save the recorded audio
    if full_recording_data:
        try:
            # Concatenate all numpy arrays into a single array
            recording_array = np.concatenate(full_recording_data, axis=0)
            file_name = 'recorded_audio.wav'
            sf.write(file_name, recording_array, FS)
            print(f"Recording saved to {file_name}")
            emit('status', {'message': f'Recording stopped and saved to {file_name}.'})
        except Exception as e:
            print(f"Error saving recording: {e}")
            emit('status', {'message': f'Recording stopped, but error saving file: {e}'})
    else:
        print("No audio data was recorded.")
        emit('status', {'message': 'Recording stopped, but no audio data was captured.'})

if __name__ == '__main__':
    # It's recommended to run Flask in debug mode only for development.
    # For production, use a production-ready WSGI server like Gunicorn.
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)