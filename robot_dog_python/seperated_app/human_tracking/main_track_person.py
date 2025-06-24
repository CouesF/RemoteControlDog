import cv2
from collections import defaultdict
import numpy as np
from ultralytics import YOLO
from flask import Flask, Response, render_template_string, request, jsonify
import threading
import time
import signal
import json
import os

# --- 配置区 ---
VIDEO_SOURCE = 0
DETECTION_MODEL_PATH = "yolo11n.pt"
REID_MODEL_PATH = "/app/resources/yolo11n-cls.pt"
TRACKER_CONFIG_PATH = "botsort_custom.yaml"

# --- 持久化和识别配置 (调整) ---
PERSON_DB_PATH = "/app/database/person_database_gallery.json" # 使用新的数据库文件名
# 调整阈值。因为我们会对比多个向量，可以适当提高阈值以增加置信度
REID_MATCH_THRESHOLD = 0.88 

# Web服务器配置
HOST = '0.0.0.0'
PORT = 8080
STREAM_FPS = 15
# --- 配置区结束 ---

# --- 全局变量和线程控制 ---
app = Flask(__name__)
output_frame = None
lock = threading.Lock()
stop_event = threading.Event()

# --- 用于存储和识别人脸的全局变量 (调整) ---
# 数据库现在将存储一个向量列表: [{'name': 'Alice', 'feature_vectors': [[...], [...]]}]
known_people_db = []
current_tracked_features = {}
db_lock = threading.Lock()

# --- 优雅退出处理 ---
def signal_handler(sig, frame):
    print("\n检测到退出信号 (Ctrl+C)... 正在优雅地关闭...")
    stop_event.set()

signal.signal(signal.SIGINT, signal_handler)

# --- 辅助函数 ---
def cosine_similarity(v1, v2):
    if v1 is None or v2 is None:
        return 0.0
    v1 = np.array(v1)
    v2 = np.array(v2)
    dot_product = np.dot(v1, v2)
    norm_v1 = np.linalg.norm(v1)
    norm_v2 = np.linalg.norm(v2)
    if norm_v1 == 0 or norm_v2 == 0:
        return 0.0
    return dot_product / (norm_v1 * norm_v2)

# --- 数据库加载 (调整以适应新结构) ---
def load_person_database():
    global known_people_db
    try:
        if os.path.exists(PERSON_DB_PATH):
            with open(PERSON_DB_PATH, 'r') as f:
                with db_lock:
                    known_people_db = json.load(f)
                    # *** 向后兼容性检查 ***
                    # 检查旧格式并转换为新格式
                    for person in known_people_db:
                        if 'feature_vector' in person:
                            print(f"检测到旧版数据库格式，正在为 '{person['name']}' 进行转换...")
                            person['feature_vectors'] = [person.pop('feature_vector')]
                print(f"成功从 {PERSON_DB_PATH} 加载了 {len(known_people_db)} 位已知人物。")
        else:
            print(f"数据库文件 {PERSON_DB_PATH} 不存在，将创建一个新的。")
            known_people_db = []
    except Exception as e:
        print(f"加载人物数据库时出错: {e}")
        known_people_db = []

# --- HTML模板 (调整以提供更好的用户反馈) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>YOLOv8 持久化Re-ID 监控 (多向量增强版)</title>
    <style>
        body { font-family: sans-serif; margin: 0; padding: 0; background-color: #f0f0f0; display: flex; }
        .main-container { display: flex; flex-direction: row; width: 100%; }
        .video-column { flex-grow: 1; padding: 1rem; }
        .controls-column { width: 350px; padding: 1rem; background-color: #fff; box-shadow: -2px 0 5px rgba(0,0,0,0.1); }
        h1, h2 { color: #333; text-align: center;}
        #video-container { border: 5px solid #333; display: inline-block; box-shadow: 0 4px 8px rgba(0,0,0,0.1); background-color: #000; max-width: 100%;}
        img { max-width: 100%; height: auto; display: block; }
        p { color: #666; text-align: center; }
        .form-group { margin-bottom: 1rem; }
        label { display: block; margin-bottom: 0.5rem; font-weight: bold; }
        input[type="text"], input[type="number"] { width: calc(100% - 20px); padding: 8px; border-radius: 4px; border: 1px solid #ccc; }
        button { width: 100%; padding: 10px; background-color: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 1rem; }
        button:hover { background-color: #0056b3; }
        #status-message { margin-top: 1rem; padding: 10px; border-radius: 4px; text-align: center; font-weight: bold; visibility: hidden; }
        .success { background-color: #d4edda; color: #155724; visibility: visible; }
        .updated { background-color: #cce5ff; color: #004085; visibility: visible; }
        .error { background-color: #f8d7da; color: #721c24; visibility: visible; }
    </style>
</head>
<body>
    <div class="main-container">
        <div class="video-column">
            <h1>YOLOv8 持久化Re-ID 监控 (多向量增强版)</h1>
            <div id="video-container">
                <img src="{{ url_for('video_feed') }}" width="960">
            </div>
            <p>正在从摄像头 {{ video_source }} 进行实时串流 (约 {{ fps }} FPS)。</p>
        </div>
        <div class="controls-column">
            <h2>注册或更新人物</h2>
            <p>输入ID和姓名。如果姓名已存在，将为其添加一个新的外观特征。</p>
            <form id="add-person-form">
                <div class="form-group">
                    <label for="track-id">追踪ID:</label>
                    <input type="number" id="track-id" name="track_id" required>
                </div>
                <div class="form-group">
                    <label for="person-name">姓名:</label>
                    <input type="text" id="person-name" name="person_name" required>
                </div>
                <button type="submit">保存/更新人物</button>
            </form>
            <div id="status-message"></div>
        </div>
    </div>

    <script>
        document.getElementById('add-person-form').addEventListener('submit', function(e) {
            e.preventDefault();
            const trackId = document.getElementById('track-id').value;
            const personName = document.getElementById('person-name').value;
            const statusDiv = document.getElementById('status-message');

            fetch('/add_person', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ track_id: parseInt(trackId), name: personName }),
            })
            .then(response => response.json())
            .then(data => {
                statusDiv.textContent = data.message;
                statusDiv.className = data.status; // 'success', 'updated', or 'error'
                if (data.status.startsWith('success')) {
                    document.getElementById('add-person-form').reset();
                }
            })
            .catch(error => {
                console.error('Error:', error);
                statusDiv.textContent = '发生网络错误，请检查后台服务。';
                statusDiv.className = 'error';
            });
        });
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE, video_source=VIDEO_SOURCE, fps=STREAM_FPS)

def generate_frames():
    global output_frame, lock
    while not stop_event.is_set():
        with lock:
            if output_frame is None:
                time.sleep(0.01)
                continue
            (flag, encoded_image) = cv2.imencode(".jpg", output_frame)
            if not flag:
                continue
        yield(b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + bytearray(encoded_image) + b'\r\n')
        time.sleep(1 / STREAM_FPS)

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

# --- Flask 路由 (核心逻辑修改) ---
@app.route('/add_person', methods=['POST'])
def add_person():
    global known_people_db
    data = request.get_json()
    track_id = data.get('track_id')
    name = data.get('name')

    if not track_id or not name:
        return jsonify({'status': 'error', 'message': '缺少ID或姓名。'})

    with db_lock:
        feature_vector = current_tracked_features.get(track_id)
        if feature_vector is None:
            return jsonify({'status': 'error', 'message': f'未在当前帧中找到ID {track_id}。请确保ID可见。'})

        person_to_update = None
        for person in known_people_db:
            if person['name'] == name:
                person_to_update = person
                break
        
        # --- 核心逻辑：更新或创建 ---
        if person_to_update:
            # 姓名已存在 -> 更新，添加新的特征向量
            person_to_update['feature_vectors'].append(feature_vector.tolist())
            message = f"成功更新 '{name}' 的外观信息！"
            status = "updated"
        else:
            # 姓名不存在 -> 创建新条目
            known_people_db.append({
                'name': name,
                'feature_vectors': [feature_vector.tolist()]
            })
            message = f"成功保存新人物: {name}！"
            status = "success"

        try:
            with open(PERSON_DB_PATH, 'w') as f:
                json.dump(known_people_db, f, indent=4)
            print(f"数据库已更新。状态: {status}, 人物: {name}")
            return jsonify({'status': status, 'message': message})
        except Exception as e:
            print(f"写入数据库文件时出错: {e}")
            return jsonify({'status': 'error', 'message': '保存到数据库文件失败。'})

# --- YOLOv8 视频处理函数 (核心识别逻辑修改) ---
def run_yolo_tracking():
    global output_frame, lock, current_tracked_features

    print(f"正在加载模型...")
    try:
        model = YOLO(DETECTION_MODEL_PATH)
        reid_model = YOLO(REID_MODEL_PATH)
    except Exception as e:
        print(f"错误: 无法加载模型: {e}")
        stop_event.set(); return

    print(f"正在打开视频源: {VIDEO_SOURCE}")
    cap = cv2.VideoCapture(VIDEO_SOURCE)
    if not cap.isOpened():
        print(f"错误: 无法打开视频源 {VIDEO_SOURCE}")
        stop_event.set(); return

    track_history = defaultdict(lambda: [])
    print("模型和摄像头已准备就绪，开始处理帧...")

    while not stop_event.is_set():
        success, frame = cap.read()
        if not success:
            print("无法从视频源读取帧，将终止处理。"); break

        frame = cv2.flip(frame, 0)
        results = model.track(frame, persist=True, tracker=TRACKER_CONFIG_PATH, classes=0, conf=0.4, iou=0.5)
        annotated_frame = frame.copy()

        if results and results[0].boxes is not None and results[0].boxes.id is not None:
            boxes = results[0].boxes.xyxy.cpu().numpy().astype(int)
            track_ids = results[0].boxes.id.int().cpu().tolist()
            
            frame_identities = {}
            temp_current_features = {}

            # 1. 提取当前帧所有人的特征
            for box, track_id in zip(boxes, track_ids):
                x1, y1, x2, y2 = box
                person_crop = frame[y1:y2, x1:x2]
                if person_crop.size == 0: continue

                reid_results = reid_model(person_crop, verbose=False)
                current_feature = reid_results[0].obb.cls if reid_results[0].obb is not None else reid_results[0].probs.data
                current_feature = current_feature.cpu().numpy()
                temp_current_features[track_id] = current_feature

                # --- 核心识别逻辑：与数据库中的向量 gallery 对比 ---
                best_match_name = None
                highest_similarity = REID_MATCH_THRESHOLD # 初始化为阈值

                with db_lock:
                    for person in known_people_db:
                        # 将当前特征与该人物 gallery 中的每个向量进行比较
                        for known_vector in person['feature_vectors']:
                            similarity = cosine_similarity(current_feature, known_vector)
                            # 如果找到一个相似度更高的匹配，则更新最佳匹配
                            if similarity > highest_similarity:
                                highest_similarity = similarity
                                best_match_name = person['name']
                
                if best_match_name:
                    frame_identities[track_id] = (best_match_name, highest_similarity)

            with db_lock:
                current_tracked_features = temp_current_features

            # 2. 绘制边界框和标签
            for box, track_id in zip(boxes, track_ids):
                x1, y1, x2, y2 = box
                
                identity_info = frame_identities.get(track_id)
                if identity_info:
                    name, score = identity_info
                    label = f"{name} ({score:.2f})"
                    color = (0, 255, 0)
                else:
                    label = f"ID: {track_id}"
                    color = (255, 0, 0)

                cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), color, 2)
                (w, h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
                cv2.rectangle(annotated_frame, (x1, y1 - 20), (x1 + w, y1), color, -1)
                cv2.putText(annotated_frame, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

                # 绘制轨迹
                center_x, center_y = (x1 + x2) // 2, (y1 + y2) // 2
                track = track_history[track_id]
                track.append((float(center_x), float(center_y)))
                if len(track) > 30: track.pop(0)
                points = np.hstack(track).astype(np.int32).reshape((-1, 1, 2))
                cv2.polylines(annotated_frame, [points], isClosed=False, color=(230, 230, 230), thickness=5)

        with lock:
            output_frame = annotated_frame.copy()

    cap.release()
    print("视频处理线程已停止，摄像头已释放。")

# --- 主程序入口 ---
if __name__ == '__main__':
    load_person_database()

    yolo_thread = threading.Thread(target=run_yolo_tracking)
    yolo_thread.start()

    flask_thread = threading.Thread(target=lambda: app.run(host=HOST, port=PORT, debug=False), daemon=True)
    flask_thread.start()

    print(f"服务器已启动，请在浏览器中打开 http://{HOST}:{PORT}")
    print("按 Ctrl+C 优雅地关闭服务器。")

    try:
        stop_event.wait()
    except KeyboardInterrupt:
        print("\n在主线程中检测到 KeyboardInterrupt，开始关闭...")
        stop_event.set()

    print("Flask服务器正在关闭... 正在等待YOLO处理线程结束...")
    yolo_thread.join()
    print("程序已成功退出。")