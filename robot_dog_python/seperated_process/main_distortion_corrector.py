import cv2
import numpy as np
import math
import time

class FisheyeCorrector:
    """
    A class to handle Scaramuzza model fisheye distortion correction.
    It pre-computes the remap matrices for efficient, real-time application.
    """
    map_x: np.ndarray | None
    map_y: np.ndarray | None
    matlab_params: dict
    undistorted_size: tuple
    calibration_input_size: tuple

    def __init__(self, camera_config: dict):
        """
        Initializes the corrector, generates maps, and sets the flip method.
        """
        print("Initializing Fisheye Corrector...")
        self.matlab_params = camera_config['fisheye_params']
        self.undistorted_size = camera_config['undistorted_resolution']
        
        calib_size_rc = self.matlab_params['imageSize']
        self.calibration_input_size = (calib_size_rc[1], calib_size_rc[0])

        self.map_x: np.ndarray | None = None
        self.map_y: np.ndarray | None = None
        
        # Read the flip configuration from the camera settings
        self.flip_code = self._map_flip_method(camera_config.get("flip_method", "none"))

        start_time = time.time()
        self._generate_maps()
        end_time = time.time()
        print(f"Distortion map generation took {end_time - start_time:.2f} seconds.")

    def _map_flip_method(self, method_str: str) -> int | None:
        """Maps a readable string to an OpenCV flip code."""
        method_str = method_str.lower()
        if method_str == "vertical":
            # Flips the image upside down
            return 0
        elif method_str == "horizontal":
            # Flips the image like a mirror
            return 1
        elif method_str == "both":
            # Rotates the image 180 degrees
            return -1
        else:
            # "none" or any other value results in no flip
            return None

    # In distortion_corrector.py

    def correct(self, frame: np.ndarray) -> np.ndarray:
        """
        Applies distortion correction and then flips the frame, measuring each step.
        """
        # Overall timer for the whole correction process
        # t_start_total = time.time()

        # --- 1. Measure optional resize ---
        # resize_ms = 0.0
        # t_start_resize = time.time()
        # Ensure input frame matches the size used for calibration
        if frame.shape[1] != self.calibration_input_size[0] or frame.shape[0] != self.calibration_input_size[1]:
            frame = cv2.resize(frame, self.calibration_input_size, interpolation=cv2.INTER_AREA)
            # resize_ms = (time.time() - t_start_resize) * 1000

        # --- 2. Measure core undistortion ---
        # t_start_remap = time.time()
        corrected_frame = cv2.remap(frame, self.map_x, self.map_y,
                                    interpolation=cv2.INTER_LINEAR,
                                    borderMode=cv2.BORDER_CONSTANT,
                                    borderValue=(0, 0, 0))
        # remap_ms = (time.time() - t_start_remap) * 1000

        # --- 3. Measure optional flip ---
        # flip_ms = 0.0
        if self.flip_code is not None:
            t_start_flip = time.time()
            corrected_frame = cv2.flip(corrected_frame, self.flip_code)
            # flip_ms = (time.time() - t_start_flip) * 1000

        # total_ms = (time.time() - t_start_total) * 1000
        '''
        # --- 4. Print the timing results to the terminal ---
        print(
            f"Correction Timings (ms) - "
            f"Total: {total_ms:.2f} | "
            f"Remap: {remap_ms:.2f} | "
            f"Resize: {resize_ms:.2f} | "
            f"Flip: {flip_ms:.2f}"
        )
        '''
        return corrected_frame

    def _generate_maps(self):
        """Generates the x and y maps for cv2.remap() based on Scaramuzza model."""
        # This function is a direct adaptation of create_scaramuzza_undistort_map
        map_coeffs = self.matlab_params['mappingCoeffs']
        a0, a2 = map_coeffs[0], map_coeffs[1] # Simplified for the quadratic case

        inv_stretch_matrix = np.linalg.inv(self.matlab_params['stretchMatrix'])
        dist_center_orig = self.matlab_params['distortionCenter']
        
        w_new, h_new = self.undistorted_size
        
        # Virtual pinhole camera intrinsics
        fov_deg = self.matlab_params.get('undistorted_fov_deg', 110.0)
        fx_new = w_new / (2 * math.tan(math.radians(fov_deg) / 2))
        fy_new = fx_new
        cx_new = w_new / 2.0
        cy_new = h_new / 2.0

        u_dst, v_dst = np.meshgrid(np.arange(w_new), np.arange(h_new))

        # Normalized coords in virtual camera
        X_virt = (u_dst - cx_new) / fx_new
        Y_virt = (v_dst - cy_new) / fy_new
        R_virt = np.sqrt(X_virt**2 + Y_virt**2)

        rho_s_all = np.full_like(R_virt, -1.0, dtype=np.float32)
        mask_not_center = R_virt > 1e-6

        # Solve quadratic equation: a2*rho_s^2 - (1/R_virt)*rho_s + a0 = 0
        A_quad = a2
        B_quad = -1.0 / R_virt[mask_not_center]
        C_quad = a0
        delta = B_quad**2 - 4 * A_quad * C_quad
        mask_real_roots = delta >= 0

        sqrt_delta = np.sqrt(delta[mask_real_roots])
        rho_s1 = (-B_quad[mask_real_roots] + sqrt_delta) / (2 * A_quad)
        rho_s2 = (-B_quad[mask_real_roots] - sqrt_delta) / (2 * A_quad)
        
        rho_s1_pos = np.where(rho_s1 >= 0, rho_s1, np.inf)
        rho_s2_pos = np.where(rho_s2 >= 0, rho_s2, np.inf)
        rho_s_sol = np.minimum(rho_s1_pos, rho_s2_pos)
        rho_s_sol[rho_s_sol == np.inf] = -1

        indices_real_roots = np.where(mask_not_center)
        valid_indices = tuple(idx[mask_real_roots] for idx in indices_real_roots)
        rho_s_all[valid_indices] = rho_s_sol
        rho_s_all[R_virt <= 1e-6] = 0.0

        valid_rho_s_mask = rho_s_all >= 0
        compute_xy_s_mask = np.logical_and(valid_rho_s_mask, mask_not_center)
        
        scale_factor = np.zeros_like(R_virt)
        scale_factor[compute_xy_s_mask] = rho_s_all[compute_xy_s_mask] / R_virt[compute_xy_s_mask]

        x_s = X_virt * scale_factor
        y_s = Y_virt * scale_factor
        
        sensor_coords = np.stack((x_s.ravel(), y_s.ravel()), axis=0)
        pixel_coords_centered = inv_stretch_matrix @ sensor_coords
        
        u_src = pixel_coords_centered[0, :].reshape(h_new, w_new) + dist_center_orig[0]
        v_src = pixel_coords_centered[1, :].reshape(h_new, w_new) + dist_center_orig[1]
        
        self.map_x = np.full((h_new, w_new), -1.0, dtype=np.float32)
        self.map_y = np.full((h_new, w_new), -1.0, dtype=np.float32)

        self.map_x[valid_rho_s_mask] = u_src[valid_rho_s_mask]
        self.map_y[valid_rho_s_mask] = v_src[valid_rho_s_mask]