import cv2
import numpy as np
import os
import glob
import matplotlib.pyplot as plt
from scipy.optimize import least_squares


class ManualOCamCalibrator:
    """
    手动实现的OCam鱼眼相机标定
    完全不使用OpenCV的fisheye模块
    """
    def __init__(self, poly_order=5):
        self.poly_order = poly_order
        self.poly_coeffs = None
        self.inv_poly_coeffs = None
        self.center = None
        self.affine = np.array([1.0, 0.0, 0.0, 1.0])
        self.image_size = None
        
    def calibrate(self, objpoints, imgpoints, image_size):
        """
        手动实现OCam标定
        """
        self.image_size = image_size
        
        # 初始化中心点
        self.center = np.array([image_size[0]/2, image_size[1]/2])
        
        # 初始化多项式系数
        # 对于180度鱼眼，初始焦距应该较小
        init_focal = min(image_size) * 0.3
        self.poly_coeffs = np.zeros(self.poly_order)
        self.poly_coeffs[0] = init_focal
        
        # 准备所有数据点
        all_obj_pts = []
        all_img_pts = []
        image_indices = []
        
        for i, (obj_pts, img_pts) in enumerate(zip(objpoints, imgpoints)):
            all_obj_pts.extend(obj_pts)
            all_img_pts.extend(img_pts)
            image_indices.extend([i] * len(obj_pts))
            
        all_obj_pts = np.array(all_obj_pts)
        all_img_pts = np.array(all_img_pts)
        image_indices = np.array(image_indices)
        
        # 初始化每张图片的外参（简化：只估计平移）
        n_images = len(objpoints)
        translations = np.zeros((n_images, 3))
        for i in range(n_images):
            # 假设棋盘格在z=200mm处
            translations[i] = [0, 0, 200]
        
        # 构建优化参数
        # [cx, cy, a0, a1, ..., an-1, c, d, e, f, tx0, ty0, tz0, tx1, ty1, tz1, ...]
        initial_params = np.concatenate([
            self.center,                    # 2个参数
            self.poly_coeffs,              # poly_order个参数
            self.affine,                   # 4个参数
            translations.flatten()         # 3*n_images个参数
        ])
        
        print(f"开始优化，参数数量: {len(initial_params)}")
        
        # 执行优化
        result = least_squares(
            self._cost_function,
            initial_params,
            args=(all_obj_pts, all_img_pts, image_indices, n_images),
            method='lm',
            max_nfev=1000,
            verbose=2
        )
        
        # 提取优化结果
        self.center = result.x[:2]
        self.poly_coeffs = result.x[2:2+self.poly_order]
        self.affine = result.x[2+self.poly_order:6+self.poly_order]
        
        # 计算RMS误差
        residuals = result.fun
        rms_error = np.sqrt(np.mean(residuals**2))
        
        print(f"\n优化完成!")
        print(f"RMS误差: {rms_error:.3f} 像素")
        print(f"图像中心: {self.center}")
        print(f"多项式系数: {self.poly_coeffs}")
        print(f"仿射系数: {self.affine}")
        
        # 计算反向多项式系数（用于去畸变）
        self._compute_inverse_poly()
        
        return True
        
    def _cost_function(self, params, obj_pts, img_pts, image_indices, n_images):
        """
        计算重投影误差
        """
        # 解析参数
        cx, cy = params[:2]
        poly = params[2:2+self.poly_order]
        affine = params[2+self.poly_order:6+self.poly_order]
        
        # 解析每张图片的平移
        trans_start = 6 + self.poly_order
        translations = params[trans_start:].reshape(n_images, 3)
        
        errors = []
        
        for i in range(len(obj_pts)):
            # 获取对应的图片索引
            img_idx = image_indices[i]
            tx, ty, tz = translations[img_idx]
            
            # 3D点（假设棋盘格平面）
            X, Y = obj_pts[i, 0], obj_pts[i, 1]
            Z = tz  # 使用估计的深度
            
            # 投影到图像平面
            x_proj, y_proj = self._project_point(X + tx, Y + ty, Z, cx, cy, poly, affine)
            
            # 计算误差
            errors.append(x_proj - img_pts[i, 0])
            errors.append(y_proj - img_pts[i, 1])
            
        return np.array(errors)
        
    def _project_point(self, X, Y, Z, cx, cy, poly, affine):
        """
        将3D点投影到图像平面
        """
        # 计算入射角
        r_3d = np.sqrt(X**2 + Y**2)
        
        if Z <= 0:
            return cx, cy
            
        # 入射角theta
        theta = np.arctan2(r_3d, Z)
        
        # 应用多项式模型计算图像平面半径
        rho = poly[0]
        theta_i = theta
        for i in range(1, len(poly)):
            rho += poly[i] * theta_i
            theta_i *= theta
            
        # 计算未畸变的图像坐标
        if r_3d > 0:
            x = rho * X / r_3d
            y = rho * Y / r_3d
        else:
            x = 0
            y = 0
            
        # 应用仿射变换
        x_affine = affine[0] * x + affine[1] * y
        y_affine = affine[2] * x + affine[3] * y
        
        # 加上中心偏移
        return x_affine + cx, y_affine + cy
        
    def _compute_inverse_poly(self):
        """
        计算反向多项式系数（从rho到theta）
        """
        # 创建采样点
        max_rho = min(self.image_size) * 0.5
        rho_samples = np.linspace(0, max_rho, 100)
        theta_samples = []
        
        # 对每个rho找到对应的theta
        for rho in rho_samples:
            # 使用二分查找
            theta_min, theta_max = 0, np.pi/2
            for _ in range(20):
                theta_mid = (theta_min + theta_max) / 2
                
                # 计算f(theta)
                rho_calc = self.poly_coeffs[0]
                theta_i = theta_mid
                for i in range(1, len(self.poly_coeffs)):
                    rho_calc += self.poly_coeffs[i] * theta_i
                    theta_i *= theta_mid
                    
                if rho_calc < rho:
                    theta_min = theta_mid
                else:
                    theta_max = theta_mid
                    
            theta_samples.append(theta_mid)
            
        # 拟合反向多项式
        theta_samples = np.array(theta_samples)
        A = np.vander(rho_samples, self.poly_order, increasing=True)
        self.inv_poly_coeffs = np.linalg.lstsq(A, theta_samples, rcond=None)[0]
        
    def create_undistort_maps(self, scale=1.0):
        """
        创建去畸变映射表
        scale: 输出图像的缩放因子
        """
        if self.poly_coeffs is None or self.inv_poly_coeffs is None:
            return None, None
            
        width, height = self.image_size
        new_width = int(width * scale)
        new_height = int(height * scale)
        
        # 创建映射表
        map_x = np.zeros((new_height, new_width), dtype=np.float32)
        map_y = np.zeros((new_height, new_width), dtype=np.float32)
        
        # 新图像的中心
        new_cx = new_width / 2
        new_cy = new_height / 2
        
        # 计算新图像的焦距（控制视场角）
        new_focal = min(new_width, new_height) * 0.5
        
        for y in range(new_height):
            for x in range(new_width):
                # 归一化坐标
                x_norm = (x - new_cx) / new_focal
                y_norm = (y - new_cy) / new_focal
                
                # 计算3D方向
                r = np.sqrt(x_norm**2 + y_norm**2)
                if r == 0:
                    map_x[y, x] = self.center[0]
                    map_y[y, x] = self.center[1]
                    continue
                
                # 从r计算theta（针孔模型）
                theta = np.arctan(r)
                
                # 限制theta范围（对于180度镜头）
                if theta > np.pi * 0.48:  # 约172度
                    map_x[y, x] = -1
                    map_y[y, x] = -1
                    continue
                
                # 使用正向多项式计算rho
                rho = self.poly_coeffs[0]
                theta_i = theta
                for i in range(1, len(self.poly_coeffs)):
                    rho += self.poly_coeffs[i] * theta_i
                    theta_i *= theta
                
                # 计算畸变图像坐标
                if r > 0:
                    x_dist = rho * x_norm / r
                    y_dist = rho * y_norm / r
                else:
                    x_dist = 0
                    y_dist = 0
                
                # 应用仿射变换
                x_affine = self.affine[0] * x_dist + self.affine[1] * y_dist
                y_affine = self.affine[2] * x_dist + self.affine[3] * y_dist
                
                # 最终坐标
                src_x = x_affine + self.center[0]
                src_y = y_affine + self.center[1]
                
                # 检查边界
                if 0 <= src_x < width and 0 <= src_y < height:
                    map_x[y, x] = src_x
                    map_y[y, x] = src_y
                else:
                    map_x[y, x] = -1
                    map_y[y, x] = -1
                    
        return map_x, map_y


def manual_fisheye_calibration(image_folder, output_folder, 
                             pattern=(11, 8), square_size=3.0,
                             show_results=True):
    """
    使用手动实现的OCam方法进行180度鱼眼标定
    """
    print("=" * 60)
    print("手动OCam鱼眼标定（不使用OpenCV fisheye模块）")
    print("=" * 60)
    
    # 准备棋盘格点
    objp = np.zeros((pattern[0] * pattern[1], 3), np.float32)
    objp[:, :2] = np.mgrid[0:pattern[0], 0:pattern[1]].T.reshape(-1, 2)
    objp *= square_size
    
    objpoints = []
    imgpoints = []
    valid_images = []
    image_size = None
    
    # 读取图像
    image_files = glob.glob(os.path.join(image_folder, '*.jpg'))
    image_files.extend(glob.glob(os.path.join(image_folder, '*.png')))
    
    print(f"找到 {len(image_files)} 张图像")
    
    # 检测角点
    for fname in sorted(image_files):
        img = cv2.imread(fname)
        if img is None:
            continue
            
        if image_size is None:
            image_size = (img.shape[1], img.shape[0])
            
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # 查找角点
        ret, corners = cv2.findChessboardCorners(
            gray, pattern,
            cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE
        )
        
        if ret:
            # 亚像素精化
            corners2 = cv2.cornerSubPix(
                gray, corners, (11, 11), (-1, -1),
                (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
            )
            
            objpoints.append(objp)
            imgpoints.append(corners2.reshape(-1, 2))
            valid_images.append((fname, img))
            print(f"✓ {os.path.basename(fname)}")
        else:
            print(f"✗ {os.path.basename(fname)}")
            
    if len(objpoints) < 10:
        print("错误：有效图像太少！")
        return None
        
    print(f"\n使用 {len(objpoints)} 张图像进行标定")
    
    # 执行标定
    calibrator = ManualOCamCalibrator(poly_order=4)
    success = calibrator.calibrate(objpoints, imgpoints, image_size)
    
    if not success:
        print("标定失败！")
        return None
        
    # 创建输出目录
    os.makedirs(output_folder, exist_ok=True)
    
    # 生成去畸变映射
    print("\n生成去畸变映射...")
    map_x, map_y = calibrator.create_undistort_maps(scale=1.0)
    
    # 处理图像
    print("\n处理图像...")
    for i, (fname, img) in enumerate(valid_images[:5]):  # 先处理前5张测试
        # 去畸变
        undistorted = cv2.remap(img, map_x, map_y,
                              interpolation=cv2.INTER_LINEAR,
                              borderMode=cv2.BORDER_CONSTANT)
        
        # 保存
        output_path = os.path.join(output_folder, f"undist_{os.path.basename(fname)}")
        cv2.imwrite(output_path, undistorted)
        print(f"已保存: {os.path.basename(output_path)}")
        
        # 显示对比
        if show_results and i == 0:
            plt.figure(figsize=(15, 7))
            
            plt.subplot(121)
            plt.imshow(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
            plt.title('原始180°鱼眼图像')
            plt.axis('off')
            
            plt.subplot(122)
            plt.imshow(cv2.cvtColor(undistorted, cv2.COLOR_BGR2RGB))
            plt.title('去畸变图像')
            plt.axis('off')
            
            plt.tight_layout()
            plt.show()
    
    return calibrator


if __name__ == "__main__":
    input_folder = "/Users/couesfang/我的云端硬盘/25机器狗户外研究/05软件系统/RemoteControlDog/rd_robot/cam_calibration/180cam_images"
    output_folder = "/Users/couesfang/我的云端硬盘/25机器狗户外研究/05软件系统/RemoteControlDog/rd_robot/cam_calibration/180_manual_ocam"
    
    calibrator = manual_fisheye_calibration(
        input_folder,
        output_folder,
        pattern=(11, 8),
        square_size=3.0,
        show_results=True
    )