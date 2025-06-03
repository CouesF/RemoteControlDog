import cv2
import numpy as np
from typing import Tuple
import time
class OptimizedMatlabFisheyeUndistorter:
    def __init__(self, mapping_coeffs: list, image_size: Tuple[int, int], 
                 distortion_center: Tuple[float, float], stretch_matrix: np.ndarray = None,
                 output_fov: float = 120):
        """
        Optimized version with adjustable output field of view
        
        Args:
            output_fov: Desired field of view in output image (degrees)
        """
        self.a0, self.a2, self.a3, self.a4 = mapping_coeffs
        self.height, self.width = image_size
        self.cx, self.cy = distortion_center
        self.stretch_matrix = stretch_matrix if stretch_matrix is not None else np.eye(2)
        self.output_fov = np.radians(output_fov)
        
        # Compute virtual focal length for desired FOV
        self.f_virtual = (self.width / 2) / np.tan(self.output_fov / 2)
        
        self._compute_optimized_maps()
    
    def _polynomial_inverse(self, rho: float, max_iter: int = 10) -> float:
        """
        Numerically invert the polynomial mapping to find theta given rho
        Uses Newton-Raphson method
        """
        if rho <= 0:
            return 0
        
        # Initial guess
        theta = rho / self.a0
        
        for _ in range(max_iter):
            # f(theta) = a0*theta + a2*theta^2 + a3*theta^3 + a4*theta^4 - rho
            f = self.a0 * theta + self.a2 * theta**2 + self.a3 * theta**3 + self.a4 * theta**4 - rho
            # f'(theta) = a0 + 2*a2*theta + 3*a3*theta^2 + 4*a4*theta^3
            f_prime = self.a0 + 2*self.a2*theta + 3*self.a3*theta**2 + 4*self.a4*theta**3
            
            if abs(f_prime) < 1e-10:
                break
                
            theta_new = theta - f / f_prime
            if abs(theta_new - theta) < 1e-6:
                break
            theta = theta_new
        
        return theta
    
    def _compute_optimized_maps(self):
        """Compute undistortion maps with inverse mapping"""
        # Create coordinate arrays
        x = np.arange(self.width) - self.cx
        y = np.arange(self.height) - self.cy
        xv, yv = np.meshgrid(x, y)
        
        # Apply inverse stretch matrix
        stretch_inv = np.linalg.inv(self.stretch_matrix)
        coords = np.stack([xv.ravel(), yv.ravel()])
        coords_corrected = stretch_inv @ coords
        xv_corrected = coords_corrected[0].reshape(self.height, self.width)
        yv_corrected = coords_corrected[1].reshape(self.height, self.width)
        
        # Calculate radius in distorted image
        rho = np.sqrt(xv_corrected**2 + yv_corrected**2)
        
        # Vectorized polynomial inverse (approximate)
        # For small distortions, we can use first-order approximation
        theta = rho / self.a0  # Initial approximation
        
        # Apply one Newton-Raphson iteration for better accuracy
        f = self.a0 * theta + self.a2 * theta**2 - rho
        f_prime = self.a0 + 2*self.a2*theta
        theta = theta - f / np.where(abs(f_prime) > 1e-10, f_prime, 1e-10)
        
        # Convert to undistorted coordinates
        r_undist = self.f_virtual * np.tan(theta)
        
        # Calculate undistorted coordinates
        scale = np.where(rho > 0, r_undist / rho, 1)
        self.map_x = (scale * xv + self.width/2).astype(np.float32)
        self.map_y = (scale * yv + self.height/2).astype(np.float32)
    
    def undistort_frame(self, frame: np.ndarray) -> np.ndarray:
        """Fast frame undistortion using pre-computed maps"""
        return cv2.remap(frame, self.map_x, self.map_y, cv2.INTER_LINEAR)

class MatlabFisheyeUndistorter:
    def __init__(self, mapping_coeffs: list, image_size: Tuple[int, int], 
                 distortion_center: Tuple[float, float], stretch_matrix: np.ndarray = None):
        """
        Initialize with MATLAB fisheye parameters
        
        Args:
            mapping_coeffs: [a0, a2, a3, a4] polynomial coefficients
            image_size: [height, width] 
            distortion_center: [cx, cy] in pixels
            stretch_matrix: 2x2 transformation matrix (default: identity)
        """
        self.a0, self.a2, self.a3, self.a4 = mapping_coeffs
        self.height, self.width = image_size
        self.cx, self.cy = distortion_center
        self.stretch_matrix = stretch_matrix if stretch_matrix is not None else np.eye(2)
        self.stretch_matrix_inv = np.linalg.inv(self.stretch_matrix)
        
        # Pre-compute undistortion maps
        self._compute_undistort_maps()
    
    def _compute_undistort_maps(self):
        """Pre-compute the undistortion mapping for real-time processing"""
        # Create meshgrid for undistorted image coordinates
        x = np.arange(self.width)
        y = np.arange(self.height)
        X, Y = np.meshgrid(x, y)
        
        # Initialize maps
        self.map_x = np.zeros((self.height, self.width), dtype=np.float32)
        self.map_y = np.zeros((self.height, self.width), dtype=np.float32)
        
        # For each pixel in the undistorted image, find corresponding distorted pixel
        for i in range(self.height):
            for j in range(self.width):
                # Normalized coordinates in undistorted image (assuming pinhole model)
                # Using a virtual focal length (can be adjusted based on desired FOV)
                f_virtual = self.a0  # Use a0 as approximate focal length
                x_norm = (j - self.width/2) / f_virtual
                y_norm = (i - self.height/2) / f_virtual
                
                # Calculate angle from optical axis
                r_norm = np.sqrt(x_norm**2 + y_norm**2)
                theta = np.arctan(r_norm)
                
                # Apply Scaramuzza model: ρ = a0 + a2*θ² + a3*θ³ + a4*θ⁴
                rho = self.a0 * theta + self.a2 * theta**2 + self.a3 * theta**3 + self.a4 * theta**4
                
                if r_norm > 0:
                    # Scale factor from normalized radius to distorted radius
                    scale = rho / (f_virtual * r_norm)
                    
                    # Distorted coordinates relative to image center
                    x_dist_centered = scale * (j - self.width/2)
                    y_dist_centered = scale * (i - self.height/2)
                    
                    # Apply stretch matrix
                    dist_point = self.stretch_matrix @ np.array([x_dist_centered, y_dist_centered])
                    
                    # Convert to absolute pixel coordinates
                    x_dist = dist_point[0] + self.cx
                    y_dist = dist_point[1] + self.cy
                else:
                    # Center point
                    x_dist = self.cx
                    y_dist = self.cy
                
                self.map_x[i, j] = x_dist
                self.map_y[i, j] = y_dist
    
    def undistort_frame(self, frame: np.ndarray) -> np.ndarray:
        """
        Undistort a single frame using pre-computed maps
        
        Args:
            frame: Input distorted frame
            
        Returns:
            Undistorted frame
        """
        return cv2.remap(frame, self.map_x, self.map_y, cv2.INTER_LINEAR)

def process_video_stream(video_source=0):
    """
    Process video stream and display undistorted output
    
    Args:
        video_source: Camera index (0 for default camera) or video file path
    """
    # Initialize MATLAB fisheye parameters
    mapping_coeffs = [684.0465, -0.0017, 0, 0]
    image_size = (1080, 1920)
    distortion_center = (976.0474, 521.8287)
    stretch_matrix = np.array([[1, 0], [0, 1]])
    
    # Create undistorter
    undistorter = MatlabFisheyeUndistorter(
        mapping_coeffs, image_size, distortion_center, stretch_matrix
    )
    
    # Open video capture
    cap = cv2.VideoCapture(video_source)
    
    # Set resolution if using camera
    if isinstance(video_source, int):
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
    
    print("Press 'q' to quit, 's' to save current frame")
    
    frame_count = 0
    start_time = time.time()
    
    while True:
        ret, frame = cap.read()
        if not ret:
            print("Failed to read frame")
            break
        
        # Ensure frame matches expected size
        if frame.shape[:2] != (1080, 1920):
            frame = cv2.resize(frame, (1920, 1080))
        
        # Undistort frame
        undistorted = undistorter.undistort_frame(frame)
        
        # Calculate FPS
        frame_count += 1
        if frame_count % 30 == 0:
            elapsed = time.time() - start_time
            fps = frame_count / elapsed
            print(f"FPS: {fps:.2f}")
        
        # Display results side by side
        display_width = 960  # Half of original width for display
        display_height = 540
        
        frame_display = cv2.resize(frame, (display_width, display_height))
        undistorted_display = cv2.resize(undistorted, (display_width, display_height))
        
        # Add labels
        cv2.putText(frame_display, "Original", (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.putText(undistorted_display, "Undistorted", (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        
        # Concatenate for side-by-side display
        combined = np.hstack([frame_display, undistorted_display])
        cv2.imshow("Fisheye Undistortion", combined)
        
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('s'):
            # Save current frames
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            cv2.imwrite(f"original_{timestamp}.jpg", frame)
            cv2.imwrite(f"undistorted_{timestamp}.jpg", undistorted)
            print(f"Saved frames with timestamp {timestamp}")
    
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    # Use camera index 0 for default camera, or provide a video file path
    process_video_stream(0)
