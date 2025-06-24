import cv2
import sys

# --- 配置参数 ---
CAMERA_INDEX = 0  # 对应 sensor-id=0
OUTPUT_FILENAME = "captured_image_correct.jpg"
# 设置捕获分辨率
CAPTURE_WIDTH = 1920
CAPTURE_HEIGHT = 1080

def create_gstreamer_pipeline(
    sensor_id=0,
    capture_width=1920,
    capture_height=1080,
    display_width=1920,
    display_height=1080,
    framerate=30,
    flip_method=0,
):
    """
    构建并返回一个用于NVIDIA Jetson CSI摄像头的GStreamer管道字符串。
    这个管道会处理好Debayering，输出OpenCV可以直接使用的BGR格式。
    """
    return (
        f"nvarguscamerasrc sensor-id={sensor_id} ! "
        f"video/x-raw(memory:NVMM), width=(int){capture_width}, height=(int){capture_height}, framerate=(fraction){framerate}/1 ! "
        "nvvidconv flip-method=0 ! "
        f"video/x-raw, width=(int){display_width}, height=(int){display_height}, format=(string)BGRx ! "
        "videoconvert ! "
        "video/x-raw, format=(string)BGR ! appsink"
    )

def main():
    """
    主函数，使用GStreamer管道打开摄像头、捕获并保存一张图片。
    """
    # 1. 创建 GStreamer 管道
    gstreamer_pipeline_str = create_gstreamer_pipeline(
        sensor_id=CAMERA_INDEX,
        capture_width=CAPTURE_WIDTH,
        capture_height=CAPTURE_HEIGHT,
        display_width=CAPTURE_WIDTH, # 可以设置为不同的显示/处理分辨率
        display_height=CAPTURE_HEIGHT,
    )
    print("使用的 GStreamer 管道:")
    print(gstreamer_pipeline_str)

    # 2. 使用 GStreamer 后端打开摄像头
    # 注意第二个参数是 cv2.CAP_GSTREAMER
    cap = cv2.VideoCapture(gstreamer_pipeline_str, cv2.CAP_GSTREAMER)

    # 3. 检查摄像头是否成功打开
    if not cap.isOpened():
        print(f"错误：无法通过 GStreamer 打开摄像头。")
        print("请检查：")
        print("1. Jetson IO 工具是否已正确配置 IMX219。")
        print("2. GStreamer 依赖是否完整。")
        sys.exit(1)

    print("成功打开摄像头。正在捕获图像...")

    # 4. 从摄像头读取一帧图像
    ret, frame = cap.read()

    # 5. 检查图像帧是否成功捕获
    if not ret or frame is None:
        print("错误：无法从摄像头捕获图像帧。")
        cap.release()
        sys.exit(1)

    # 6. 保存捕获到的图像帧到文件
    try:
        cv2.imwrite(OUTPUT_FILENAME, frame)
        print(f"成功！图像已保存为 '{OUTPUT_FILENAME}'")
        # 打印图像尺寸以供验证
        print(f"图像尺寸: {frame.shape}") 
    except Exception as e:
        print(f"错误：保存图像时发生问题: {e}")

    # 7. 释放摄像头资源
    cap.release()
    print("摄像头资源已释放。")

if __name__ == "__main__":
    main()