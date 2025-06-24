#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CameraHandler – 1080p → undistort → 480p
兼容 cv2.fisheye.calibrate 输出
"""

import cv2
import logging
import numpy as np

logger = logging.getLogger(__name__)

# ------- 直接填入 fisheye.calibrate 的结果 (注意顺序: [w,h]) -------
DEFAULT_FISHEYE_PARAMS = {
    # 内参矩阵 K (3×3)
    "K": [
        [6.05497153e02, -9.80219732e-03, 9.71773710e02],
        [0.0,            6.04738486e02, 5.22561566e02],
        [0.0,            0.0,           1.0],
    ],
    # 畸变系数 D (k1, k2, k3, k4)
    "D": [-0.14713139, -0.01777163, 0.0, 0.0],
    # 标定图像尺寸 [width, height]
    "ImageSize": [1920, 1080],
}

# 从MATLAB参数构建OpenCV所需的参数
# 图像尺寸
img_width = 1920
img_height = 1080

# 畸变中心（主点）
cx = 976.0474
cy = 521.8287

# 从MappingCoefficients提取焦距（第一个参数）
focal_length = 684.0465

# 构建相机内参矩阵 K
K = np.array([[focal_length, 0, cx],
              [0, focal_length, cy],
              [0, 0, 1]], dtype=np.float64)

# 畸变系数 D (从MappingCoefficients的后三个参数，加上第四个参数)
D = np.array([-0.0017, 0, 0, 0], dtype=np.float64)


class CameraHandler:
    """
    1. 以 1920×1080 打开摄像头
    2. fisheye 畸变校正
    3. 缩放到 (width,height)，默认 640×480
    4. JPEG 编码
    """

    def __init__(
        self,
        camera_id: int = 0,
        width: int = 640,
        height: int = 480,
        jpeg_quality: int = 80,
        fisheye_params: dict = DEFAULT_FISHEYE_PARAMS,
        fisheye_balance: float = 0.0,
    ):
        self.camera_id = camera_id
        self.width = width
        self.height = height
        self.out_size = (width, height)
        self.jpeg_quality = jpeg_quality

        # ---------- fisheye 参数 ----------
        self.K = np.asarray(fisheye_params["K"], np.float64)
        self.D = np.asarray(fisheye_params["D"], np.float64).reshape(4, 1)
        calib_w, calib_h = fisheye_params["ImageSize"]
        self.calib_size = (calib_w, calib_h)  # (w,h)

        # ---------- 畸变 LUT ----------
        self.P_new, self.map1, self.map2 = self._build_lut(fisheye_balance)

        # ---------- 摄像头 ----------
        self.cap = self._open_camera()

    # --------------------------------------------------
    def _build_lut(self, balance: float):
        logger.info("K:\n%s", self.K)
        logger.info("D: %s", self.D.ravel())
        logger.info("标定分辨率 (w,h): %s", self.calib_size)

        P_new = cv2.fisheye.estimateNewCameraMatrixForUndistortRectify(
            self.K, self.D, self.calib_size, np.eye(3), balance=balance
        )

        map1, map2 = cv2.fisheye.initUndistortRectifyMap(
            self.K,
            self.D,
            np.eye(3),
            P_new,
            self.calib_size,
            cv2.CV_16SC2,
        )

        logger.info("畸变 LUT 生成完毕")
        return P_new, map1, map2

    # --------------------------------------------------
    def _open_camera(self):
        cap = cv2.VideoCapture(self.camera_id)
        if not cap.isOpened():
            logger.error("无法打开摄像头 %s", self.camera_id)
            return None

        # 强制 1920×1080
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

        # 验证尺寸
        ok, test = cap.read()
        if not ok:
            logger.error("摄像头读帧失败")
            cap.release()
            return None

        h, w = test.shape[:2]
        logger.info("摄像头实际输出: %dx%d", w, h)
        if (w, h) != self.calib_size:
            logger.warning(
                "实际输出与标定尺寸不一致，建议让相机输出 %s！", self.calib_size
            )
        return cap

    # --------------------------------------------------
    def is_opened(self) -> bool:
        return self.cap is not None and self.cap.isOpened()

    def read_frame(self):
        if not self.is_opened():
            return None
        ok, frame = self.cap.read()
        return frame if ok else None

    # --------------------------------------------------
    def preprocess_frame(self, frame):
        if frame is None:
            return b""
        
        # hand writen undistort
        balance = 0.5
        h=1080
        w=1920
        # h, w = frame.shape[:2]
        # if not dim2:
        dim2 = (w, h)
        # if not dim3:
        dim3 = (w, h)
        
        # 计算新的相机矩阵
        scaled_K = K.copy()
        scaled_K[0, 0] = K[0, 0] * dim3[0] / w
        scaled_K[1, 1] = K[1, 1] * dim3[1] / h
        scaled_K[0, 2] = K[0, 2] * dim3[0] / w
        scaled_K[1, 2] = K[1, 2] * dim3[1] / h
        
        # 获取新的相机矩阵
        new_K = cv2.fisheye.estimateNewCameraMatrixForUndistortRectify(
            scaled_K, D, dim2, np.eye(3), balance=balance
        )
        
        # 计算映射
        map1, map2 = cv2.fisheye.initUndistortRectifyMap(
            K, D, np.eye(3), K, dim3, cv2.CV_16SC2
        )

        # 应用映射进行畸变校正
        frame = cv2.remap(
            frame, map1, map2, 
            interpolation=cv2.INTER_LINEAR, 
            borderMode=cv2.BORDER_CONSTANT
        )
        

        # 1. 畸变校正
        # frame = cv2.remap(
        #     frame,
        #     self.map1,
        #     self.map2,
        #     interpolation=cv2.INTER_LINEAR,
        #     borderMode=cv2.BORDER_CONSTANT,
        # )

        # 2. 缩放到目标尺寸
        if (frame.shape[1], frame.shape[0]) != self.out_size:
            frame = cv2.resize(
                frame, self.out_size, interpolation=cv2.INTER_AREA
            )

        # 3. JPEG
        ok, enc = cv2.imencode(
            ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality]
        )
        return enc.tobytes() if ok else b""

    # --------------------------------------------------
    def release(self):
        if self.cap:
            self.cap.release()
            logger.info("摄像头已释放")


# ------------------- 演示 -------------------
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )

    cam = CameraHandler()
    if not cam.is_opened():
        exit("摄像头失败")

    try:
        while True:
            f = cam.read_frame()
            if f is None:
                break
            jpg = cam.preprocess_frame(f)
            # 这里可以把 jpg 发送 / 存盘 / 显示
    finally:
        cam.release()