# Camera System Refactoring Plan

This document outlines the plan to refactor the camera functionality within the Electron application. The goal is to create a robust, reusable, and centralized system for handling camera streams based on the protocol established in `Doc/test/cam_test.py`.

## 1. Analysis of `cam_test.py`

The existing Python test script reveals the following about the camera gateway protocol:

-   **Transport:** UDP.
-   **Communication:**
    -   Client sends JSON-based requests (`get_camera_list`, `subscribe`, `unsubscribe`).
    -   Server responds with JSON messages.
    -   Server streams video data as binary packets.
-   **Data Formats:**
    -   **Control Packets (JSON):** A simple protocol with a 2-byte header length, a JSON header, and a JSON payload.
    -   **Video Frame Packets (Binary):**
        -   Uses a magic byte (`0xFF` for a full frame, `0xFE` for a fragment).
        -   Includes metadata like timestamp, camera ID, resolution, and quality.
        -   Supports fragmentation and reassembly for large frames.

## 2. Refactoring Architecture

We will adopt a two-part architecture that separates the low-level network communication from the high-level UI presentation.

### Main Process (`src/main`)

-   **`camera_udp_handler.js`:** This will be the core of the new system on the backend. It will be rewritten to act as a `CameraClient`, mirroring the logic from `cam_test.py`.
    -   Manages the UDP socket connection to the camera gateway.
    -   Handles sending subscription requests and other commands.
    -   Listens for incoming UDP packets.
    -   Implements the logic for reassembling fragmented frames.
    -   Parses binary frame headers.
    -   Forwards processed camera lists and video frames to the renderer process via IPC (`ipcMain`).

-   **`main.js`:**
    -   Integrates and initializes the `camera_udp_handler`.
    -   Sets up IPC channels to communicate with the renderer process.

### Renderer Process (`src/renderer`)

-   **`js/components/camera/CameraManager.js` (New):**
    -   Acts as the single point of contact for all camera-related functionality in the UI.
    -   Communicates with the main process via `window.api` (exposed through `preload.js`).
    -   Provides methods like `getCameraList()`, `subscribe(cameraIds)`, `unsubscribe()`.
    -   Manages an internal state of camera streams and notifies UI components of new frames using an event-driven approach.

-   **`js/components/camera/CameraDisplay.js` (New):**
    -   A reusable UI component responsible for rendering a single camera feed on a `<canvas>` element.
    -   Receives frame data from the `CameraManager`.

-   **`js/components/MultiCameraMonitor.js` (Refactored):**
    -   A container component that displays multiple `CameraDisplay` instances.
    -   Manages the layout of the camera views (e.g., one main view, multiple smaller auxiliary views).
    -   Uses the `CameraManager` to subscribe to the required set of cameras.

-   **`js/config/camera-config.js` (New):**
    -   A configuration file to define presets for camera views, such as default resolutions and layouts. This will allow easy modification of how cameras are displayed.
    -   Defines which camera ID is the "main" camera (ID `2`) and which are auxiliary (IDs `0`, `1`).

-   **Cleanup:**
    -   The existing `CameraConnectionDebugger.js` component and its related UI will be removed.
    -   Any scattered camera logic in the HTML pages will be replaced by the new `MultiCameraMonitor` component.

## 3. Implementation Steps

1.  **Create New Files:**
    -   `control_end_electron/CAMERA_REFACTOR_SUMMARY.md` (this file).
    -   `control_end_electron/src/renderer/js/config/camera-config.js`.
    -   `control_end_electron/src/renderer/js/components/camera/CameraManager.js`.
    -   `control_end_electron/src/renderer/js/components/camera/CameraDisplay.js`.
    -   `control_end_electron/src/renderer/js/components/camera/RobotCameraView.js` (as a wrapper if needed).

2.  **Refactor Main Process:**
    -   Rewrite `camera_udp_handler.js` to implement the full client protocol.
    -   Update `main.js` and `preload.js` to establish the new IPC channels.

3.  **Implement Renderer Components:**
    -   Build the new camera components (`CameraManager`, `CameraDisplay`, `MultiCameraMonitor`).

4.  **Integrate into Views:**
    -   Update `experiment_control.html`, `map_builder.html`, etc., to use the `<multi-camera-monitor>` component.

5.  **Cleanup:**
    -   Delete `CameraConnectionDebugger.js`.
    -   Delete `camera_debug_test.html`.
    -   Remove any old, unused camera-related code.
