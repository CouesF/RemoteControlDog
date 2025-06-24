import cv2, glob, numpy as np, os, textwrap

IMG_DIR   = '/home/d3lab/Projects/RemoteControlDog/robot_dog_python/cam_calibration/180cam_images'
PATTERN   = (11, 8)   # (列, 行) = 内角点数
SQUARE_MM = 3.0

def build_objp(cols, rows, square):
    """横向优先 world 坐标 (X 先变、Y 后变)"""
    objp = np.zeros((cols*rows, 1, 3), np.float32)
    objp[:, 0, :2] = np.mgrid[0:cols, 0:rows].T.reshape(-1, 2)
    objp *= square
    return objp

def main():
    cols, rows = PATTERN
    objp = build_objp(cols, rows, SQUARE_MM)

    objpoints, imgpoints = [], []
    files = sorted(glob.glob(os.path.join(IMG_DIR, '*.*')))
    if not files:
        raise RuntimeError('文件夹为空')

    print(f'检测图片数量：{len(files)}')
    
    # 获取第一张图片的尺寸
    sample_img = cv2.imread(files[0])
    if sample_img is None:
        raise RuntimeError('无法读取第一张图片')
    h, w = sample_img.shape[:2]
    
    # 收集所有角点
    for f in files:
        img  = cv2.imread(f)
        if img is None:
            continue
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        ok, corners = cv2.findChessboardCorners(
            gray, PATTERN, 
            cv2.CALIB_CB_ADAPTIVE_THRESH | cv2.CALIB_CB_NORMALIZE_IMAGE)

        if not ok:
            print(f'× {os.path.basename(f):28}  棋盘检测失败')
            continue

        corners = cv2.cornerSubPix(gray, corners, (11,11), (-1,-1),
                                   (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.1))

        objpoints.append(objp)
        imgpoints.append(corners)
        print(f'✓ {os.path.basename(f):28}  角点 {len(corners)}')

    n = len(objpoints)
    if n < 5:
        raise RuntimeError(f'有效图像仅 {n} 张，无法标定')

    print(f'\n共保留 {n} 张图像，开始标定 …')
    
    # 对于180度鱼眼，我们需要非常特殊的处理
    print('\n使用180度鱼眼专用策略...')
    
    # 策略1：使用极小的焦距和强畸变初始值
    results = []
    
    # 尝试一系列焦距值
    focal_values = [w/20, w/15, w/12, w/10, w/8, w/6, w/5, w/4]
    
    for f_init in focal_values:
        print(f'\n尝试焦距: {f_init:.1f}')
        
        K = np.array([[f_init, 0, w/2],
                      [0, f_init, h/2],
                      [0, 0,      1]], np.float64)
        
        # 180度鱼眼需要强畸变初始值
        distortion_inits = [
            np.array([[-0.3], [0.15], [-0.05], [0.01]], np.float64),
            np.array([[-0.5], [0.25], [-0.1], [0.05]], np.float64),
            np.array([[-0.7], [0.35], [-0.15], [0.08]], np.float64),
        ]
        
        for d_idx, D_init in enumerate(distortion_inits):
            try:
                # 首先只标定K1和K2
                rms1, K1, D1, _, _ = cv2.fisheye.calibrate(
                    objpoints, imgpoints, (w, h),
                    K.copy(), D_init.copy(),
                    flags=cv2.fisheye.CALIB_RECOMPUTE_EXTRINSIC |
                          cv2.fisheye.CALIB_FIX_K3 |
                          cv2.fisheye.CALIB_FIX_K4,
                    criteria=(cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 50, 1e-6))
                
                # 然后尝试标定所有参数
                try:
                    rms2, K2, D2, _, _ = cv2.fisheye.calibrate(
                        objpoints, imgpoints, (w, h),
                        K1.copy(), D1.copy(),
                        flags=cv2.fisheye.CALIB_RECOMPUTE_EXTRINSIC,
                        criteria=(cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 50, 1e-6))
                    
                    fx = K2[0, 0]
                    # 对于鱼眼相机，使用更准确的视场角计算
                    fov_x = 2 * np.arctan(w / (2 * fx)) * 180 / np.pi
                    
                    results.append({
                        'K': K2, 'D': D2, 'rms': rms2, 'fov': fov_x,
                        'fx': fx, 'method': f'完整标定(f={f_init:.0f}, d={d_idx})'
                    })
                    print(f'  畸变初值{d_idx+1} - 完整标定成功: RMS={rms2:.3f}, FOV={fov_x:.1f}°')
                    
                except:
                    fx = K1[0, 0]
                    fov_x = 2 * np.arctan(w / (2 * fx)) * 180 / np.pi
                    results.append({
                        'K': K1, 'D': D1, 'rms': rms1, 'fov': fov_x,
                        'fx': fx, 'method': f'部分标定(f={f_init:.0f}, d={d_idx})'
                    })
                    print(f'  畸变初值{d_idx+1} - 部分标定: RMS={rms1:.3f}, FOV={fov_x:.1f}°')
                    
            except Exception as e:
                continue
    
    if not results:
        print('\n所有尝试都失败了！')
        return
    
    # 选择最接近180度的结果
    print('\n=== 所有结果汇总 ===')
    for r in sorted(results, key=lambda x: abs(x['fov'] - 180)):
        print(f"{r['method']:30} RMS={r['rms']:.3f}  FOV={r['fov']:.1f}°  fx={r['fx']:.1f}")
    
    # 选择最佳结果（平衡FOV和RMS）
    # 优先选择FOV在150-190度范围内，RMS较小的
    valid_results = [r for r in results if 150 < r['fov'] < 190]
    if valid_results:
        best = min(valid_results, key=lambda x: x['rms'])
    else:
        # 如果没有在合理范围内的，选择FOV最大的
        best = max(results, key=lambda x: x['fov'])
    
    print('\n=== 最佳标定结果 ===')
    print(f'方法: {best["method"]}')
    print(f'RMS: {best["rms"]:.4f}')
    print(f'水平视场角: {best["fov"]:.1f}°')
    print('K :\n', best['K'])
    print('D :', best['D'].ravel())
    
    # 如果视场角仍然太小，提供诊断信息
    if best['fov'] < 150:
        print('\n⚠️ 警告：计算的视场角小于150度！')
        print('可能的原因：')
        print('1. 相机可能不是真正的180度鱼眼')
        print('2. 标定图像可能没有充分利用边缘区域')
        print('3. OpenCV鱼眼模型可能不适合该相机')
        print('\n建议尝试omnidir模块进行全向相机标定')
    
    # 保存标定结果
    np.savez('fisheye_calibration.npz', 
             K=best['K'], D=best['D'], rms=best['rms'], fov=best['fov'])
    print('\n标定结果已保存到 fisheye_calibration.npz')

if __name__ == '__main__':
    main()