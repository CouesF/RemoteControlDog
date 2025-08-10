from ctypes import POINTER
import cv2
import threading
import time
from flask import Flask, Response, render_template_string
import numpy as np
import os
import sys
import time
from requests import get, head
import serial
import math
from typing import List

# --- SDK & DDS Imports ---
current_script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_script_dir)
communication_dir_path = os.path.join(parent_dir, 'communication')
sys.path.append(communication_dir_path)
try:
    from dds_data_structure import HeadCommand, HeadAction
    from unitree_sdk2py.core.channel import ChannelSubscriber, ChannelFactoryInitialize
except ImportError as e:
    print(f"Error: A required library is not found. {e}")
    sys.exit(1)

# --- 设置 ---
CAPTURE_WIDTH = 640
CAPTURE_HEIGHT = 480
TARGET_FPS = 10  # 我们希望发送的帧率 (10Hz)
JPEG_QUALITY = 20 # JPEG 压缩质量 (0-100, 越高越清晰但文件越大)

VIEW_WIDTH = 5.3
VIEW_HEIGHT = -5.3
POINTER_RADIUS = 5  # 指针半径
POINTER_COLOR = (200, 30, 30)  # 红色
POINTER_THICKNESS = 1  # 指针线条粗细

DDS_NETWORK_INTERFACE = "enP8p1s0"
HEAD_COMMAND_TOPIC = "HeadCommand"
# ---

# 全局变量，用于在线程间共享帧数据
msg = None  # 用于存储最新的头部命令
head_x, head_y = 0.0, 0.0
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

from main_distortion_corrector import FisheyeCorrector

fisheye_corrector = FisheyeCorrector({
                    'is_fisheye': True,
                    'undistorted_resolution': (640, 480),
                    'fisheye_params': {
                'mappingCoeffs': np.array([272.428,-0.002384499,0.0,0.0]),
                'imageSize': np.array([480, 640]),
                'distortionCenter': np.array([328.71590201,234.40496395759]),
                'stretchMatrix': np.array([[1.0, 0.0], [0.0, 1.0]]),
                'undistorted_fov_deg': 110.0
            }
                })

def apply_rotation(frame: np.ndarray, angle: int) -> np.ndarray:
    """应用旋转"""
    if angle == 90:
        return cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
    elif angle == 180:
        return cv2.rotate(frame, cv2.ROTATE_180)
    elif angle == 270:
        return cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
    else:
        return frame

def apply_head_pointer(frame: np.ndarray, head_x: float, head_y: float) -> np.ndarray:
    """在帧上应用头部指针"""
    # 这里我们简单地在指定位置绘制一个圆形指针
    # (head_x, head_y) 映射到图像坐标系
    view_x = int(head_x * VIEW_WIDTH + 320)
    view_y = int(head_y * VIEW_HEIGHT + 240)
    cv2.circle(frame, (view_x, view_y), POINTER_RADIUS, POINTER_COLOR, POINTER_THICKNESS)
    return frame

def get_head_position(data: HeadCommand):
    """获取头部位置"""
    global head_x, head_y
    head_x = data.yaw_deg
    head_y = data.pitch_deg
    print(f"Head position updated: Yaw={head_x:.1f}°, Pitch={head_y:.1f}°")

def capture_thread_func(recorder):
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
                processed_frame = fisheye_corrector.correct(frame)
                processed_frame = apply_rotation(frame=processed_frame, angle=180)
                # add a rectangle, using head orientation info
                processed_frame = apply_head_pointer(frame=processed_frame, head_x=head_x, head_y=head_y)
                output_frame = processed_frame.copy()
                if recorder.is_recording and recorder.video_writer is not None:
                    try:
                        recorder.video_writer.write(processed_frame)
                        recorder.recording_stats['frames_written'] += 1
                    except Exception as e:
                        # Log errors but don't crash the capture thread
                        print(f"Error writing frame to video file: {e}")
                        recorder.recording_stats['write_errors'] = recorder.recording_stats.get('write_errors', 0) + 1
        else:
            # 读取失败时可以等待一会再尝试
            print("无法读取摄像头帧，等待...")
            time.sleep(0.5)

    video_capture.release()
    print("摄像头捕获线程已停止。")

class Recorder:
    def __init__(self, output_dir="recordings", config=None):
        # All variables that used to be global or on 'self' now belong here
        self.is_recording = False
        self.video_writer = None
        self.current_output_file = ""
        self.recording_stats = {}
        self.camera_id = 0 # You can make this configurable
        self.output_dir = output_dir
        
        # This config would hold settings like resolution and fps
        self.config = config if config is not None else {
            'resolution': (CAPTURE_WIDTH, CAPTURE_HEIGHT),
            'fps': 25,
            'name': 'main_cam'
        }
        # The fisheye corrector could also be passed in if needed by the recorder
        # For this example, we assume resolution is passed via config
        # self.corrector = fisheye_corrector 

    # --- Move start_recording into the class (no other changes needed inside) ---
    def start_recording(self):
        """Starts recording if not already in progress with robust error handling."""
        if self.is_recording:
            print(f"Camera {self.camera_id}: Already recording.")
            return

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        cam_name = self.config.get('name', f'cam{self.camera_id}').replace(" ", "_")
        output_filename = os.path.join(self.output_dir, f"{cam_name}_{timestamp}.mp4")
        
        width, height = self.config.get('resolution', (640, 480))
        fps = self.config.get('fps', 25)

        codecs_to_try = [
            ('mp4v', cv2.VideoWriter_fourcc(*'mp4v')),
            ('XVID', cv2.VideoWriter_fourcc(*'XVID')),
            ('H264', cv2.VideoWriter_fourcc(*'H264')),
            ('MJPG', cv2.VideoWriter_fourcc(*'MJPG')),
        ]
        
        self.video_writer = None
        self.current_output_file = output_filename
        
        for codec_name, fourcc in codecs_to_try:
            try:
                os.makedirs(os.path.dirname(output_filename), exist_ok=True)
                self.video_writer = cv2.VideoWriter(output_filename, fourcc, fps, (width, height))
                
                if self.video_writer and self.video_writer.isOpened():
                    self.is_recording = True
                    self.recording_stats = { 'frames_written': 0, 'write_errors': 0, 'codec_used': codec_name }
                    print(f"Camera {self.camera_id}: Started recording to {output_filename} using {codec_name} codec")
                    return
                else:
                    if self.video_writer: self.video_writer.release()
                    print(f"Camera {self.camera_id}: Failed to initialize with {codec_name} codec")
            except Exception as e:
                print(f"Camera {self.camera_id}: Exception with {codec_name} codec: {e}")
                if self.video_writer: self.video_writer.release()
        
        print(f"Camera {self.camera_id}: Failed to initialize video recording with any codec")

    # --- Move stop_recording into the class ---
    def stop_recording(self):
        """Stops recording if in progress with robust cleanup."""
        if not self.is_recording:
            return

        self.is_recording = False
        
        if self.video_writer:
            try:
                self.video_writer.release()
                print(f"Camera {self.camera_id}: Recording stopped. Stats: {self.recording_stats}")
                
                if os.path.exists(self.current_output_file) and os.path.getsize(self.current_output_file) == 0:
                    print(f"Camera {self.camera_id}: Video file is empty, removing it.")
                    os.remove(self.current_output_file)
                else:
                    print(f"Camera {self.camera_id}: Video file saved.")
            except Exception as e:
                print(f"Camera {self.camera_id}: Error during recording cleanup: {e}")
            finally:
                self.video_writer = None

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
    try:
        # subscribe to the DDS topic for head commands
        print(f"Initializing DDS on network interface: {DDS_NETWORK_INTERFACE}")
        ChannelFactoryInitialize(networkInterface=DDS_NETWORK_INTERFACE)
        sub = ChannelSubscriber(HEAD_COMMAND_TOPIC, HeadCommand)
        sub.Init(get_head_position)
        # 创建并启动摄像头捕获线程

        # 1. Create an instance of your new Recorder class
        my_recorder = Recorder()
        
        # 2. Pass the recorder instance to the capture thread
        capture_thread = threading.Thread(target=capture_thread_func, args=(my_recorder,))
        capture_thread.daemon = True
        capture_thread.start()

        # 3. Start the recording directly from the main thread.
        #    We no longer need a separate 'record_thread'.
        #    You could add a delay or trigger this based on some event if needed.
        time.sleep(2) # Give the camera a moment to initialize
        print("Starting recording...")
        my_recorder.start_recording()

        # 启动 Flask Web 服务器
        # 使用 use_reloader=False 避免主线程重启导致摄像头资源问题
        print(f"服务器正在启动，请在浏览器中访问 http://<你的IP地址>:58603")
        print(f"流媒体参数: {CAPTURE_WIDTH}x{CAPTURE_HEIGHT}, {TARGET_FPS}Hz, JPEG质量={JPEG_QUALITY}")
        app.run(host='0.0.0.0', port=58603, debug=False, threaded=True)

    except KeyboardInterrupt:
        print("stopping...")
    except Exception as e:
        print(f"发生错误: {e}")
        sys.exit(1)
    finally:
        if my_recorder.is_recording:
            my_recorder.stop_recording()
            print("录制已停止。")
        if 'sub' in locals():
            sub.Close()
        try:
            video_capture.release()
            print("摄像头已释放。")
        except Exception as e:
            print(f"释放摄像头时出错: {e}")
        sys.exit(0)
        if 'capture_thread' in locals() and capture_thread.is_alive():
            capture_thread.join(timeout=1)
