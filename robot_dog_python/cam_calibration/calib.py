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

    参数:
    image_folder_path (str): 包含棋盘格图像的文件夹路径。
    output_folder_path (str): 存储去畸变图像的文件夹路径。
    checkerboard_pattern (tuple): 棋盘格的内角点数量 (列数, 行数)。
                                  例如 (12, 9) 表示 12 列内角点, 9 行内角点。
    square_size_mm (float): 棋盘格每个格子的边长 (单位: 毫米)。

    返回:
    tuple: (K, D) 或 (None, None)
           K (numpy.ndarray): 相机内参矩阵 (3x3)。
           D (numpy.ndarray): 相机畸变系数 (4x1 for fisheye: k1, k2, k3, k4)。
           如果标定失败，则返回 (None, None)。
    """

    print(f"开始标定过程...")
    print(f"棋盘格内角点数量 (列, 行): {checkerboard_pattern}")
    print(f"棋盘格方格边长: {square_size_mm} mm")

    # 1. 准备对象点 (3D 世界坐标点)
    # 例如：(0,0,0), (1*square_size,0,0), ..., ((cols-1)*square_size, (rows-1)*square_size, 0)
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

        # 查找棋盘格角点
        # flags for findChessboardCorners:
        # cv2.CALIB_CB_ADAPTIVE_THRESH: Use adaptive thresholding.
        # cv2.CALIB_CB_FAST_CHECK: Run a fast check on the image and return quickly if no chessboard is found.
        # cv2.CALIB_CB_NORMALIZE_IMAGE: Normalize the image gamma before applying fixed or adaptive thresholding.
        # ret, corners = cv2.findChessboardCorners(
        #     gray, 
        #     checkerboard_pattern, 
        #     cv2.CALIB_CB_ADAPTIVE_THRESH  + cv2.CALIB_CB_NORMALIZE_IMAGE
        # )

        # 尝试 cv2.findChessboardCornersSB
        flags_sb = cv2.CALIB_CB_NORMALIZE_IMAGE | cv2.CALIB_CB_EXHAUSTIVE | cv2.CALIB_CB_ACCURACY
        # 或者更简单的 flags_sb = cv2.CALIB_CB_NORMALIZE_IMAGE
        ret, corners = cv2.findChessboardCorners(
            gray,
            checkerboard_pattern,
            cv2.CALIB_CB_ADAPTIVE_THRESH
            | cv2.CALIB_CB_NORMALIZE_IMAGE
            | cv2.CALIB_CB_FILTER_QUADS
        )

        if not ret:
            print(f"  警告: {fname} 无角点")
            continue

        # 亚像素精炼
        cv2.cornerSubPix(gray, corners, (11,11), (-1,-1),
                        (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001))

        # 简单过滤：第一个角点不应该正好落在 (0,0) 或者靠太近
        x0, y0 = corners[0,0]
        if x0<1 or y0<1:
            print(f"  跳过: {fname} 第一个角点位置太离谱 ({x0:.1f},{y0:.1f})")
            continue

        objpoints.append(objp)      # 之前创建的世界坐标
        imgpoints.append(corners)   # 精炼后的像素坐标

        # (可选) 绘制并显示角点，用于调试
        # cv2.drawChessboardCorners(img, checkerboard_pattern, corners_subpix, ret)
        # cv2.imshow('检测到的角点', cv2.resize(img, (img.shape[1]//2, img.shape[0]//2)))
        # cv2.waitKey(50)


    # cv2.destroyAllWindows()

    if not objpoints or not imgpoints:
        print("错误: 没有足够的角点数据进行标定。请确保：")
        print("  1. 棋盘格在图像中清晰可见。")
        print(f"  2. `checkerboard_pattern` ({checkerboard_pattern}) 设置正确。")
        print("  3. 有足够数量的图像成功检测到角点。")
        return None, None
    
    if len(objpoints) < 3: # 至少需要几张不同视角的图像
        print(f"警告: 只有 {len(objpoints)} 张图像成功检测到角点，标定结果可能不准确。建议使用更多图像。")


    print(f"\n使用 {len(objpoints)} 张图像进行标定...")

    # 4. 相机标定
    # K = np.zeros((3, 3))  # 初始化相机内参矩阵
    # D = np.zeros((4, 1))  # 初始化畸变系数 (k1, k2, k3, k4 for fisheye)
    # image_size = (1920,1080)
    # 1) 给一个合理的初始内参猜测
    K = np.eye(3, dtype=np.float64)
    # 初始 focal length 猜成图像宽度的 0.8 倍
    K[0, 0] = K[1, 1] = 0.8 * image_size[0]
    # 主点猜成图像中心
    K[0, 2] = image_size[0] / 2
    K[1, 2] = image_size[1] / 2

    # 2) 畸变系数初始为 0
    D = np.zeros((4, 1), dtype=np.float64)
    
    # rvecs 和 tvecs 用于存储每张图像的旋转和平移向量，标定函数会填充它们
    rvecs = [np.zeros((1, 1, 3), dtype=np.float64) for _ in range(len(objpoints))]
    tvecs = [np.zeros((1, 1, 3), dtype=np.float64) for _ in range(len(objpoints))]

    # 标定迭代的终止条件
    criteria_calib = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 1e-6)

    # 鱼眼相机标定标志
    # CALIB_RECOMPUTE_EXTRINSIC: 每次迭代后重新计算外参。
    # CALIB_CHECK_COND: 检查条件数。如果过高，可能标定不稳定。
    # CALIB_FIX_SKEW: 将倾斜因子(alpha)固定为0。
    calibration_flags = (
            cv2.fisheye.CALIB_RECOMPUTE_EXTRINSIC |
            cv2.fisheye.CALIB_FIX_SKEW |
            cv2.fisheye.CALIB_USE_INTRINSIC_GUESS
            )

    try:
        rms, K, D, rvecs, tvecs = cv2.fisheye.calibrate(
            objpoints,
            imgpoints,
            image_size, # (width, height)
            K,
            D,
            rvecs,
            tvecs,
            calibration_flags,
            criteria_calib
        )
    except cv2.error as e:
        print(f"OpenCV 标定错误: {e}")
        print("标定失败。请检查输入图像和参数。")
        return None, None

    print("\n标定完成。")
    print("-----------------------------------------------------")
    print(f"RMS 重投影误差: {rms}")
    print("相机内参矩阵 K:")
    print(K)
    print("\n畸变系数 D (k1, k2, k3, k4):")
    print(D)
    print("-----------------------------------------------------")

    # 5. 创建输出文件夹
    if not os.path.exists(output_folder_path):
        try:
            os.makedirs(output_folder_path)
            print(f"已创建输出文件夹: {output_folder_path}")
        except OSError as e:
            print(f"错误: 无法创建输出文件夹 '{output_folder_path}': {e}")
            return K, D # 至少返回标定参数

    # 6. 校正图像并保存
    print(f"\n开始对图像进行去畸变处理并保存到 '{output_folder_path}'...")
    
    # 用于去畸变的新的相机内参矩阵。这里使用标定得到的 K，
    # 也可以使用 cv2.fisheye.estimateNewCameraMatrixForUndistortRectify 调整 Knew 以控制视场
    # 例如: new_K = cv2.fisheye.estimateNewCameraMatrixForUndistortRectify(K, D, image_size, np.eye(3), balance=0.5)
    # balance=0.0: 保留所有像素, 可能有黑边。balance=1.0: 裁剪无效像素, 丢失部分边缘。
    # 为简单起见，这里直接使用 K 作为 Knew，这意味着尝试保留原始视场。
    K_new = K 
    
    for i, fname in enumerate(image_files):
        img = cv2.imread(fname)
        if img is None:
            continue # 前面已经处理过读取失败的情况

        # 计算去畸变和校正的映射表
        # R 通常是单位矩阵 np.eye(3) 如果不需要校正旋转
        # P 是新的相机矩阵，这里使用 K_new
        map1, map2 = cv2.fisheye.initUndistortRectifyMap(
            K, D, np.eye(3), K_new, image_size, cv2.CV_16SC2
        )
        
        # 应用映射表进行重映射
        undistorted_img = cv2.remap(
            img, map1, map2, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT
        )

        # 或者，使用更简单的函数（但控制较少）:
        # undistorted_img = cv2.fisheye.undistortImage(img, K, D, Knew=K_new)

        base_name = os.path.basename(fname)
        name, ext = os.path.splitext(base_name)
        undistorted_filename = os.path.join(output_folder_path, f"{name}_undistorted{ext}")
        
        try:
            cv2.imwrite(undistorted_filename, undistorted_img)
            if (i+1) % 10 == 0 or (i+1) == len(image_files) : # 每10张或最后一张时打印
                 print(f"  已保存去畸变图像 ({i+1}/{len(image_files)}): {undistorted_filename}")
        except Exception as e:
            print(f"错误: 无法保存图像 {undistorted_filename}: {e}")
            
    print("所有图像处理完毕。")
    return K, D


if __name__ == '__main__':
    # --- 用户配置 ---
    # 1. 输入包含棋盘格图片的文件夹路径
    #    请确保路径正确，例如: "C:/Users/YourUser/Desktop/chessboard_images" (Windows)
    #    或 "/home/youruser/chessboard_images" (Linux/Mac)
    # input_image_folder = input("请输入包含棋盘格图片的文件夹路径: ").strip()
    input_image_folder = "/Users/couesfang/我的云端硬盘/25机器狗户外研究/05软件系统/RemoteControlDog/rd_robot/cam_calibration/180cam_images"
    # 2. 输出存储去畸变图片的文件夹路径
    #    例如: "C:/Users/YourUser/Desktop/undistorted_images"
    # output_undistorted_folder = input("请输入用于存储去畸变图片的文件夹路径: ").strip()
    output_undistorted_folder = "/Users/couesfang/我的云端硬盘/25机器狗户外研究/05软件系统/RemoteControlDog/rd_robot/cam_calibration/180calib_images"
    # 3. 棋盘格参数 (重要!)
    #    (列内角点数, 行内角点数)
    #    您描述的是 "12*9"。这通常指内角点数量。
    #    如果您的棋盘格是 12x9 个 *格子*，则内角点是 (12-1, 9-1) = (11, 8)。
    #    请根据您的实际棋盘格调整。
    CHESSBOARD_COLS = 11  # 棋盘格每行的内角点数 (宽度方向)
    CHESSBOARD_ROWS = 8   # 棋盘格每列的内角点数 (高度方向)
    PATTERN_SIZE = (CHESSBOARD_COLS, CHESSBOARD_ROWS)

    # 4. 棋盘格每个方格的边长 (单位：毫米)
    SQUARE_EDGE_LENGTH_MM = 3.0

    # --- 执行标定和去畸变 ---
    if not os.path.isdir(input_image_folder):
        print(f"错误: 输入的图像文件夹路径无效或不存在: {input_image_folder}")
    else:
        K_matrix, D_coeffs = calibrate_and_undistort_fisheye(
            input_image_folder,
            output_undistorted_folder,
            checkerboard_pattern=PATTERN_SIZE,
            square_size_mm=SQUARE_EDGE_LENGTH_MM
        )

        if K_matrix is not None and D_coeffs is not None:
            print("\n--- 最终相机参数 ---")
            print("相机内参矩阵 K:")
            print(K_matrix)
            print("\n畸变系数 D (k1, k2, k3, k4):")
            print(D_coeffs)
            print(f"\n去畸变后的图像已保存到: {output_undistorted_folder}")
        else:
            print("\n标定或去畸变过程失败。请检查上述错误信息。")