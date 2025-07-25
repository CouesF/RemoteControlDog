#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Integrated Web Application for Periodic Camera Capture (v2)

This FastAPI application directly controls a camera to periodically capture images.
It replaces the separate UDP gateway and web bridge, simplifying the architecture.
Distortion correction has been explicitly removed.
"""
import asyncio
import os
import threading
import time
import uuid
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

import aiofiles
import cv2
import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# --- Configuration ---
# Define your cameras here. The script will use TARGET_CAMERA_ID.
CAMERA_CONFIGS = {
    0: {"type": "csi", "resolution": (1280, 720), "fps": 15, "name": "CSI Camera 0"},
    1: {"type": "csi", "resolution": (1280, 720), "fps": 15, "name": "CSI Camera 1"},
    2: {
        "type": "usb",
        "resolution": (640, 480),
        "fps": 15,
        "quality": 85, # JPEG quality for saved images
        "name": "USB Camera 2",
    },
}

# --- Key Settings ---
TARGET_CAMERA_ID = 0  # The camera you want this app to control.
CAPTURE_INTERVAL_SECONDS = 2  # How often to automatically capture an image.
CAPTURE_DIR = "captures"  # Directory to save images.

# Create the directory for captures if it doesn't exist
os.makedirs(CAPTURE_DIR, exist_ok=True)


# --- Camera Handling Logic (Adapted from your gateway) ---
class SmartCameraHandler:
    """A streamlined class to manage a single camera instance."""

    def __init__(self, camera_id: int, config: Dict[str, Any]):
        self.camera_id = camera_id
        self.config = config
        self.cap: Optional[cv2.VideoCapture] = None
        self.is_running = False
        self.capture_thread = None
        self._lock = threading.Lock()
        print(f"Initializing handler for camera {camera_id} ({config.get('name')})")

    def _get_csi_gstreamer_pipeline(self, width, height, fps) -> str:
        """Returns a GStreamer pipeline string for CSI cameras."""
        pipeline = (
            f"nvarguscamerasrc sensor-id={self.camera_id} ! "
            f"video/x-raw(memory:NVMM), width=(int){width}, height=(int){height}, framerate=(fraction){fps}/1 ! "
            "nvvidconv ! "
            "video/x-raw, format=(string)BGRx ! "
            "videoconvert ! "
            "video/x-raw, format=(string)BGR ! appsink drop=true max-buffers=1"
        )
        return pipeline

    def start(self) -> bool:
        """Starts the camera based on its configured type."""
        with self._lock:
            cam_type = self.config.get("type", "usb").lower()
            success = False

            if self.is_running:
                print("Camera is already running.")
                return True

            print(f"Attempting to start camera {self.camera_id} as type: {cam_type}")
            if cam_type == "csi":
                pipeline = self._get_csi_gstreamer_pipeline(*self.config['resolution'], self.config['fps'])
                self.cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
            elif cam_type == "usb":
                self.cap = cv2.VideoCapture(self.camera_id, cv2.CAP_V4L2)
                if self.cap and self.cap.isOpened():
                    self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config['resolution'][0])
                    self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config['resolution'][1])
                    self.cap.set(cv2.CAP_PROP_FPS, self.config['fps'])
                    self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            if not self.cap or not self.cap.isOpened():
                print(f"ERROR: Failed to open camera {self.camera_id}.")
                self.cap = None
                return False

            # Test read a frame
            ret, frame = self.cap.read()
            if not ret or frame is None:
                print(f"ERROR: Opened camera {self.camera_id}, but could not read a frame.")
                self.cap.release()
                self.cap = None
                return False

            self.is_running = True
            print(f"SUCCESS: Camera {self.camera_id} started. Resolution: {frame.shape}")
            return True

    def stop(self):
        """Stops the camera and releases resources."""
        with self._lock:
            if not self.is_running:
                return
            self.is_running = False
            if self.cap:
                print(f"Releasing camera {self.camera_id}...")
                self.cap.release()
                self.cap = None
            print(f"Camera {self.camera_id} stopped.")

    def capture_frame(self) -> Optional[np.ndarray]:
        """Captures a single raw frame from the camera."""
        if not self.is_running or not self.cap:
            print("Capture failed: Camera is not running.")
            return None
        
        with self._lock:
            # For some cameras, reading a few frames ensures the latest image
            for _ in range(3):
                 self.cap.grab()

            ret, frame = self.cap.read()
            if not ret or frame is None:
                print("Failed to capture frame from camera.")
                return None
            return frame

# --- FastAPI App & Global State ---
app = FastAPI(title="Periodic Camera Capture App")

class AppState:
    camera_handler: Optional[SmartCameraHandler] = None
    latest_image_path: Optional[str] = None
    capture_task: Optional[asyncio.Task] = None

app_state = AppState()

# --- Background Task for Periodic Capture ---
async def periodic_capture_task():
    """A background task that captures an image every X seconds."""
    print("Starting periodic capture background task...")
    while True:
        await asyncio.sleep(CAPTURE_INTERVAL_SECONDS)
        print(f"[{datetime.now()}] Triggering periodic capture...")
        await perform_capture()

async def perform_capture() -> Optional[str]:
    """The core logic to capture, save, and update state."""
    if not app_state.camera_handler:
        print("Error: Camera handler not initialized.")
        return None

    # Run blocking CV2 code in a separate thread
    frame = await asyncio.to_thread(app_state.camera_handler.capture_frame)

    if frame is None:
        print("Capture process failed to get a frame.")
        return None

    # --- Frame Processing (No Distortion Correction) ---
    # Directly encode the raw frame.
    encode_params = [cv2.IMWRITE_JPEG_QUALITY, app_state.camera_handler.config.get('quality', 90)]
    success, encoded_jpg = cv2.imencode('.jpg', frame, encode_params)

    if not success:
        print("Error: Failed to encode frame to JPEG.")
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"capture_{timestamp}.jpg"
    filepath = os.path.join(CAPTURE_DIR, filename)
    
    try:
        async with aiofiles.open(filepath, 'wb') as f:
            await f.write(encoded_jpg.tobytes())
        
        relative_path = f"/{CAPTURE_DIR}/{filename}"
        print(f"Image saved: {filepath}")
        
        # Update global state with the path to the new image
        app_state.latest_image_path = relative_path
        return relative_path
    except Exception as e:
        print(f"Error saving file: {e}")
        return None

# --- FastAPI Event Handlers ---
@app.on_event("startup")
async def startup_event():
    """Initializes the camera and starts the background capture task."""
    print("--- Application Starting Up ---")
    if TARGET_CAMERA_ID not in CAMERA_CONFIGS:
        raise RuntimeError(f"TARGET_CAMERA_ID {TARGET_CAMERA_ID} not found in CAMERA_CONFIGS.")
    
    config = CAMERA_CONFIGS[TARGET_CAMERA_ID]
    app_state.camera_handler = SmartCameraHandler(TARGET_CAMERA_ID, config)
    
    # Run blocking start method in a thread
    success = await asyncio.to_thread(app_state.camera_handler.start)

    if success:
        # Start the background task
        app_state.capture_task = asyncio.create_task(periodic_capture_task())
    else:
        print("CRITICAL: Camera failed to start. The application will run without capture functionality.")

@app.on_event("shutdown")
async def shutdown_event():
    """Stops the camera and cancels the background task."""
    print("--- Application Shutting Down ---")
    if app_state.capture_task:
        app_state.capture_task.cancel()
    if app_state.camera_handler:
        await asyncio.to_thread(app_state.camera_handler.stop)

# --- API Endpoints ---
# Serve static files and captured images
app.mount(f"/{CAPTURE_DIR}", StaticFiles(directory=CAPTURE_DIR), name="captures")
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def get_index():
    """Serves the main HTML page."""
    try:
        async with aiofiles.open('static/index_v2.html', mode='r') as f:
            return await f.read()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="index_v2.html not found in 'static' directory.")

@app.post("/capture")
async def trigger_manual_capture():
    """Endpoint to trigger a one-off, on-demand capture."""
    print("Manual capture triggered via API.")
    saved_path = await perform_capture()
    if saved_path:
        return {"status": "success", "path": saved_path}
    else:
        raise HTTPException(status_code=500, detail="Failed to perform capture.")

@app.get("/latest_image")
async def get_latest_image_path():
    """Returns the path to the most recently captured image."""
    if app_state.latest_image_path:
        return {"path": app_state.latest_image_path}
    return HTTPException(status_code=404, detail="No image has been captured yet.")

@app.get("/list_captures")
async def list_captures():
    """Returns a sorted list of all captured images."""
    try:
        files = sorted(
            [f for f in os.listdir(CAPTURE_DIR) if f.endswith(".jpg")],
            key=lambda f: os.path.getmtime(os.path.join(CAPTURE_DIR, f)),
            reverse=True
        )
        captures = [{"filename": f, "path": f"/{CAPTURE_DIR}/{f}"} for f in files]
        return JSONResponse(content=captures)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    # Make sure to create a 'static' folder and place your 'index_v2.html' in it.
    print("Starting web application server...")
    print(f"View the UI at http://127.0.0.1:8002")
    uvicorn.run(app, host="0.0.0.0", port=8002)