import cv2
import threading
import time
from flask import Flask, Response, render_template_string

# --- 设置 ---
CAPTURE_WIDTH = 640
CAPTURE_HEIGHT = 480
TARGET_FPS = 10  # 我们希望发送的帧率 (10Hz)
JPEG_QUALITY = 20 # JPEG 压缩质量 (0-100, 越高越清晰但文件越大)
# ---

# 全局变量，用于在线程间共享帧数据
output_frame = None
lock = threading.Lock() # 线程锁，防止多线程同时访问 output_frame 造成数据冲突

# 初始化 Flask 应用
app = Flask(__name__)

# 初始化摄像头
video_capture = cv2.VideoCapture(0)
# 添加一个启动检查
if not video_capture.isOpened():
    raise RuntimeError("无法打开摄像头。请检查摄像头是否连接或被其他程序占用。")
else:
    print("摄像头已成功打开。")

# 设置摄像头捕获分辨率
video_capture.set(cv2.CAP_PROP_FRAME_WIDTH, CAPTURE_WIDTH)
video_capture.set(cv2.CAP_PROP_FRAME_HEIGHT, CAPTURE_HEIGHT)
# 尝试设置摄像头硬件帧率 (不一定所有摄像头都支持)
video_capture.set(cv2.CAP_PROP_FPS, 25) # 我们让摄像头以更高帧率捕获，以确保有新帧可用


def capture_thread_func():
    """
    专门用于捕获摄像头画面的线程函数。
    它会持续读取帧并更新全局变量 output_frame。
    """
    global video_capture, output_frame, lock
    
    print("摄像头捕获线程已启动...")
    while True:
        if not video_capture.isOpened():
            print("摄像头未开启，线程退出。")
            break

        success, frame = video_capture.read()
        if success:
            # print("newframe") # 频繁打印会影响性能，调试时可开启
            with lock:
                # 直接更新 output_frame，覆盖旧的帧
                output_frame = frame.copy()
        else:
            # 读取失败时可以等待一会再尝试
            print("无法读取摄像头帧，等待...")
            time.sleep(0.5)

    video_capture.release()
    print("摄像头捕获线程已停止。")


def generate_frames():
    """
    一个生成器函数，用于从全局变量读取最新的帧，
    并按照 TARGET_FPS 的频率将其编码为 JPEG 流输出。
    """
    global output_frame, lock
    
    # 计算每帧之间需要等待的时间
    frame_interval = 1.0 / TARGET_FPS

    while True:
        # 等待，以控制发送的帧率
        time.sleep(frame_interval)

        current_frame = None
        with lock:
            # 如果 output_frame 还没有被捕获线程填充，则跳过此次循环
            if output_frame is None:
                continue
            # 复制一份帧到局部变量，以尽快释放锁
            current_frame = output_frame.copy()

        # 对当前帧进行JPEG编码
        # 可以通过调整 imencode 的第三个参数来控制压缩质量
        params = [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY]
        (flag, encoded_image) = cv2.imencode(".jpg", current_frame, params)

        # 如果编码失败，跳过
        if not flag:
            continue

        # 将编码后的图像字节流作为 MJPEG 帧产出
        yield(b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + 
              bytearray(encoded_image) + b'\r\n')


@app.route('/')
def index():
    """主页，显示视频流。"""
    # 这是【已修复】的部分
    html_template = """
    <html>
    <head>
        <title>低延迟实时视频监控 (10Hz)</title>
         <style>
        body { display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; background-color: #1a1a1a; }
        img { border: 3px solid #00ff00; background-color: #000; }
    </style>
    </head>
    <body>
        <!-- url_for 和变量 w, h 会被 Jinja2 引擎正确渲染 -->
        <img src="{{ url_for('video_feed') }}" width="{{ w }}" height="{{ h }}">
    </body>
    </html>
    """
    # 将 Python 变量作为关键字参数传递给模板
    return render_template_string(html_template, w=CAPTURE_WIDTH, h=CAPTURE_HEIGHT)

@app.route('/video_feed')
def video_feed():
    """视频流路由。"""
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    # 创建并启动摄像头捕获线程
    capture_thread = threading.Thread(target=capture_thread_func)
    capture_thread.daemon = True  # 设置为守护线程，这样主程序退出时它也会退出
    capture_thread.start()

    # 启动 Flask Web 服务器
    # 使用 use_reloader=False 避免主线程重启导致摄像头资源问题
    print(f"服务器正在启动，请在浏览器中访问 http://<你的IP地址>:58603")
    print(f"流媒体参数: {CAPTURE_WIDTH}x{CAPTURE_HEIGHT}, {TARGET_FPS}Hz, JPEG质量={JPEG_QUALITY}")
    app.run(host='0.0.0.0', port=58603, debug=False, threaded=True)