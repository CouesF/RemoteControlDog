import cv2
import numpy as np
import os
import glob

def calibrate_and_undistort_fisheye(image_folder_path, 
                                    output_folder_path, 
                                    checkerboard_pattern=(12, 9), 
                                    square_size_mm=3.0):
    """
    标定鱼眼相机并对图像进行去畸变处理。
    把识别不到棋盘格的图片删掉。

    参数:
    image_folder_path (str): 包含棋盘格图像的文件夹路径。
    output_folder_path (str): 存储去畸变图像的文件夹路径。
    checkerboard_pattern (tuple): 棋盘格的内角点数量 (列数, 行数)。
    square_size_mm (float): 棋盘格每个格子的边长 (单位: 毫米)。

    返回:
    tuple: (K, D) 或 (None, None)
    """
    print(f"开始标定过程...")
    print(f"棋盘格内角点数量 (列, 行): {checkerboard_pattern}")
    print(f"棋盘格方格边长: {square_size_mm} mm")

    # 1. 准备对象点 (3D 世界坐标点)
    objp = np.zeros((1, checkerboard_pattern[0] * checkerboard_pattern[1], 3), np.float32)
    objp[0, :, :2] = np.mgrid[0:checkerboard_pattern[0], 0:checkerboard_pattern[1]].T.reshape(-1, 2)
    objp = objp * square_size_mm

    # 2. 存储检测到的对象点和图像点
    objpoints = []  # 存储3D世界坐标点
    imgpoints = []  # 存储2D图像平面点
    
    image_size = None # 用于存储图像尺寸 (width, height)

    # 3. 加载图像并查找角点
    supported_formats = ('*.jpg', '*.jpeg', '*.png', '*.bmp', '*.tif', '*.tiff')
    image_files = []
    for fmt in supported_formats:
        image_files.extend(glob.glob(os.path.join(image_folder_path, fmt)))
    
    if not image_files:
        print(f"错误: 在路径 '{image_folder_path}' 中没有找到支持的图像文件。")
        print(f"支持的格式: {', '.join(supported_formats)}")
        return None, None

    print(f"找到 {len(image_files)} 张图像进行处理。")

    # 用于记录最终保留的文件名
    valid_image_files = []

    for i, fname in enumerate(image_files):
        print(f"处理图像: {os.path.basename(fname)} ({i+1}/{len(image_files)})")
        img = cv2.imread(fname)
        if img is None:
            print(f"警告: 无法读取图像 {fname}，跳过此图像。")
            continue

        if image_size is None:
            image_size = (img.shape[1], img.shape[0]) # (width, height)
        elif image_size != (img.shape[1], img.shape[0]):
            print(f"警告: 图像 {fname} 的尺寸与之前的图像不同。所有图像应具有相同尺寸。跳过此图像。")
            continue
            
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        ret, corners = cv2.findChessboardCorners(
            gray, 
            checkerboard_pattern, 
            cv2.CALIB_CB_ADAPTIVE_THRESH | cv2.CALIB_CB_NORMALIZE_IMAGE | cv2.CALIB_CB_FILTER_QUADS
        )

        if ret:
            # 亚像素级角点精炼
            criteria_subpix = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
            corners_subpix = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria_subpix)
            
            # 简单验证：第一个角点不应该太靠近原点
            x0, y0 = corners_subpix[0, 0]
            if x0 < 1 or y0 < 1:
                print(f"  警告: 图像 {os.path.basename(fname)} 的第一个角点位置异常 ({x0:.1f}, {y0:.1f})，跳过此图像。")
                # 删除文件
                try:
                    os.remove(fname)
                    print(f"  已删除识别不到角点的图片: {fname}")
                except Exception as e:
                    print(f"  删除文件失败: {fname}，原因: {e}")
                continue
                
            objpoints.append(objp)
            imgpoints.append(corners_subpix)
            valid_image_files.append(fname)
            print(f"  在 {os.path.basename(fname)} 中成功检测到角点。")
        else:
            print(f"  警告: 在图像 {os.path.basename(fname)} 中未检测到棋盘格角点，删除该图片。")
            # 新增：删除无法识别棋盘格的图片
            try:
                os.remove(fname)
                print(f"  已删除识别不到角点的图片: {fname}")
            except Exception as e:
                print(f"  删除文件失败: {fname}，原因: {e}")

    cv2.destroyAllWindows()

    if not objpoints or not imgpoints:
        print("错误: 没有足够的角点数据进行标定。请确保：")
        print("  1. 棋盘格在图像中清晰可见。")
        print(f"  2. `checkerboard_pattern` ({checkerboard_pattern}) 设置正确。")
        print("  3. 有足够数量的图像成功检测到角点。")
        return None, None
    
    if len(objpoints) < 10:  # 建议至少10张图像
        print(f"警告: 只有 {len(objpoints)} 张图像成功检测到角点，建议使用至少10张以上图像以获得更好的标定结果。")

    print(f"\n使用 {len(objpoints)} 张图像进行标定...")
    print(f"图像尺寸: {image_size}")

    # 4. 相机标定
    K = np.eye(3, dtype=np.float64)
    focal_length_init = max(image_size[0], image_size[1]) / 100.0  # 对应约114度视场角
    K[0, 0] = focal_length_init
    K[1, 1] = focal_length_init
    K[0, 2] = image_size[0] / 2.0
    K[1, 2] = image_size[1] / 2.0

    print(f"初始焦距猜测: {focal_length_init}")
    print(f"初始主点猜测: ({K[0,2]}, {K[1,2]})")

    D = np.zeros((4, 1), dtype=np.float64)
    rvecs = [np.zeros((1, 1, 3), dtype=np.float64) for _ in range(len(objpoints))]
    tvecs = [np.zeros((1, 1, 3), dtype=np.float64) for _ in range(len(objpoints))]
    criteria_calib = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 1e-6)
    calibration_flags = (
        cv2.fisheye.CALIB_RECOMPUTE_EXTRINSIC |  
        cv2.fisheye.CALIB_FIX_SKEW |             
        cv2.fisheye.CALIB_USE_INTRINSIC_GUESS    
    )

    try:
        print("\n开始执行鱼眼相机标定...")
        rms, K_opt, D_opt, rvecs, tvecs = cv2.fisheye.calibrate(
            objpoints,
            imgpoints,
            image_size,
            K,
            D,
            rvecs,
            tvecs,
            calibration_flags,
            criteria_calib
        )
    except cv2.error as e:
        print(f"第一次标定尝试失败: {e}")
        print("尝试使用更保守的初始参数...")
        diag = np.sqrt(image_size[0]**2 + image_size[1]**2)
        focal_length_init = diag / np.pi  # 对应约90度视场角
        K[0, 0] = focal_length_init
        K[1, 1] = focal_length_init
        try:
            rms, K_opt, D_opt, rvecs, tvecs = cv2.fisheye.calibrate(
                objpoints,
                imgpoints,
                image_size,
                K,
                D,
                rvecs,
                tvecs,
                calibration_flags,
                criteria_calib
            )
        except cv2.error as e2:
            print(f"第二次标定尝试也失败: {e2}")
            print("标定失败。可能的原因：")
            print("1. 图像质量问题（模糊、过曝等）")
            print("2. 棋盘格拍摄角度过于单一")
            print("3. 棋盘格参数设置错误")
            return None, None

    print("\n标定完成！")
    print("-----------------------------------------------------")
    print(f"RMS 重投影误差: {rms:.4f} 像素")
    if rms > 1.0:
        print(f"警告: RMS误差较大（{rms:.4f} > 1.0），标定结果可能不够准确。")
    print("\n相机内参矩阵 K:")
    print(K_opt)
    print(f"\n焦距: fx = {K_opt[0,0]:.2f}, fy = {K_opt[1,1]:.2f}")
    print(f"主点: cx = {K_opt[0,2]:.2f}, cy = {K_opt[1,2]:.2f}")
    print("\n畸变系数 D (k1, k2, k3, k4):")
    print(D_opt.ravel())
    print("-----------------------------------------------------")

    # 5. 创建输出文件夹
    if not os.path.exists(output_folder_path):
        try:
            os.makedirs(output_folder_path)
            print(f"已创建输出文件夹: {output_folder_path}")
        except OSError as e:
            print(f"错误: 无法创建输出文件夹 '{output_folder_path}': {e}")
            return K_opt, D_opt

    # 6. 校正图像并保存
    print(f"\n开始对图像进行去畸变处理并保存到 '{output_folder_path}'...")
    balance = 0.5
    new_K = cv2.fisheye.estimateNewCameraMatrixForUndistortRectify(
        K_opt, D_opt, image_size, np.eye(3), balance=balance
    )
    map1, map2 = cv2.fisheye.initUndistortRectifyMap(
        K_opt, D_opt, np.eye(3), new_K, image_size, cv2.CV_16SC2
    )
    for i, fname in enumerate(valid_image_files):  # 只处理有效图像
        img = cv2.imread(fname)
        if img is None:
            continue
        undistorted_img = cv2.remap(
            img, map1, map2, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT
        )
        base_name = os.path.basename(fname)
        name, ext = os.path.splitext(base_name)
        undistorted_filename = os.path.join(output_folder_path, f"{name}_undistorted{ext}")
        try:
            cv2.imwrite(undistorted_filename, undistorted_img)
            if (i+1) % 10 == 0 or (i+1) == len(valid_image_files):
                print(f"  已保存去畸变图像 ({i+1}/{len(valid_image_files)}): {os.path.basename(undistorted_filename)}")
        except Exception as e:
            print(f"错误: 无法保存图像 {undistorted_filename}: {e}")
            
    print("所有图像处理完毕。")
    return K_opt, D_opt, image_size


if __name__ == '__main__':
    # --- 用户配置 ---
    input_image_folder = "/Users/couesfang/我的云端硬盘/25机器狗户外研究/05软件系统/RemoteControlDog/rd_robot/cam_calibration/180cam_images"
    output_undistorted_folder = "/Users/couesfang/我的云端硬盘/25机器狗户外研究/05软件系统/RemoteControlDog/rd_robot/cam_calibration/180calib_images"
    
    # 棋盘格参数
    CHESSBOARD_COLS = 11  # 棋盘格每行的内角点数
    CHESSBOARD_ROWS = 8   # 棋盘格每列的内角点数
    PATTERN_SIZE = (CHESSBOARD_COLS, CHESSBOARD_ROWS)
    
    # 棋盘格每个方格的边长 (单位：毫米)
    SQUARE_EDGE_LENGTH_MM = 3.0

    # --- 执行标定和去畸变 ---
    if not os.path.isdir(input_image_folder):
        print(f"错误: 输入的图像文件夹路径无效或不存在: {input_image_folder}")
    else:
        result = calibrate_and_undistort_fisheye(
            input_image_folder,
            output_undistorted_folder,
            checkerboard_pattern=PATTERN_SIZE,
            square_size_mm=SQUARE_EDGE_LENGTH_MM
        )
        if result is not None and len(result) == 3:
            K_matrix, D_coeffs, image_size = result
            print("\n--- 最终相机参数 ---")
            print("相机内参矩阵 K:")
            print(K_matrix)
            print("\n畸变系数 D (k1, k2, k3, k4):")
            print(D_coeffs)
            print(f"\n去畸变后的图像已保存到: {output_undistorted_folder}")
            
            # 保存标定结果到文件
            calibration_file = os.path.join(output_undistorted_folder, "calibration_results.npz")
            np.savez(calibration_file, K=K_matrix, D=D_coeffs, image_size=image_size)
            print(f"\n标定结果已保存到: {calibration_file}")
        else:
            print("\n标定或去畸变过程失败。请检查上述错误信息。")