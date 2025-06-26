#!/usr/bin/env python3
import subprocess
import numpy as np
import cv2
import time
import os

class CSICameraCommandLine:
    """使用命令行GStreamer的CSI摄像头类"""
    
    def __init__(self, sensor_id=0, width=1280, height=720, fps=30):
        self.sensor_id = sensor_id
        self.width = width
        self.height = height
        self.fps = fps
        self.temp_file = f"/tmp/csi_frame_{sensor_id}.jpg"
        
    def capture_frame(self):
        """捕获一帧"""
        try:
            # 使用gst-launch捕获一帧到文件
            cmd = [
                "gst-launch-1.0",
                "nvarguscamerasrc",
                f"sensor-id={self.sensor_id}",
                "num-buffers=1",
                "!",
                f"video/x-raw(memory:NVMM),width={self.width},height={self.height},framerate={self.fps}/1",
                "!",
                "nvvidconv",
                "!",
                "nvjpegenc",
                "!",
                "filesink",
                f"location={self.temp_file}"
            ]
            
            # 运行命令（隐藏输出）
            result = subprocess.run(cmd, capture_output=True, timeout=5)
            
            if result.returncode == 0 and os.path.exists(self.temp_file):
                # 读取图像
                frame = cv2.imread(self.temp_file)
                os.remove(self.temp_file)  # 删除临时文件
                return True, frame
            else:
                return False, None
                
        except Exception as e:
            print(f"捕获失败: {e}")
            return False, None
    
    def capture_continuous(self, duration=10):
        """连续捕获测试"""
        print(f"开始连续捕获 {duration} 秒...")
        start_time = time.time()
        frame_count = 0
        
        while time.time() - start_time < duration:
            ret, frame = self.capture_frame()
            if ret:
                frame_count += 1
                print(f"捕获帧 {frame_count}: {frame.shape}")
                
                # 保存第一帧
                if frame_count == 1:
                    cv2.imwrite(f"csi_continuous_test_{self.sensor_id}.jpg", frame)
                    print(f"已保存第一帧")
            else:
                print("捕获失败")
            
            time.sleep(1)  # 每秒一帧
        
        print(f"完成，总共捕获 {frame_count} 帧")

# 测试
if __name__ == "__main__":
    print("=== CSI摄像头命令行方案测试 ===")
    
    # 测试CSI-0
    camera0 = CSICameraCommandLine(sensor_id=0)
    ret, frame = camera0.capture_frame()
    
    if ret:
        print(f"✅ CSI-0 成功: {frame.shape}")
        cv2.imwrite("csi0_cmdline_test.jpg", frame)
        
        # 连续捕获测试
        camera0.capture_continuous(5)
    else:
        print("❌ CSI-0 失败")
    
    # 测试CSI-1
    camera1 = CSICameraCommandLine(sensor_id=1)
    ret, frame = camera1.capture_frame()
    
    if ret:
        print(f"✅ CSI-1 成功: {frame.shape}")
        cv2.imwrite("csi1_cmdline_test.jpg", frame)
    else:
        print("❌ CSI-1 失败")