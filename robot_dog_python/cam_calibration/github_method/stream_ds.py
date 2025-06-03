import numpy as np
import cv2
import time

# 从Matlab导出的参数
params = {
    "MappingCoefficients": [684.0465, -0.0017, 0, 0],  # [a0, a2, a3, a4]
    "ImageSize": [1080, 1920],       # [height, width]
    "DistortionCenter": [976.0474, 521.8287],  # [cx, cy]
    "StretchMatrix": np.eye(2)       # 单位矩阵
}

# 提取参数
a0, a2, a3, a4 = params["MappingCoefficients"]
cx, cy = params["DistortionCenter"][0], params["DistortionCenter"][1]
height, width = params["ImageSize"]
S = params["StretchMatrix"]
S_inv = np.linalg.inv(S)  # 仿射变换的逆

# 牛顿迭代求解lambda
def solve_lambda(X, Y, Z, max_iter=20, tol=1e-6):
    r2 = X**2 + Y**2
    if r2 < 1e-12:  # 中心点直接返回a0
        return a0
    
    # 计算多项式系数 (简化后的方程形式)
    c = [a4 * (r2**2), a3 * (r2**1.5), a2 * r2, -Z, a0]
    
    # 牛顿迭代设置初始值
    lambda_est = a0 / Z if Z != 0 else a0
    for _ in range(max_iter):
        # 计算多项式值及其导数
        poly_val = c[0]*lambda_est**4 + c[1]*lambda_est**3 + c[2]*lambda_est**2 + c[3]*lambda_est + c[4]
        poly_der = 4*c[0]*lambda_est**3 + 3*c[1]*lambda_est**2 + 2*c[2]*lambda_est + c[3]
        
        if abs(poly_der) < 1e-12:
            break
            
        lambda_new = lambda_est - poly_val / poly_der
        if abs(lambda_new - lambda_est) < tol:
            return lambda_new
        lambda_est = lambda_new
        
    return lambda_est

# 预计算映射表
start_time = time.time()
map_x = np.zeros((height, width), dtype=np.float32)
map_y = np.zeros((height, width), dtype=np.float32)

f = a0  # 虚拟焦距
for v in range(height):      # 遍历行 (y坐标)
    for u in range(width):  # 遍历列 (x坐标)
        # 转换为归一化坐标 (虚拟针孔模型)
        xn = (u - cx) / f
        yn = (v - cy) / f
        
        # 归一化到单位球面
        norm_factor = 1.0 / np.sqrt(xn**2 + yn**2 + 1)
        X = xn * norm_factor
        Y = yn * norm_factor
        Z = norm_factor
        
        # 求解lambda
        lambda_val = solve_lambda(X, Y, Z)
        
        # 畸变点传感器坐标 (u'', v'')
        u_pp = X * lambda_val
        v_pp = Y * lambda_val
        
        # 逆仿射变换 -> 畸变图像坐标 (u_d, v_d)
        u_hat, v_hat = S_inv @ np.array([u_pp, v_pp])
        u_d = u_hat + cx
        v_d = v_hat + cy
        
        # 存储映射 (确保在图像范围内)
        map_x[v, u] = np.clip(u_d, 0, width-1)
        map_y[v, u] = np.clip(v_d, 0, height-1)

print(f"LUT计算完成, 耗时: {time.time()-start_time:.2f}秒")

# 实时视频处理
cap = cv2.VideoCapture(0)  # 摄像头
while True:
    ret, frame = cap.read()
    if not ret: 
        break
        
    # 应用映射表去畸变
    undistorted = cv2.remap(
        frame, map_x, map_y, 
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT
    )
    
    # 显示结果
    cv2.imshow("Distorted", frame)
    cv2.imshow("Undistorted", undistorted)
    
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
