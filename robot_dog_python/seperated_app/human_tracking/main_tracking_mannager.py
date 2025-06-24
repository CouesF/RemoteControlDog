
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
# 定义视频源。修改为使用摄像头 0
VIDEO_SOURCE = 0

# 主检测模型 (e.g., yolov8n.pt)
DETECTION_MODEL_PATH = "yolov8n.pt" 

# Re-ID 模型，用于提取人物特征向量
# 这个模型路径应该和你的 botsort_custom.yaml 文件中的 'model' 字段一致
REID_MODEL_PATH = "/app/resources/yolo11n-cls.pt"

# 指向我们为 Re-ID 创建的自定义追踪器配置文件
TRACKER_CONFIG_PATH = "botsort_custom.yaml"

# --- 新增：持久化和识别配置 ---
# 存储已知人物特征的数据库文件
PERSON_DB_PATH = "person_database.json"
# 识别匹配的相似度阈值 (使用余弦相似度, 范围 0-1)
# 阈值越高，匹配要求越严格。0.85 是一个不错的起点。
REID_MATCH_THRESHOLD = 0.85 

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

# --- 新增：用于存储和识别人脸的全局变量 ---
# 存储从 person_database.json 加载的已知人物信息
known_people_db = []
# 实时存储当前帧中每个 track_id 对应的特征向量
# {track_id: feature_vector}
current_tracked_features = {}
# 用于保护数据库和特征字典的锁，因为它们会被多个线程访问
db_lock = threading.Lock()


# --- 优雅退出处理 ---
def signal_handler(sig, frame):
    """捕获Ctrl+C信号，并设置停止事件"""
    print("\n检测到退出信号 (Ctrl+C)... 正在优雅地关闭...")
    stop_event.set()

signal.signal(signal.SIGINT, signal_handler)


# --- 新增：计算特征向量之间的余弦相似度 ---
def cosine_similarity(v1, v2):
    """计算两个向量之间的余弦相似度"""
    if v1 is None or v2 is None:
        return 0.0
    # 确保向量是归一化的 numpy 数组
    v1 = np.array(v1)
    v2 = np.array(v2)
    dot_product = np.dot(v1, v2)
    norm_v1 = np.linalg.norm(v1)
    norm_v2 = np.linalg.norm(v2)
    
    if norm_v1 == 0 or norm_v2 == 0:
        return 0.0
        
    return dot_product / (norm_v1 * norm_v2)


# --- 新增：加载人物数据库 ---
def load_person_database():
    """从JSON文件加载已知人物数据库"""
    global known_people_db
    try:
        if os.path.exists(PERSON_DB_PATH):
            with open(PERSON_DB_PATH, 'r') as f:
                with db_lock:
                    known_people_db = json.load(f)
                print(f"成功从 {PERSON_DB_PATH} 加载了 {len(known_people_db)} 位已知人物。")
        else:
            print(f"数据库文件 {PERSON_DB_PATH} 不存在，将创建一个新的。")
            known_people_db = []
    except Exception as e:
        print(f"加载人物数据库时出错: {e}")
        known_people_db = []


# --- 更新：HTML模板，增加注册表单 ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>YOLOv8 持久化Re-ID 实时监控</title>
    <style>
        body { font-family: sans-serif; margin: 0; padding: 0; background-color: #f0f0f0; display: flex; }
        .main-container { display: flex; flex-direction: row; width: 100%; }
        .video-column { flex-grow: 1; padding: 1rem; }
        .controls-column { width: 350px; padding: 1rem; background-color: #fff; box-shadow: -2px 0 5px rgba(0,0,0,0.1); }
        h1, h2 { color: #333; text-align: center;}
        #video-container { 
            border: 5px solid #333; 
            display: inline-block;
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
            background-color: #000;
            max-width: 100%;
        }
        img { max-width: 100%; height: auto; display: block; }
        p { color: #666; text-align: center; }
        .form-group { margin-bottom: 1rem; }
        label { display: block; margin-bottom: 0.5rem; font-weight: bold; }
        input[type="text"], input[type="number"] { width: calc(100% - 20px); padding: 8px; border-radius: 4px; border: 1px solid #ccc; }
        button { width: 100%; padding: 10px; background-color: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 1rem; }
        button:hover { background-color: #0056b3; }
        #status-message { margin-top: 1rem; padding: 10px; border-radius: 4px; text-align: center; font-weight: bold; }
        .success { background-color: #d4edda; color: #155724; }
        .error { background-color: #f8d7da; color: #721c24; }
    </style>
</head>
<body>
    <div class="main-container">
        <div class="video-column">
            <h1>YOLOv8 持久化Re-ID 实时监控</h1>
            <div id="video-container">
                <img src="{{ url_for('video_feed') }}" width="960">
            </div>
            <p>正在从摄像头 {{ video_source }} 进行实时串流 (约 {{ fps }} FPS)。</p>
        </div>
        <div class="controls-column">
            <h2>注册新人物</h2>
            <p>在下方输入视频中人物的ID和姓名，将其保存到数据库中。</p>
            <form id="add-person-form">
                <div class="form-group">
                    <label for="track-id">追踪ID:</label>
                    <input type="number" id="track-id" name="track_id" required>
                </div>
                <div class="form-group">
                    <label for="person-name">姓名:</label>
                    <input type="text" id="person-name" name="person_name" required>
                </div>
                <button type="submit">保存人物</button>
            </form>
            <div id="status-message"></div>
        </div>
    </div>

    <script>
        document.getElementById('add-person-form').addEventListener('submit', function(e) {
            e.preventDefault(); // 阻止表单默认提交
            
            const trackId = document.getElementById('track-id').value;
            const personName = document.getElementById('person-name').value;
            const statusDiv = document.getElementById('status-message');

            fetch('/add_person', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    track_id: parseInt(trackId),
                    name: personName,
                }),
            })
            .then(response => response.json())
            .then(data => {
                statusDiv.textContent = data.message;
                if (data.status === 'success') {
                    statusDiv.className = 'success';
                    document.getElementById('add-person-form').reset(); // 成功后清空表单
                } else {
                    statusDiv.className = 'error';
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
    """主页，渲染HTML模板"""
    return render_template_string(HTML_TEMPLATE, video_source=VIDEO_SOURCE, fps=STREAM_FPS)

def generate_frames():
    """生成器函数，用于持续生成视频帧并控制帧率"""
    global output_frame, lock
    while not stop_event.is_set():
        with lock:
            if output_frame is None:
                time.sleep(0.01)
                continue
            
            (flag, encoded_image) = cv2.imencode(".jpg", output_frame)
            if not flag:
                continue

        yield(b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + 
              bytearray(encoded_image) + b'\r\n')
        
        time.sleep(1 / STREAM_FPS)

@app.route('/video_feed')
def video_feed():
    """视频流路由"""
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

# --- 新增：处理添加人物请求的 Flask 路由 ---
@app.route('/add_person', methods=['POST'])
def add_person():
    """处理来自网页的添加新人物的请求"""
    global known_people_db
    data = request.get_json()
    track_id = data.get('track_id')
    name = data.get('name')

    if not track_id or not name:
        return jsonify({'status': 'error', 'message': '缺少ID或姓名。'})

    with db_lock:
        # 检查姓名是否已存在
        if any(p['name'] == name for p in known_people_db):
            return jsonify({'status': 'error', 'message': f'姓名 "{name}" 已存在。'})

        # 从当前追踪的特征中获取该ID的特征向量
        feature_vector = current_tracked_features.get(track_id)
        if feature_vector is None:
            return jsonify({'status': 'error', 'message': f'未在当前帧中找到ID {track_id}。请确保ID可见。'})
        
        # 添加新人物到数据库
        known_people_db.append({
            'name': name,
            'feature_vector': feature_vector.tolist() # 转换为列表以便JSON序列化
        })

        # 将更新后的数据库写回文件
        try:
            with open(PERSON_DB_PATH, 'w') as f:
                json.dump(known_people_db, f, indent=4)
            print(f"成功添加新人物: {name} (ID: {track_id})，数据库已更新。")
            return jsonify({'status': 'success', 'message': f'成功保存人物: {name}！'})
        except Exception as e:
            print(f"写入数据库文件时出错: {e}")
            return jsonify({'status': 'error', 'message': '保存到数据库文件失败。'})


# --- YOLOv8 视频处理函数 (核心逻辑修改) ---
def run_yolo_tracking():
    """
    包含主要YOLOv8处理逻辑的函数。
    新增了加载数据库、特征提取、身份识别和手动绘制的功能。
    """
    global output_frame, lock, current_tracked_features

    print(f"正在加载检测模型: {DETECTION_MODEL_PATH}")
    try:
        model = YOLO(DETECTION_MODEL_PATH)
        # 专门加载 Re-ID 模型用于提取特征
        reid_model = YOLO(REID_MODEL_PATH)
    except Exception as e:
        print(f"错误: 无法加载模型。请检查路径和文件。错误信息: {e}")
        stop_event.set()
        return

    print(f"正在打开视频源: {VIDEO_SOURCE}")
    cap = cv2.VideoCapture(VIDEO_SOURCE)
    if not cap.isOpened():
        print(f"错误: 无法打开视频源 {VIDEO_SOURCE}")
        stop_event.set()
        return

    track_history = defaultdict(lambda: [])
    print("模型和摄像头已准备就绪，开始处理帧...")

    while not stop_event.is_set():
        success, frame = cap.read()
        if not success:
            print("无法从视频源读取帧，将终止处理。")
            break

        frame = cv2.flip(frame, 0)

        # 运行 YOLOv8 追踪
        results = model.track(frame, persist=True, tracker=TRACKER_CONFIG_PATH, classes=0, conf=0.4, iou=0.5)
        
        annotated_frame = frame.copy() # 我们将手动绘制，所以从原始帧开始

        if results and results[0].boxes is not None and results[0].boxes.id is not None:
            boxes = results[0].boxes.xyxy.cpu().numpy().astype(int)
            track_ids = results[0].boxes.id.int().cpu().tolist()
            
            # 用于存储当前帧的识别结果 {track_id: "name"}
            frame_identities = {}
            # 用于更新全局特征字典的临时字典
            temp_current_features = {}

            # --- 1. 提取当前帧所有人的特征，并尝试识别 ---
            for box, track_id in zip(boxes, track_ids):
                x1, y1, x2, y2 = box
                # 裁剪出人物图像
                person_crop = frame[y1:y2, x1:x2]
                
                if person_crop.size == 0:
                    continue

                # 提取特征向量
                reid_results = reid_model(person_crop, verbose=False)
                current_feature = reid_results[0].obb.cls if reid_results[0].obb is not None else reid_results[0].probs.data
                current_feature = current_feature.cpu().numpy()
                
                temp_current_features[track_id] = current_feature

                # --- 与数据库中的已知人物进行比对 ---
                best_match_name = None
                best_match_score = REID_MATCH_THRESHOLD # 只有高于此阈值的才算匹配
                
                with db_lock:
                    for person in known_people_db:
                        similarity = cosine_similarity(current_feature, person['feature_vector'])
                        if similarity > best_match_score:
                            best_match_score = similarity
                            best_match_name = person['name']
                
                if best_match_name:
                    frame_identities[track_id] = best_match_name
            
            # --- 安全地更新全局的特征字典 ---
            with db_lock:
                current_tracked_features = temp_current_features

            # --- 2. 绘制边界框、标签和轨迹线 ---
            for box, track_id in zip(boxes, track_ids):
                x1, y1, x2, y2 = box
                
                # 确定标签文本（姓名或ID）和颜色
                label_name = frame_identities.get(track_id)
                if label_name:
                    label = f"{label_name}"
                    color = (0, 255, 0) # 绿色表示已识别
                else:
                    label = f"ID: {track_id}"
                    color = (255, 0, 0) # 蓝色表示未识别

                # 绘制边界框
                cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), color, 2)
                # 绘制标签背景
                (w, h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
                cv2.rectangle(annotated_frame, (x1, y1 - 20), (x1 + w, y1), color, -1)
                # 绘制标签文本
                cv2.putText(annotated_frame, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

                # 绘制轨迹线
                center_x, center_y = (x1 + x2) // 2, (y1 + y2) // 2
                track = track_history[track_id]
                track.append((float(center_x), float(center_y)))
                if len(track) > 30:
                    track.pop(0)

                points = np.hstack(track).astype(np.int32).reshape((-1, 1, 2))
                cv2.polylines(annotated_frame, [points], isClosed=False, color=(230, 230, 230), thickness=5)

        with lock:
            output_frame = annotated_frame.copy()

    cap.release()
    print("视频处理线程已停止，摄像头已释放。")


# --- 主程序入口 ---
if __name__ == '__main__':
    # 在启动时加载人物数据库
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