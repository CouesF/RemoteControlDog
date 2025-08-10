import cv2
import threading
import time
from flask import Flask, Response, render_template_string
import numpy as np

# ---- 相机与图像设置 ----
CAPTURE_WIDTH = 320
CAPTURE_HEIGHT = 240
CAPTURE_FPS = 30 # 注意：这是摄像头原始采集帧率
TARGET_FPS = 8   # 这是推流给前端的帧率
JPEG_QUALITY = 16   # 0~100, 越高越清晰/体积大

# ---- Flask 初始化 ----
app = Flask(__name__)

# ---- 全局帧引用 - 使用字典包装实现可变共享 ----
output_frames = {"left": None, "right": None}
locks = {
    "left": threading.Lock(),
    "right": threading.Lock()
}

# ------------------------------------
# GStreamer 管道生成函数
# ------------------------------------
def gstreamer_pipeline(
    device_id=0,
    capture_width=320,
    capture_height=240,
    framerate=30,
    flip_method=0, # 对于USB摄像头，这个通常不需要设置，设为0
):
    # 对于 V4L2 (Video for Linux 2) 设备，如USB摄像头
    # 我们直接指定设备、格式、分辨率和帧率
    # 然后通过videoconvert转换为OpenCV能处理的BGR格式
    return (
        "v4l2src device=/dev/video%d ! "
        "video/x-raw, format=(string)YUY2, width=(int)%d, height=(int)%d, framerate=(fraction)%d/1 ! "
        "videoconvert ! "
        "video/x-raw, format=(string)BGR ! appsink"
        % (
            device_id,
            capture_width,
            capture_height,
            framerate,
        )
    )

# ---- 摄像头初始化 ----
# 明确设备ID
DEVICE_ID_LEFT = 2
DEVICE_ID_RIGHT = 4

# 创建 GStreamer 管道字符串
pipeline_left = gstreamer_pipeline(DEVICE_ID_LEFT, CAPTURE_WIDTH, CAPTURE_HEIGHT, CAPTURE_FPS)
pipeline_right = gstreamer_pipeline(DEVICE_ID_RIGHT, CAPTURE_WIDTH, CAPTURE_HEIGHT, CAPTURE_FPS)

print("Left Camera Pipeline:\n", pipeline_left)
print("Right Camera Pipeline:\n", pipeline_right)

# 使用 GStreamer 管道和 cv2.CAP_GSTREAMER 标志来打开摄像头
video_capture_left = cv2.VideoCapture(pipeline_left, cv2.CAP_GSTREAMER)
video_capture_right = cv2.VideoCapture(pipeline_right, cv2.CAP_GSTREAMER)

# 检查摄像头是否成功打开
if not video_capture_left.isOpened():
    raise RuntimeError(f"无法使用GStreamer打开摄像头 /dev/video{DEVICE_ID_LEFT}")
if not video_capture_right.isOpened():
    raise RuntimeError(f"无法使用GStreamer打开摄像头 /dev/video{DEVICE_ID_RIGHT}")

print(f"👀 摄像头 left (/dev/video{DEVICE_ID_LEFT}) 启动成功")
print(f"👀 摄像头 right (/dev/video{DEVICE_ID_RIGHT}) 启动成功")

# ----------------------------
# 摄像头采集线程定义 (代码与之前相同)
# ----------------------------
def capture_thread_func(camera_name, cap, output_frames, locks):
    print(f"📷 采集线程 {camera_name} 启动")
    while True:
        ret, frame = cap.read()
        if not ret:
            print(f"⚠️ {camera_name} 读取失败，尝试重启或检查连接...")
            time.sleep(1)
            continue

        with locks[camera_name]:
            output_frames[camera_name] = frame.copy()
            
    cap.release()
    print(f"📷 采集线程 {camera_name} 结束")

# ----------------------------
# MJPEG 生成器 (代码与之前相同)
# ----------------------------
def generate_frames(camera_name):
    frame_interval = 1.0 / TARGET_FPS
    while True:
        time.sleep(frame_interval)

        local_frame = None
        with locks[camera_name]:
            if output_frames[camera_name] is not None:
                local_frame = output_frames[camera_name].copy()

        if local_frame is None:
            continue

        flag, jpeg = cv2.imencode(".jpg", local_frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
        if not flag:
            continue

        yield (b"--frame\r\n"
               b"Content-Type: image/jpeg\r\n\r\n" +
               jpeg.tobytes() +
               b"\r\n")

# ----------------------------
# 前端页面路由 (代码与之前相同)
# ----------------------------
@app.route('/')
def index():
    html_template = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>双摄像头实时监控 (GStreamer/YUY2)</title>
        <style>
            body { margin: 0; padding: 0; background-color: #000; display: flex; justify-content: center; align-items: center; height: 100vh; }
            .container { display: flex; gap: 10px; }
            img { border: 2px solid #0f0; width: {{ w }}; height: {{ h }}; background-color: #222; }
        </style>
    </head>
    <body>
        <div class="container">
            <img src="{{ url_for('video_feed_left') }}">
            <img src="{{ url_for('video_feed_right') }}">
        </div>
    </body>
    </html>
    """
    return render_template_string(
        html_template,
        w=f"{CAPTURE_WIDTH}px",
        h=f"{CAPTURE_HEIGHT}px"
    )

@app.route('/video_feed_left')
def video_feed_left():
    return Response(generate_frames("left"), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/video_feed_right')
def video_feed_right():
    return Response(generate_frames("right"), mimetype='multipart/x-mixed-replace; boundary=frame')

# ----------------------------
# 启动
# ----------------------------
if __name__ == '__main__':
    t_left = threading.Thread(target=capture_thread_func, args=("left", video_capture_left, output_frames, locks))
    t_right = threading.Thread(target=capture_thread_func, args=("right", video_capture_right, output_frames, locks))
    t_left.daemon = True
    t_right.daemon = True
    t_left.start()
    t_right.start()

    print("🚀 服务器启动：http://<你的IP>:58604")
    app.run(host='0.0.0.0', port=58604, debug=False, threaded=True)