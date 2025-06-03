import cv2
import numpy as np
import time

class ScaramuzzaFisheyeUndistorter:
    def __init__(self, mapping_coeffs, image_size, distortion_center, stretch_matrix=None):
        """
        Initialize with MATLAB fisheyeIntrinsics parameters
        
        Args:
            mapping_coeffs: [a0, a2, a3, a4] polynomial coefficients
            image_size: [rows, cols] 
            distortion_center: [cx, cy] in pixels
            stretch_matrix: 2x2 transformation matrix (default: identity)
        """
        self.a0, self.a2, self.a3, self.a4 = mapping_coeffs
        self.image_height, self.image_width = image_size
        self.cx, self.cy = distortion_center
        
        # Stretch matrix (affine transformation)
        if stretch_matrix is None:
            self.A = np.eye(2)
        else:
            self.A = np.array(stretch_matrix).reshape(2, 2)
        
        # Pre-compute undistortion mapping for efficiency
        self._create_undistortion_maps()
    
    def _theta_to_rho(self, theta):
        """Forward projection: angle to radius"""
        theta2 = theta * theta
        theta3 = theta2 * theta
        theta4 = theta2 * theta2
        return self.a0 + self.a2 * theta2 + self.a3 * theta3 + self.a4 * theta4
    
    def _rho_to_theta_vectorized(self, rho):
        """Inverse projection: radius to angle (vectorized Newton-Raphson)"""
        # Initial guess
        theta = rho / self.a0
        
        # Newton-Raphson iterations
        for _ in range(5):
            theta2 = theta * theta
            theta3 = theta2 * theta
            theta4 = theta2 * theta2
            
            f = self.a0 + self.a2 * theta2 + self.a3 * theta3 + self.a4 * theta4 - rho
            f_prime = 2 * self.a2 * theta + 3 * self.a3 * theta2 + 4 * self.a4 * theta3
            
            # Avoid division by very small numbers
            valid_mask = np.abs(f_prime) > 1e-10
            theta[valid_mask] = theta[valid_mask] - f[valid_mask] / f_prime[valid_mask]
            
            # Clamp to reasonable range for 180° fisheye
            theta = np.clip(theta, 0, np.pi/2)
        
        return theta
    
    def _create_undistortion_maps(self):
        """Pre-compute pixel mapping for undistortion"""
        # Create output image coordinates
        y_out, x_out = np.mgrid[0:self.image_height, 0:self.image_width]
        
        # Convert to normalized coordinates centered at distortion center
        x_norm = x_out - self.cx
        y_norm = y_out - self.cy
        
        # Apply inverse stretch matrix
        A_inv = np.linalg.inv(self.A)
        coords = np.stack([x_norm.ravel(), y_norm.ravel()])
        coords_sensor = A_inv @ coords
        x_sensor = coords_sensor[0].reshape(x_norm.shape)
        y_sensor = coords_sensor[1].reshape(y_norm.shape)
        
        # Calculate radius in sensor plane
        rho = np.sqrt(x_sensor**2 + y_sensor**2)
        
        # Calculate angle for each pixel
        theta = np.zeros_like(rho)
        mask = rho > 0
        theta[mask] = self._rho_to_theta_vectorized(rho[mask])
        
        # For undistorted (rectilinear) image, we use perspective projection
        # Choose focal length to preserve field of view
        # For 180° fisheye, we want to map θ=π/2 to image edge
        max_radius = min(self.cx, self.cy, self.image_width - self.cx, self.image_height - self.cy)
        f_rect = max_radius / np.tan(np.pi/2 * 0.8)  # Use 80% of full FOV to avoid extreme distortion
        
        # Calculate undistorted radius
        r_rect = f_rect * np.tan(theta)
        
        # Scale factor
        scale = np.zeros_like(rho)
        scale[mask] = r_rect[mask] / rho[mask]
        
        # Calculate source coordinates for remapping
        self.map_x = x_norm * scale + self.cx
        self.map_y = y_norm * scale + self.cy
        
        # Create OpenCV remap format
        self.map_x = self.map_x.astype(np.float32)
        self.map_y = self.map_y.astype(np.float32)
    
    def undistort_frame(self, frame):
        """Undistort a single frame"""
        return cv2.remap(frame, self.map_x, self.map_y, 
                        interpolation=cv2.INTER_LINEAR,
                        borderMode=cv2.BORDER_CONSTANT,
                        borderValue=(0, 0, 0))

def process_video_stream(video_source=0, output_path=None):
    """
    Process video stream with fisheye undistortion
    
    Args:
        video_source: Camera index (0 for default) or video file path
        output_path: Optional path to save output video
    """
    # MATLAB parameters
    mapping_coeffs = [684.0465, -0.0017, 0, 0]
    image_size = [1080, 1920]
    distortion_center = [976.0474, 521.8287]
    stretch_matrix = [[1, 0], [0, 1]]
    
    # Initialize undistorter
    print("Initializing undistorter...")
    undistorter = ScaramuzzaFisheyeUndistorter(
        mapping_coeffs, image_size, distortion_center, stretch_matrix
    )
    print("Undistorter initialized successfully")
    
    # Open video capture
    cap = cv2.VideoCapture(video_source)
    if not cap.isOpened():
        print("Error: Could not open video source")
        return
    
    # Get video properties
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    print(f"Video properties: {width}x{height} @ {fps} fps")
    
    # Setup video writer if output path specified
    writer = None
    if output_path:
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
    
    print("Press 'q' to quit, 's' to save current frame, 'p' to toggle preview mode")
    frame_count = 0
    show_preview = True
    
    while True:
        ret, frame = cap.read()
        if not ret:
            print("End of stream")
            break
        
        # Check if frame size matches expected size
        if frame.shape[:2] != (height, width):
            print(f"Warning: Frame size {frame.shape[:2]} doesn't match expected {(height, width)}")
            frame = cv2.resize(frame, (width, height))
        
        # Undistort frame
        start_time = time.time()
        undistorted = undistorter.undistort_frame(frame)
        process_time = time.time() - start_time
        
        if show_preview:
            # Display results
            # Resize for display if needed
            display_scale = 0.5
            frame_display = cv2.resize(frame, None, fx=display_scale, fy=display_scale)
            undistorted_display = cv2.resize(undistorted, None, fx=display_scale, fy=display_scale)
            
            # Add text info
            cv2.putText(undistorted_display, f"Frame: {frame_count} | Process time: {process_time*1000:.1f}ms", 
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            
            # Show side by side
            combined = np.hstack([frame_display, undistorted_display])
            cv2.imshow('Original (left) | Undistorted (right)', combined)
        
        # Write to output video
        if writer:
            writer.write(undistorted)
        
        # Handle key press
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('s'):
            cv2.imwrite(f'frame_{frame_count}_original.jpg', frame)
            cv2.imwrite(f'frame_{frame_count}_undistorted.jpg', undistorted)
            print(f"Saved frame {frame_count}")
        elif key == ord('p'):
            show_preview = not show_preview
            if not show_preview:
                cv2.destroyAllWindows()
            print(f"Preview mode: {'ON' if show_preview else 'OFF'}")
        
        frame_count += 1
        
        # Print progress every 100 frames
        if frame_count % 100 == 0:
            print(f"Processed {frame_count} frames...")
    
    # Cleanup
    cap.release()
    if writer:
        writer.release()
    cv2.destroyAllWindows()
    print(f"Total frames processed: {frame_count}")

# Alternative: Wide-angle preserving projection
class ScaramuzzaWideAngleProjection(ScaramuzzaFisheyeUndistorter):
    """Creates a projection that preserves more of the wide-angle view"""
    
    def _create_undistortion_maps(self):
        """Create stereographic or equidistant projection mapping"""
        # Create output image coordinates
        y_out, x_out = np.mgrid[0:self.image_height, 0:self.image_width]
        
        # Convert to normalized coordinates centered at image center
        x_norm = (x_out - self.image_width/2)
        y_norm = (y_out - self.image_height/2)
        
        # Calculate desired angle for each output pixel (equidistant projection)
        # Map the full image to 160 degrees FOV (slightly less than full 180 to avoid edges)
        max_fov = 160 * np.pi / 180
        r_out = np.sqrt(x_norm**2 + y_norm**2)
        max_r_out = min(self.image_width/2, self.image_height/2)
        
        # Equidistant projection: radius proportional to angle
        theta = r_out / max_r_out * (max_fov / 2)
        theta = np.clip(theta, 0, np.pi/2 * 0.95)  # Limit to 95% of max angle
        
        # Calculate source radius using forward model
        rho_src = self._theta_to_rho(theta)
        
        # Calculate scale factor
        scale = np.zeros_like(r_out)
        mask = r_out > 0
        scale[mask] = rho_src[mask] / r_out[mask]
        
        # Apply scale and shift to distortion center
        self.map_x = x_norm * scale + self.cx
        self.map_y = y_norm * scale + self.cy
        
        # Create OpenCV remap format
        self.map_x = self.map_x.astype(np.float32)
        self.map_y = self.map_y.astype(np.float32)

if __name__ == "__main__":
    # Example usage:
    # For webcam
    process_video_stream(video_source=0)
    
    # For video file with output
    # process_video_stream(video_source='input_fisheye.mp4', output_path='output_rectified.mp4')
    
    # For wide-angle preservation (uncomment to use):
    # undistorter = ScaramuzzaWideAngleProjection(
    #     mapping_coeffs=[684.0465, -0.0017, 0, 0],
    #     image_size=[1080, 1920],
    #     distortion_center=[976.0474, 521.8287]
    # )
    # # Then use undistorter.undistort_frame() in your video loop
