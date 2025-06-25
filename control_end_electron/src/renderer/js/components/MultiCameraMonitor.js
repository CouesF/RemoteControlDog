// 多摄像头监控组件 - 支持同时显示多个摄像头画面
import BaseComponent from './BaseComponent.js';
import { getUDPManager } from './UDPConnectionManager.js';
import { EVENTS } from '../utils/constants.js';
import Logger from '../utils/logger.js';

export default class MultiCameraMonitor extends BaseComponent {
    constructor(containerId, options = {}) {
        super(containerId);
        
        this.options = {
            maxCameras: 3,
            autoLayout: true,
            showStats: true,
            showControls: true,
            defaultQuality: 80,
            ...options
        };
        
        this.cameras = new Map(); // 摄像头实例
        this.cameraElements = new Map(); // DOM元素
        this.isActive = false;
        this.udpManager = null;
        this.cameraConnection = null;
        
        this.stats = {
            totalFrames: 0,
            droppedFrames: 0,
            averageFPS: 0,
            lastUpdateTime: Date.now()
        };
        
        this.frameCounters = new Map(); // 每个摄像头的帧计数
    }

    async doRender() {
        if (!this.container) {
            throw new Error('Multi camera monitor container not found');
        }

        this.container.innerHTML = this.getTemplate();
        this.addStyles();
        this.initializeElements();
        
        // 初始化UDP连接
        await this.initializeUDPConnection();
    }

    getTemplate() {
        return `
            <div class="multi-camera-monitor">
                <div class="camera-controls" ${this.options.showControls ? '' : 'style="display: none;"'}>
                    <div class="control-group">
                        <h6>摄像头控制</h6>
                        <div class="btn-group" role="group">
                            <button id="start-cameras-btn" class="btn btn-success btn-sm">
                                <i class="fas fa-play"></i> 启动
                            </button>
                            <button id="stop-cameras-btn" class="btn btn-danger btn-sm">
                                <i class="fas fa-stop"></i> 停止
                            </button>
                            <button id="refresh-cameras-btn" class="btn btn-secondary btn-sm">
                                <i class="fas fa-sync"></i> 刷新
                            </button>
                        </div>
                    </div>
                    
                    <div class="camera-selection">
                        <label for="camera-select">选择摄像头:</label>
                        <select id="camera-select" class="form-control form-control-sm" multiple>
                            <!-- 摄像头选项将动态添加 -->
                        </select>
                    </div>
                    
                    <div class="layout-controls">
                        <label for="layout-select">布局:</label>
                        <select id="layout-select" class="form-control form-control-sm">
                            <option value="auto">自动</option>
                            <option value="grid">网格</option>
                            <option value="horizontal">水平</option>
                            <option value="vertical">垂直</option>
                        </select>
                    </div>
                </div>
                
                <div class="camera-grid" id="camera-grid">
                    <!-- 摄像头画面将动态添加 -->
                </div>
                
                <div class="camera-stats" ${this.options.showStats ? '' : 'style="display: none;"'}>
                    <div class="stats-content" id="stats-content">
                        <div class="stat-item">
                            <span class="stat-label">连接状态:</span>
                            <span id="connection-status" class="stat-value">未连接</span>
                        </div>
                        <div class="stat-item">
                            <span class="stat-label">总帧数:</span>
                            <span id="total-frames" class="stat-value">0</span>
                        </div>
                        <div class="stat-item">
                            <span class="stat-label">平均FPS:</span>
                            <span id="average-fps" class="stat-value">0</span>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    addStyles() {
        const styleId = 'multi-camera-monitor-styles';
        if (document.getElementById(styleId)) return;

        const style = document.createElement('style');
        style.id = styleId;
        style.textContent = `
            .multi-camera-monitor {
                display: flex;
                flex-direction: column;
                height: 100%;
                background: #f8f9fa;
                border-radius: 8px;
                overflow: hidden;
            }
            
            .camera-controls {
                display: flex;
                align-items: center;
                gap: 20px;
                padding: 15px;
                background: white;
                border-bottom: 1px solid #e9ecef;
                flex-wrap: wrap;
            }
            
            .control-group {
                display: flex;
                align-items: center;
                gap: 10px;
            }
            
            .control-group h6 {
                margin: 0;
                font-weight: 600;
                color: #495057;
            }
            
            .camera-selection, .layout-controls {
                display: flex;
                align-items: center;
                gap: 8px;
            }
            
            .camera-selection label, .layout-controls label {
                margin: 0;
                font-size: 0.875rem;
                font-weight: 500;
                color: #6c757d;
            }
            
            .camera-selection select, .layout-controls select {
                min-width: 120px;
            }
            
            .camera-grid {
                flex: 1;
                display: grid;
                gap: 10px;
                padding: 15px;
                overflow: auto;
            }
            
            .camera-grid.layout-auto {
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            }
            
            .camera-grid.layout-grid {
                grid-template-columns: repeat(2, 1fr);
            }
            
            .camera-grid.layout-horizontal {
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                grid-template-rows: 1fr;
            }
            
            .camera-grid.layout-vertical {
                grid-template-columns: 1fr;
                grid-template-rows: repeat(auto-fit, minmax(200px, 1fr));
            }
            
            .camera-item {
                background: white;
                border-radius: 8px;
                overflow: hidden;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                display: flex;
                flex-direction: column;
                min-height: 200px;
            }
            
            .camera-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 10px 15px;
                background: #f8f9fa;
                border-bottom: 1px solid #e9ecef;
            }
            
            .camera-title {
                font-weight: 600;
                color: #495057;
                margin: 0;
            }
            
            .camera-status {
                display: flex;
                align-items: center;
                gap: 5px;
                font-size: 0.75rem;
            }
            
            .status-dot {
                width: 8px;
                height: 8px;
                border-radius: 50%;
                background: #dc3545;
            }
            
            .status-dot.active {
                background: #28a745;
                animation: pulse 2s infinite;
            }
            
            .camera-content {
                flex: 1;
                display: flex;
                align-items: center;
                justify-content: center;
                position: relative;
                background: #000;
            }
            
            .camera-video {
                max-width: 100%;
                max-height: 100%;
                object-fit: contain;
            }
            
            .camera-placeholder {
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                color: #6c757d;
                text-align: center;
                padding: 20px;
            }
            
            .camera-placeholder i {
                font-size: 3rem;
                margin-bottom: 10px;
                opacity: 0.5;
            }
            
            .camera-info {
                padding: 8px 15px;
                background: #f8f9fa;
                border-top: 1px solid #e9ecef;
                font-size: 0.75rem;
                color: #6c757d;
            }
            
            .camera-info-item {
                display: inline-block;
                margin-right: 15px;
            }
            
            .camera-stats {
                padding: 10px 15px;
                background: white;
                border-top: 1px solid #e9ecef;
            }
            
            .stats-content {
                display: flex;
                gap: 20px;
                flex-wrap: wrap;
            }
            
            .stat-item {
                display: flex;
                align-items: center;
                gap: 5px;
                font-size: 0.875rem;
            }
            
            .stat-label {
                color: #6c757d;
                font-weight: 500;
            }
            
            .stat-value {
                color: #495057;
                font-weight: 600;
            }
            
            .camera-overlay {
                position: absolute;
                top: 10px;
                right: 10px;
                background: rgba(0,0,0,0.7);
                color: white;
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 0.75rem;
                font-family: monospace;
            }
            
            @keyframes pulse {
                0% { opacity: 1; }
                50% { opacity: 0.5; }
                100% { opacity: 1; }
            }
            
            .btn-group .btn {
                margin-right: 5px;
            }
            
            .btn-group .btn:last-child {
                margin-right: 0;
            }
            
            .loading-spinner {
                display: inline-block;
                width: 20px;
                height: 20px;
                border: 3px solid #f3f3f3;
                border-top: 3px solid #007bff;
                border-radius: 50%;
                animation: spin 1s linear infinite;
            }
            
            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
        `;
        document.head.appendChild(style);
    }

    initializeElements() {
        this.elements = {
            startBtn: this.querySelector('#start-cameras-btn'),
            stopBtn: this.querySelector('#stop-cameras-btn'),
            refreshBtn: this.querySelector('#refresh-cameras-btn'),
            cameraSelect: this.querySelector('#camera-select'),
            layoutSelect: this.querySelector('#layout-select'),
            cameraGrid: this.querySelector('#camera-grid'),
            connectionStatus: this.querySelector('#connection-status'),
            totalFrames: this.querySelector('#total-frames'),
            averageFPS: this.querySelector('#average-fps')
        };
    }

    setupEventListeners() {
        // 控制按钮事件
        this.addEventListener(this.elements.startBtn, 'click', () => {
            this.startMonitoring();
        });

        this.addEventListener(this.elements.stopBtn, 'click', () => {
            this.stopMonitoring();
        });

        this.addEventListener(this.elements.refreshBtn, 'click', () => {
            this.refreshCameraList();
        });

        // 摄像头选择事件
        this.addEventListener(this.elements.cameraSelect, 'change', () => {
            this.updateSelectedCameras();
        });

        // 布局选择事件
        this.addEventListener(this.elements.layoutSelect, 'change', () => {
            this.updateLayout();
        });

        // UDP连接事件
        this.onEvent(EVENTS.UDP_CONNECTION_ESTABLISHED, (data) => {
            if (data.connectionId === 'camera') {
                this.onCameraConnectionEstablished();
            }
        });

        this.onEvent(EVENTS.UDP_MESSAGE_RECEIVED, (data) => {
            if (data.connectionId === 'camera') {
                this.handleCameraMessage(data.message);
            }
        });

        this.onEvent(EVENTS.UDP_CONNECTION_STATUS_CHANGED, (data) => {
            if (data.connectionId === 'camera') {
                this.updateConnectionStatus(data.isConnected);
            }
        });
    }

    async initializeUDPConnection() {
        try {
            this.udpManager = getUDPManager();
            
            // 创建摄像头连接
            this.cameraConnection = await this.udpManager.createConnection('camera');
            
            // 注册消息处理器
            this.cameraConnection.registerMessageHandler('video_frame', (message) => {
                this.handleVideoFrame(message);
            });

            this.cameraConnection.registerMessageHandler('camera_list', (message) => {
                this.handleCameraList(message);
            });

            this.cameraConnection.registerMessageHandler('screenshot_captured', (message) => {
                this.handleScreenshot(message);
            });

            Logger.info('摄像头UDP连接初始化完成');
            
        } catch (error) {
            Logger.error('摄像头UDP连接初始化失败:', error);
            this.updateConnectionStatus(false);
        }
    }

    async startMonitoring() {
        if (this.isActive) {
            Logger.warn('摄像头监控已在运行');
            return;
        }

        try {
            this.isActive = true;
            this.elements.startBtn.disabled = true;
            this.elements.startBtn.innerHTML = '<span class="loading-spinner"></span> 启动中...';

            // 获取摄像头列表
            await this.refreshCameraList();

            // 订阅选中的摄像头
            const selectedCameras = this.getSelectedCameras();
            if (selectedCameras.length > 0) {
                await this.subscribeToCameras(selectedCameras);
            }

            // 开始统计更新
            this.startStatsUpdate();

            this.elements.startBtn.innerHTML = '<i class="fas fa-play"></i> 启动';
            this.elements.startBtn.disabled = false;
            this.elements.stopBtn.disabled = false;

            Logger.info('摄像头监控已启动');

        } catch (error) {
            Logger.error('启动摄像头监控失败:', error);
            this.isActive = false;
            this.elements.startBtn.innerHTML = '<i class="fas fa-play"></i> 启动';
            this.elements.startBtn.disabled = false;
        }
    }

    async stopMonitoring() {
        if (!this.isActive) {
            Logger.warn('摄像头监控未在运行');
            return;
        }

        try {
            this.isActive = false;
            this.elements.stopBtn.disabled = true;

            // 取消订阅
            await this.unsubscribeFromCameras();

            // 停止统计更新
            this.stopStatsUpdate();

            // 清理摄像头显示
            this.clearCameraDisplays();

            this.elements.startBtn.disabled = false;
            this.elements.stopBtn.disabled = true;

            Logger.info('摄像头监控已停止');

        } catch (error) {
            Logger.error('停止摄像头监控失败:', error);
        }
    }

    async refreshCameraList() {
        try {
            if (!this.cameraConnection || !this.cameraConnection.isConnected) {
                Logger.warn('摄像头连接未建立，无法刷新摄像头列表');
                return;
            }

            // 请求摄像头列表
            await this.cameraConnection.sendMessage({
                request_type: 'get_camera_list'
            });

        } catch (error) {
            Logger.error('刷新摄像头列表失败:', error);
        }
    }

    handleCameraList(message) {
        if (message.status !== 'success') {
            Logger.error('获取摄像头列表失败:', message.message);
            return;
        }

        const cameras = message.cameras || [];
        this.updateCameraSelect(cameras);
        Logger.info(`获取到 ${cameras.length} 个摄像头`);
    }

    updateCameraSelect(cameras) {
        const select = this.elements.cameraSelect;
        select.innerHTML = '';

        cameras.forEach(camera => {
            const option = document.createElement('option');
            option.value = camera.camera_id;
            option.textContent = `${camera.name} (${camera.resolution[0]}x${camera.resolution[1]})`;
            option.title = `FPS: ${camera.fps}, 状态: ${camera.is_active ? '活跃' : '非活跃'}`;
            
            if (camera.is_active) {
                option.selected = true;
            }
            
            select.appendChild(option);
        });
    }

    getSelectedCameras() {
        const select = this.elements.cameraSelect;
        const selected = [];
        
        for (const option of select.selectedOptions) {
            selected.push(parseInt(option.value));
        }
        
        return selected;
    }

    async subscribeToCameras(cameraIds) {
        try {
            await this.cameraConnection.sendMessage({
                request_type: 'subscribe',
                camera_ids: cameraIds,
                session_id: this.cameraConnection.id
            });

            // 创建摄像头显示元素
            this.createCameraDisplays(cameraIds);

        } catch (error) {
            Logger.error('订阅摄像头失败:', error);
        }
    }

    async unsubscribeFromCameras() {
        try {
            if (this.cameraConnection && this.cameraConnection.isConnected) {
                await this.cameraConnection.sendMessage({
                    request_type: 'unsubscribe'
                });
            }
        } catch (error) {
            Logger.error('取消订阅摄像头失败:', error);
        }
    }

    createCameraDisplays(cameraIds) {
        const grid = this.elements.cameraGrid;
        grid.innerHTML = '';

        cameraIds.forEach(cameraId => {
            const cameraElement = this.createCameraElement(cameraId);
            grid.appendChild(cameraElement);
            this.cameraElements.set(cameraId, cameraElement);
            
            // 初始化帧计数器
            this.frameCounters.set(cameraId, {
                count: 0,
                lastTime: Date.now(),
                fps: 0
            });
        });

        this.updateLayout();
    }

    createCameraElement(cameraId) {
        const element = document.createElement('div');
        element.className = 'camera-item';
        element.innerHTML = `
            <div class="camera-header">
                <h6 class="camera-title">摄像头 ${cameraId}</h6>
                <div class="camera-status">
                    <div class="status-dot" id="status-dot-${cameraId}"></div>
                    <span id="status-text-${cameraId}">等待连接</span>
                </div>
            </div>
            <div class="camera-content" id="camera-content-${cameraId}">
                <div class="camera-placeholder">
                    <i class="fas fa-video-slash"></i>
                    <p>等待视频流...</p>
                </div>
                <div class="camera-overlay" id="camera-overlay-${cameraId}" style="display: none;">
                    FPS: <span id="fps-${cameraId}">0</span>
                </div>
            </div>
            <div class="camera-info">
                <span class="camera-info-item">分辨率: <span id="resolution-${cameraId}">-</span></span>
                <span class="camera-info-item">质量: <span id="quality-${cameraId}">-</span></span>
                <span class="camera-info-item">帧数: <span id="frame-count-${cameraId}">0</span></span>
            </div>
        `;
        return element;
    }

    handleVideoFrame(message) {
        const cameraId = message.camera_id;
        const frameData = message.data;
        
        if (!this.cameraElements.has(cameraId)) {
            return;
        }

        try {
            // 更新帧计数和FPS
            this.updateFrameStats(cameraId);

            // 更新视频显示
            this.updateVideoDisplay(cameraId, frameData, message);

            // 更新摄像头信息
            this.updateCameraInfo(cameraId, message);

            // 更新状态
            this.updateCameraStatus(cameraId, true);

        } catch (error) {
            Logger.error(`处理摄像头 ${cameraId} 视频帧失败:`, error);
            this.stats.droppedFrames++;
        }
    }

    updateFrameStats(cameraId) {
        const counter = this.frameCounters.get(cameraId);
        if (!counter) return;

        counter.count++;
        this.stats.totalFrames++;

        const now = Date.now();
        const timeDiff = now - counter.lastTime;

        if (timeDiff >= 1000) { // 每秒更新一次FPS
            counter.fps = Math.round((counter.count * 1000) / timeDiff);
            counter.count = 0;
            counter.lastTime = now;

            // 更新FPS显示
            const fpsElement = document.getElementById(`fps-${cameraId}`);
            if (fpsElement) {
                fpsElement.textContent = counter.fps;
            }
        }
    }

    updateVideoDisplay(cameraId, frameData, message) {
        const contentElement = document.getElementById(`camera-content-${cameraId}`);
        if (!contentElement) return;

        // 创建或更新video元素
        let videoElement = contentElement.querySelector('.camera-video');
        if (!videoElement) {
            videoElement = document.createElement('img');
            videoElement.className = 'camera-video';
            
            // 移除placeholder
            const placeholder = contentElement.querySelector('.camera-placeholder');
            if (placeholder) {
                placeholder.remove();
            }
            
            contentElement.appendChild(videoElement);
            
            // 显示overlay
            const overlay = document.getElementById(`camera-overlay-${cameraId}`);
            if (overlay) {
                overlay.style.display = 'block';
            }
        }

        // 更新图像数据
        videoElement.src = `data:image/jpeg;base64,${frameData}`;
    }

    updateCameraInfo(cameraId, message) {
        const resolutionElement = document.getElementById(`resolution-${cameraId}`);
        const qualityElement = document.getElementById(`quality-${cameraId}`);
        const frameCountElement = document.getElementById(`frame-count-${cameraId}`);

        if (resolutionElement && message.resolution) {
            resolutionElement.textContent = `${message.resolution[0]}x${message.resolution[1]}`;
        }

        if (qualityElement && message.quality) {
            qualityElement.textContent = `${message.quality}%`;
        }

        if (frameCountElement) {
            const counter = this.frameCounters.get(cameraId);
            frameCountElement.textContent = counter ? counter.count : 0;
        }
    }

    updateCameraStatus(cameraId, isActive) {
        const statusDot = document.getElementById(`status-dot-${cameraId}`);
        const statusText = document.getElementById(`status-text-${cameraId}`);

        if (statusDot) {
            statusDot.classList.toggle('active', isActive);
        }

        if (statusText) {
            statusText.textContent = isActive ? '活跃' : '断开';
        }
    }

    updateSelectedCameras() {
        if (!this.isActive) return;

        const selectedCameras = this.getSelectedCameras();
        
        // 重新订阅摄像头
        this.subscribeToCameras(selectedCameras);
    }

    updateLayout() {
        const layout = this.elements.layoutSelect.value;
        const grid = this.elements.cameraGrid;
        
        // 移除所有布局类
        grid.classList.remove('layout-auto', 'layout-grid', 'layout-horizontal', 'layout-vertical');
        
        // 添加新布局类
        grid.classList.add(`layout-${layout}`);
    }

    clearCameraDisplays() {
        this.elements.cameraGrid.innerHTML = '';
        this.cameraElements.clear();
        this.frameCounters.clear();
    }

    onCameraConnectionEstablished() {
        this.updateConnectionStatus(true);
        this.refreshCameraList();
    }

    updateConnectionStatus(isConnected) {
        const statusElement = this.elements.connectionStatus;
        if (statusElement) {
            statusElement.textContent = isConnected ? '已连接' : '未连接';
            statusElement.style.color = isConnected ? '#28a745' : '#dc3545';
        }
    }

    startStatsUpdate() {
        this.statsInterval = setInterval(() => {
            this.updateGlobalStats();
        }, 1000);
    }

    stopStatsUpdate() {
        if (this.statsInterval) {
            clearInterval(this.statsInterval);
            this.statsInterval = null;
        }
    }

    updateGlobalStats() {
        // 更新总帧数
        if (this.elements.totalFrames) {
            this.elements.totalFrames.textContent = this.stats.totalFrames;
        }

        // 计算平均FPS
        const totalFPS = Array.from(this.frameCounters.values())
            .reduce((sum, counter) => sum + counter.fps, 0);
        const averageFPS = this.frameCounters.size > 0 ? 
            Math.round(totalFPS / this.frameCounters.size) : 0;

        if (this.elements.averageFPS) {
            this.elements.averageFPS.textContent = averageFPS;
        }

        this.stats.averageFPS = averageFPS;
    }

    handleScreenshot(message) {
        if (message.status === 'success') {
            // 触发截图事件，供地图构建等功能使用
            this.emitEvent(EVENTS.CAMERA_SCREENSHOT_CAPTURED, {
                cameraId: message.camera_id,
                frameId: message.frame_id,
                timestamp: message.timestamp,
                resolution: message.resolution,
                data: message.data
            });
        }
    }

    async captureScreenshot(cameraId) {
        try {
            if (!this.cameraConnection || !this.cameraConnection.isConnected) {
                throw new Error('摄像头连接未建立');
            }

            await this.cameraConnection.sendMessage({
                request_type: 'capture_screenshot',
                camera_id: cameraId
            });

        } catch (error) {
            Logger.error('截图失败:', error);
            throw error;
        }
    }

    getStats() {
        return {
            ...this.stats,
            cameras: Array.from(this.frameCounters.entries()).map(([id, counter]) => ({
                id,
                fps: counter.fps,
                frameCount: counter.count
            }))
        };
    }

    async beforeCleanup() {
        await this.stopMonitoring();
        
        if (this.udpManager && this.cameraConnection) {
            await this.udpManager.removeConnection('camera');
        }
    }
}
