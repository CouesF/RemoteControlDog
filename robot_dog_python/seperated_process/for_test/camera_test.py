import cv2
import threading
import time

# --- GStreamer Pipeline Function ---
# This function generates the GStreamer pipeline string for a CSI camera.
# It's highly recommended to use this for consistent and correct setup.
def gstreamer_pipeline(
    sensor_id=0,
    capture_width=1920,
    capture_height=1080,
    display_width=960,
    display_height=540,
    framerate=30,
    flip_method=0, # 0 = none, 1 = counterclockwise, 2 = 180, 3 = clockwise, 4 = horizontal flip, 5 = vertical flip
):
    """
    Returns a GStreamer pipeline string for capturing from a CSI camera.
    
    Args:
        sensor_id (int): ID of the CSI camera (0, 1, etc.).
        capture_width (int): Native resolution width of the camera sensor.
        capture_height (int): Native resolution height of the camera sensor.
        display_width (int): Width for the displayed/processed frame.
        display_height (int): Height for the displayed/processed frame.
        framerate (int): Frame rate of the camera.
        flip_method (int): Method to flip the captured image.
    """
    return (
        f"nvarguscamerasrc sensor-id={sensor_id} ! "
        f"video/x-raw(memory:NVMM), width=(int){capture_width}, height=(int){capture_height}, "
        f"format=(string)NV12, framerate=(fraction){framerate}/1 ! "
        f"nvvidconv flip-method={flip_method} ! "
        f"video/x-raw, width=(int){display_width}, height=(int){display_height}, format=(string)BGRx ! "
        "videoconvert ! "
        "video/x-raw, format=(string)BGR ! appsink drop=true"
    )

# --- Camera Capture Class (Optional but recommended for multiple cameras) ---
# This class encapsulates camera reading in a separate thread to prevent blocking
# and improve frame rate consistency, especially for multiple cameras.
class CameraStream:
    def __init__(self, pipeline_string):
        self.pipeline_string = pipeline_string
        self.cap = None
        self.frame = None
        self.ret = False
        self.stopped = False
        self.thread = None

    def start(self):
        print(f"Opening camera with pipeline: {self.pipeline_string}")
        self.cap = cv2.VideoCapture(self.pipeline_string, cv2.CAP_GSTREAMER)
        if not self.cap.isOpened():
            print(f"Error: Failed to open camera with pipeline: {self.pipeline_string}")
            self.stop()
            return False
        self.ret, self.frame = self.cap.read()
        self.thread = threading.Thread(target=self._update, args=())
        self.thread.daemon = True
        self.thread.start()
        print(f"Camera opened successfully.")
        return True

    def _update(self):
        while not self.stopped:
            if self.cap.isOpened():
                self.ret, self.frame = self.cap.read()
                if not self.ret:
                    print("Warning: Failed to read frame, stopping camera.")
                    self.stopped = True
            else:
                self.stopped = True
            time.sleep(0.001) # Small sleep to prevent busy-waiting

    def read(self):
        return self.ret, self.frame

    def stop(self):
        self.stopped = True
        if self.thread is not None:
            self.thread.join()
        if self.cap is not None:
            self.cap.release()
        print("Camera stream stopped.")

# --- Main Program ---
if __name__ == "__main__":
    # Define parameters for Camera 0
    cam0_pipeline = gstreamer_pipeline(
        sensor_id=0,
        capture_width=1920,   # Sensor's native resolution
        capture_height=1080,
        display_width=640,    # Desired display/processing resolution
        display_height=360,
        framerate=30,
        flip_method=0
    )

    # Define parameters for Camera 1
    cam1_pipeline = gstreamer_pipeline(
        sensor_id=1,
        capture_width=1920,   # Sensor's native resolution
        capture_height=1080,
        display_width=640,    # Desired display/processing resolution
        display_height=360,
        framerate=30,
        flip_method=0
    )

    # Create and start camera streams
    camera0 = CameraStream(cam0_pipeline)
    camera1 = CameraStream(cam1_pipeline)

    if not camera0.start():
        print("Exiting: Camera 0 failed to start.")
        exit()
    if not camera1.start():
        print("Exiting: Camera 1 failed to start.")
        camera0.stop() # Ensure camera0 is stopped if camera1 fails
        exit()

    try:
        while True:
            ret0, frame0 = camera0.read()
            ret1, frame1 = camera1.read()

            if not ret0 or not ret1:
                print("Failed to retrieve frames from one or both cameras. Exiting.")
                break

            # Process or display frames
            cv2.imshow('Camera 0 Feed', frame0)
            cv2.imshow('Camera 1 Feed', frame1)

            # Press 'q' to quit
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    except KeyboardInterrupt:
        print("Interrupted by user.")
    finally:
        # Release resources
        camera0.stop()
        camera1.stop()
        cv2.destroyAllWindows()