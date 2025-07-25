import cv2
import numpy as np
import time
import math
import os
import glob

def create_scaramuzza_undistort_map(matlab_params, new_image_size, new_cam_fov_deg=100.0):
    """
    Creates undistortion maps for a Scaramuzza fisheye model.

    Args:
        matlab_params (dict): Dictionary containing Scaramuzza model parameters from MATLAB.
            Expected keys: 'mappingCoeffs', 'imageSize', 'distortionCenter', 'stretchMatrix'.
        new_image_size (tuple): (width, height) of the desired undistorted output image.
        new_cam_fov_deg (float): Desired horizontal field of view for the virtual pinhole camera in degrees.

    Returns:
        tuple: (map_x, map_y) for cv2.remap().
    """
    map_coeffs = matlab_params['mappingCoeffs']
    a0, a2, a3, a4 = map_coeffs[0], map_coeffs[1], map_coeffs[2], map_coeffs[3]
    
    # For user's case, a3 and a4 are 0, simplifying to quadratic.
    # If a3 or a4 were non-zero, a general polynomial solver (np.roots) would be needed per pixel.
    is_quadratic = abs(a3) < 1e-9 and abs(a4) < 1e-9

    img_size_orig = matlab_params['imageSize'] # [rows, cols]
    dist_center_orig = matlab_params['distortionCenter'] # [cx, cy] - cx is horiz, cy is vert
    stretch_matrix_orig = matlab_params['stretchMatrix']
    inv_stretch_matrix = np.linalg.inv(stretch_matrix_orig)

    w_new, h_new = new_image_size

    # Intrinsics for the new virtual pinhole camera
    fx_new = w_new / (2 * math.tan(math.radians(new_cam_fov_deg) / 2))
    fy_new = fx_new # Assuming square pixels for the virtual camera
    # Adjust fy_new if different aspect ratio for FoV is desired, e.g.
    # desired_vfov_rad = 2 * math.atan(math.tan(math.radians(new_cam_fov_deg) / 2) * (h_new / w_new))
    # fy_new = h_new / (2 * math.tan(desired_vfov_rad / 2))

    cx_new = w_new / 2.0
    cy_new = h_new / 2.0

    # Create meshgrid for destination image pixels
    u_dst, v_dst = np.meshgrid(np.arange(w_new), np.arange(h_new))
    u_dst = u_dst.astype(np.float32)
    v_dst = v_dst.astype(np.float32)

    # Convert destination pixels to normalized image coordinates on Z_virt=1 plane
    X_virt = (u_dst - cx_new) / fx_new
    Y_virt = (v_dst - cy_new) / fy_new
    Z_virt = np.ones_like(X_virt) # By definition for pinhole projection to Z=1 plane

    R_virt = np.sqrt(X_virt**2 + Y_virt**2)
    
    # Initialize maps
    map_x = np.full((h_new, w_new), -1.0, dtype=np.float32) # Using -1 for invalid
    map_y = np.full((h_new, w_new), -1.0, dtype=np.float32)

    # Solve for rho_s for each point
    # Equation: a4*rho_s^4 + a3*rho_s^3 + a2*rho_s^2 - (Z_virt/R_virt)*rho_s + a0 = 0
    # For the quadratic case (a3=0, a4=0):
    # a2*rho_s^2 - (Z_virt/R_virt)*rho_s + a0 = 0
    
    # Avoid division by zero for R_virt at the center of the virtual image
    # At this point (optical axis), X_virt=0, Y_virt=0, so R_virt=0.
    # For this ray, rho_s on the sensor plane should also be 0.
    
    # Numerically stable calculation for B_quad term (Z_virt / R_virt)
    # Let inv_R_virt = Z_virt / R_virt. When R_virt -> 0, this blows up.
    # However, we will handle R_virt == 0 as a special case where rho_s = 0.
    
    rho_s_all = np.full_like(R_virt, -1.0, dtype=np.float32) # Store calculated rho_s, init with invalid

    # --- Handle points not on the optical axis of the virtual camera ---
    mask_not_center = R_virt > 1e-6 # Epsilon to avoid division by zero
    
    if is_quadratic:
        A_quad = a2
        # B_quad = -Z_virt[mask_not_center] / R_virt[mask_not_center] # Z_virt is 1
        B_quad = -1.0 / R_virt[mask_not_center]
        C_quad = a0

        delta = B_quad**2 - 4*A_quad*C_quad
        
        mask_real_roots = delta >= 0
        
        # Calculate roots where they are real
        sqrt_delta = np.sqrt(delta[mask_real_roots])
        A_quad_masked = A_quad # Since A_quad is scalar
        B_quad_masked = B_quad[mask_real_roots]

        # Potential for A_quad to be zero if a2 is zero
        if abs(A_quad_masked) < 1e-9: # Linear equation: B_quad * rho_s + C_quad = 0
            rho_s_sol = -C_quad / B_quad_masked
        else:
            rho_s1_cand = (-B_quad_masked + sqrt_delta) / (2*A_quad_masked)
            rho_s2_cand = (-B_quad_masked - sqrt_delta) / (2*A_quad_masked)

            # Select the smallest positive real root
            # Create arrays full of infinity, then update with valid positive roots
            rho_s1_pos = np.where(rho_s1_cand >= 0, rho_s1_cand, np.inf)
            rho_s2_pos = np.where(rho_s2_cand >= 0, rho_s2_cand, np.inf)
            rho_s_sol = np.minimum(rho_s1_pos, rho_s2_pos)
            rho_s_sol[rho_s_sol == np.inf] = -1 # Mark if no positive root found

        # Place solutions back into the main rho_s_all array
        indices_real_roots = np.where(mask_not_center)
        valid_indices_within_not_center = tuple(idx[mask_real_roots] for idx in indices_real_roots)
        rho_s_all[valid_indices_within_not_center] = rho_s_sol

    else: # General polynomial solver (slower, per pixel)
        print("Using general polynomial solver (slower). Consider simplifying if a3,a4 are near zero.")
        for r_idx in range(h_new):
            for c_idx in range(w_new):
                if not mask_not_center[r_idx, c_idx]: continue # Skip center, handled later

                # poly_coeffs for: a4*x^4 + a3*x^3 + a2*x^2 + (-Z/R)*x + a0 = 0
                poly_c = [
                    a4, a3, a2,
                    -Z_virt[r_idx, c_idx] / R_virt[r_idx, c_idx],
                    a0
                ]
                roots = np.roots(poly_c)
                
                min_positive_rho_s = float('inf')
                for root_val in roots:
                    if np.isreal(root_val):
                        real_root = np.real(root_val)
                        if real_root >= 0 and real_root < min_positive_rho_s:
                            min_positive_rho_s = real_root
                
                if min_positive_rho_s != float('inf'):
                    rho_s_all[r_idx, c_idx] = min_positive_rho_s
    
    # --- Handle the optical axis of the virtual camera (R_virt approx 0) ---
    mask_center = R_virt <= 1e-6
    rho_s_all[mask_center] = 0.0 # For rays along optical axis, rho_s is 0

    # --- Calculate sensor plane coordinates (x_s, y_s) and then map to source pixels ---
    # Valid rho_s values are >= 0
    valid_rho_s_mask = rho_s_all >= 0
    
    # For points where rho_s is valid and R_virt > epsilon (not center)
    # x_s = X_virt * (rho_s / R_virt)
    # y_s = Y_virt * (rho_s / R_virt)
    # Need to combine valid_rho_s_mask and mask_not_center for the scale factor
    
    compute_xy_s_mask = np.logical_and(valid_rho_s_mask, mask_not_center)
    
    scale_factor = np.zeros_like(R_virt) # Initialize scale factor
    scale_factor[compute_xy_s_mask] = rho_s_all[compute_xy_s_mask] / R_virt[compute_xy_s_mask]

    x_s = X_virt * scale_factor
    y_s = Y_virt * scale_factor
    # For center points (mask_center), X_virt, Y_virt are 0, so x_s, y_s become 0, which is correct.
    # rho_s_all[mask_center] is 0. If R_virt[mask_center] is also 0, scale_factor needs careful def.
    # However, since rho_s is 0 at center, x_s and y_s must be 0. Our X_virt, Y_virt are 0 there, so it works.

    # Transform sensor coords (x_s, y_s) to pixel coords in original distorted image
    # pixel_coords_centered = inv_stretch_matrix @ [x_s_flat; y_s_flat]
    # This is done for all points, valid or not initially; invalid will remain -1 in map_x/y.
    
    # Stack x_s, y_s for matrix multiplication
    sensor_coords_stacked = np.stack((x_s.ravel(), y_s.ravel()), axis=0) # Shape (2, h_new*w_new)
    pixel_coords_centered_flat = inv_stretch_matrix @ sensor_coords_stacked # Shape (2, h_new*w_new)
    
    u_src_centered = pixel_coords_centered_flat[0, :].reshape(h_new, w_new)
    v_src_centered = pixel_coords_centered_flat[1, :].reshape(h_new, w_new)

    u_src = u_src_centered + dist_center_orig[0] # dist_center_orig[0] is cx
    v_src = v_src_centered + dist_center_orig[1] # dist_center_orig[1] is cy

    # Populate maps only for valid rho_s calculations
    map_x[valid_rho_s_mask] = u_src[valid_rho_s_mask]
    map_y[valid_rho_s_mask] = v_src[valid_rho_s_mask]
    
    print(f"Map generation: {np.sum(valid_rho_s_mask)} valid points out of {h_new*w_new}")
    
    # Check if the source pixels are within original image bounds
    # This is actually handled by cv2.remap border mode, but good for diagnostics
    # valid_map_pixels = (map_x >= 0) & (map_x < img_size_orig[1]) & \
    #                    (map_y >= 0) & (map_y < img_size_orig[0])
    # print(f"Map generation: {np.sum(valid_map_pixels)} map to valid source pixels.")

    return map_x.astype(np.float32), map_y.astype(np.float32)


# --- Main execution ---
if __name__ == "__main__":
    # Add these imports at the top of the file
    # import glob
    # import os

    # MATLAB parameters from user
    matlab_params_dict = {
        'mappingCoeffs': np.array([450,-0.012213581038145,0.0,0.0]), # a0, a2, a3, a4
        'imageSize': np.array([480, 640]),  # rows, cols
        'distortionCenter': np.array([328.3694,233.672943]), # cx (horizontal), cy (vertical)
        'stretchMatrix': np.array([[1.0, 0.0], [0.0, 1.0]])
    }

    orig_h, orig_w = matlab_params_dict['imageSize']
    # Desired output size (can be same or different)
    new_w, new_h = 1280, 720 # Example of resizing

    print("Generating undistortion maps...")
    start_time = time.time()
    map_x, map_y = create_scaramuzza_undistort_map(matlab_params_dict, (new_w, new_h), new_cam_fov_deg=110.0)
    end_time = time.time()
    print(f"Map generation took {end_time - start_time:.2f} seconds.")

    # --- NEW: Image Processing Logic ---
    # Define input and output folders
    input_folder = 'captures'
    output_folder = 'output_images'

    # Create output folder if it doesn't exist
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    # Get a list of all image files in the input folder
    # Supports jpg, jpeg, and png
    image_files = glob.glob(os.path.join(input_folder, '*.jpg')) + \
                  glob.glob(os.path.join(input_folder, '*.jpeg')) + \
                  glob.glob(os.path.join(input_folder, '*.png'))
    
    if not image_files:
        print(f"Error: No images found in '{input_folder}' directory.")
    else:
        print(f"Found {len(image_files)} images to process.")

    # Loop through each image file
    for image_path in image_files:
        # Read the distorted image
        frame = cv2.imread(image_path)
        if frame is None:
            print(f"Could not read image: {image_path}")
            continue

        # The undistortion map was created based on the original calibration size (orig_w, orig_h).
        # Resize the input image to this size before remapping.
        if frame.shape[1] != orig_w or frame.shape[0] != orig_h:
             frame_for_remap = cv2.resize(frame, (orig_w, orig_h))
        else:
             frame_for_remap = frame

        # Apply the undistortion map
        undistorted_frame = cv2.remap(frame_for_remap, map_x, map_y, 
                                      interpolation=cv2.INTER_LINEAR, 
                                      borderMode=cv2.BORDER_CONSTANT, 
                                      borderValue=(0,0,0))

        # Construct the output file path
        base_filename = os.path.basename(image_path)
        output_path = os.path.join(output_folder, 'undistorted_' + base_filename)

        # Save the undistorted image
        cv2.imwrite(output_path, undistorted_frame)
        print(f"Processed '{image_path}' -> Saved to '{output_path}'")

    print("Image processing complete.")