import cv2
import threading
import time

# A flag to signal the threads to stop
stop_threads = False

def capture_frames(camera_index: int):
    """
    A function to be run in a thread for capturing frames from a single camera.
    
    Args:
        camera_index (int): The index of the camera (e.g., 0, 1, 2).
    """
    # Open the camera device
    cap = cv2.VideoCapture(camera_index)

    # --- MODIFICATION START ---
    # Apply specific settings based on camera index
    if camera_index == 0:
        # For camera 0, use the efficient MJPG format at a standard resolution
        try:
            print(f"Applying custom settings to camera {camera_index}...")
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            cap.set(cv2.CAP_PROP_FPS, 30)
            print(f"Custom settings applied for camera {camera_index}.")
        except Exception as e:
            print(f"Could not apply custom settings to camera {camera_index}: {e}")

    elif camera_index in [2, 4]:
        # For cameras 2 and 4, use YUY2 at low resolution
        try:
            print(f"Applying custom settings to camera {camera_index}...")
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'YUY2'))
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
            cap.set(cv2.CAP_PROP_FPS, 30)
            print(f"Custom settings applied for camera {camera_index}.")
        except Exception as e:
            print(f"Could not apply custom settings to camera {camera_index}: {e}")
    # --- MODIFICATION END ---


    # Check if the camera was opened successfully
    if not cap.isOpened():
        print(f"Error: Could not open camera {camera_index}.")
        return

    print(f"Thread for camera {camera_index}: Started.")

    while not stop_threads:
        # Read a frame from the camera
        ret, frame = cap.read()

        # Check if the frame was read successfully
        if ret:
            # You can process the 'frame' (a NumPy array) here.
            # For this example, we just print its shape.
            print(f"Successfully read frame from camera {camera_index} with shape: {frame.shape}")
        else:
            print(f"Error: Could not read frame from camera {camera_index}. Exiting thread.")
            break
        
        # Add a small delay to prevent overwhelming the CPU
        time.sleep(0.01)

    # Release the camera resource when the loop is done
    cap.release()
    print(f"Thread for camera {camera_index}: Released camera and stopped.")

# --- Main Script ---
if __name__ == "__main__":
    camera_indices = [0, 2, 4]  # List of camera indexes to use
    threads = []

    print("Starting camera capture threads...")

    # Create and start a thread for each camera
    for index in camera_indices:
        thread = threading.Thread(target=capture_frames, args=(index,))
        threads.append(thread)
        thread.start()

    try:
        # The main thread will wait here until a KeyboardInterrupt (Ctrl+C)
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nKeyboard interrupt received. Stopping all threads...")
        stop_threads = True

    # Wait for all threads to complete their execution
    for thread in threads:
        thread.join()

    print("All threads have been stopped. Exiting program.")