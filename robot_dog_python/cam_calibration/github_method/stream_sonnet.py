import cv2
import numpy as np
import time

class ScaramuzzaFisheyeUndistorter:
    def __init__(self, mapping_coeffs, image_size, distortion_center, stretch_matrix=None):
        """
        初始化Scaramuzza鱼眼去畸变器
        
        Args:
            mapping_coeffs: [a0, a2, a3, a4] 多项式系数
            image_size: [height, width] 图像尺寸
            distortion_center: [cx, cy] 畸变中心
            stretch_matrix: 2x2 拉伸矩阵，默认为单位矩阵
        """
        self.mapping_coeffs = np.array(mapping_coeffs)
        self.image_size = image_size
        self.distortion_center = np.array(distortion_center)
        self.stretch_matrix = stretch_matrix if stretch_matrix is not None else np.eye(2)
        
        # 预计算去畸变映射表
        self.map_x, self.map_y = self._create_undistort_maps()
    
    def _polynomial_function(self, rho):
        """
        Scaramuzza多项式函数: f(rho) = a0 + a2*rho^2 + a3*rho^3 + a4*rho^4
        """
        a0, a2, a3, a4 = self.mapping_coeffs
        return a0 + a2 * rho**2 + a3 * rho**3 + a4 * rho**4
    
    def _solve_rho_inverse(self, z_target, initial_rho=1.0, max_iterations=50, tolerance=1e-6):
        """
        数值求解多项式方程的逆函数
        使用牛顿法求解: f(rho) = z_target
        """
        rho = initial_rho
        a0, a2, a3, a4 = self.mapping_coeffs
        
        for _ in range(max_iterations):
            # f(rho) = a0 + a2*rho^2 + a3*rho^3 + a4*rho^4
            f_rho = a0 + a2 * rho**2 + a3 * rho**3 + a4 * rho**4
            
            # f'(rho) = 2*a2*rho + 3*a3*rho^2 + 4*a4*rho^3
            f_prime_rho = 2 * a2 * rho + 3 * a3 * rho**2 + 4 * a4 * rho**3
            
            if abs(f_prime_rho) < 1e-12:
                break
                
            delta_rho = (f_rho - z_target) / f_prime_rho
            rho = rho - delta_rho
            
            if abs(delta_rho) < tolerance:
                break
                
            # 确保rho为正值
            rho = max(rho, 0.1)
        
        return rho
    
    def _create_undistort_maps(self):
        """
        创建去畸变映射表
        """
        height, width = self.image_size
        
        # 创建输出图像的坐标网格
        u_out, v_out = np.meshgrid(np.arange(width), np.arange(height))
        
        # 转换到以畸变中心为原点的坐标系
        cx, cy = self.distortion_center
        u_centered = u_out - cx
        v_centered = v_out - cy
        
        # 应用拉伸矩阵的逆变换
        stretch_inv = np.linalg.inv(self.stretch_matrix)
        coords_stretched = np.stack([u_centered.flatten(), v_centered.flatten()], axis=0)
        coords_original = stretch_inv @ coords_stretched
        u_orig = coords_original[0].reshape(height, width)
        v_orig = coords_original[1].reshape(height, width)
        
        # 计算距离中心的距离
        rho_out = np.sqrt(u_orig**2 + v_orig**2)
        
        # 设定输出图像的视场范围（可调整以保留更大视角）
        max_angle = np.pi * 0.8  # 约144度视场角，可根据需要调整
        
        # 将输出坐标映射到球面坐标
        theta = (rho_out / np.max(rho_out)) * max_angle
        
        # 计算对应的z值（根据所需的投影方式）
        z_target = self.mapping_coeffs[0] * np.cos(theta)
        
        # 为每个像素求解对应的原始rho
        map_x = np.zeros_like(u_out, dtype=np.float32)
        map_y = np.zeros_like(v_out, dtype=np.float32)
        
        # 使用向量化操作加速计算
        valid_mask = rho_out > 1e-6
        
        for i in range(height):
            for j in range(width):
                if not valid_mask[i, j]:
                    map_x[i, j] = cx
                    map_y[i, j] = cy
                    continue
                
                try:
                    # 求解原始图像中的rho
                    rho_orig = self._solve_rho_inverse(z_target[i, j])
                    
                    # 计算原始图像中的坐标
                    if rho_out[i, j] > 0:
                        scale = rho_orig / rho_out[i, j]
                        u_orig_final = u_orig[i, j] * scale + cx
                        v_orig_final = v_orig[i, j] * scale + cy
                        
                        # 检查坐标是否在图像范围内
                        if 0 <= u_orig_final < width and 0 <= v_orig_final < height:
                            map_x[i, j] = u_orig_final
                            map_y[i, j] = v_orig_final
                        else:
                            map_x[i, j] = -1
                            map_y[i, j] = -1
                    else:
                        map_x[i, j] = cx
                        map_y[i, j] = cy
                        
                except:
                    map_x[i, j] = -1
                    map_y[i, j] = -1
        
        return map_x, map_y
    
    def undistort_image(self, distorted_image):
        """
        去畸变图像
        """
        return cv2.remap(distorted_image, self.map_x, self.map_y, 
                        cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)

def main():
    # Matlab标定结果参数
    mapping_coeffs = [684.0465, -0.0017, 0, 0]
    image_size = [1080, 1920]  # [height, width]
    distortion_center = [976.0474, 521.8287]  # [cx, cy]
    stretch_matrix = np.array([[1, 0], [0, 1]])  # 单位矩阵
    
    # 创建去畸变器
    print("正在初始化Scaramuzza鱼眼去畸变器...")
    undistorter = ScaramuzzaFisheyeUndistorter(
        mapping_coeffs, image_size, distortion_center, stretch_matrix
    )
    print("去畸变器初始化完成！")
    
    # 打开摄像头
    cap = cv2.VideoCapture(0)
    
    # 设置摄像头分辨率（如果支持）
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
    
    if not cap.isOpened():
        print("无法打开摄像头")
        return
    
    print("开始实时去畸变处理... 按'q'键退出")
    
    # 性能统计
    frame_count = 0
    start_time = time.time()
    
    try:
        while True:
            # 读取帧
            ret, frame = cap.read()
            if not ret:
                print("无法读取视频帧")
                break
            
            # 调整帧大小到标定时的尺寸（如果需要）
            if frame.shape[:2] != tuple(image_size):
                frame = cv2.resize(frame, (image_size[1], image_size[0]))
            
            # 去畸变
            undistorted_frame = undistorter.undistort_image(frame)
            
            # 创建显示窗口
            # 原始图像（缩放以便显示）
            display_original = cv2.resize(frame, (640, 360))
            display_undistorted = cv2.resize(undistorted_frame, (640, 360))
            
            # 在图像上添加标识
            cv2.putText(display_original, 'Original (Fisheye)', (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.putText(display_undistorted, 'Undistorted', (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            
            # 横向拼接显示
            combined = np.hstack([display_original, display_undistorted])
            
            # 计算FPS
            frame_count += 1
            if frame_count % 30 == 0:
                elapsed = time.time() - start_time
                fps = frame_count / elapsed
                print(f"FPS: {fps:.1f}")
            
            cv2.imshow('Fisheye Undistortion (Scaramuzza Model)', combined)
            
            # 检查退出条件
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
                
    except KeyboardInterrupt:
        print("程序被用户中止")
    
    finally:
        cap.release()
        cv2.destroyAllWindows()
        
        # 最终性能统计
        elapsed = time.time() - start_time
        if elapsed > 0:
            avg_fps = frame_count / elapsed
            print(f"平均FPS: {avg_fps:.1f}")

if __name__ == "__main__":
    main()
