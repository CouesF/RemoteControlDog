// 机器人控制组件
import BaseComponent from './BaseComponent.js';
import { ROBOT_COMMANDS, EVENTS } from '../utils/constants.js';
import { Helpers } from '../utils/helpers.js';
import Logger from '../utils/logger.js';

export default class RobotController extends BaseComponent {
    constructor(containerId) {
        super(containerId);
        
        this.joystickActive = false;
        this.currentControl = { linearX: 0, linearY: 0, angularZ: 0 };
        this.controlInterval = null;
        this.controlFrequency = 100; // 10Hz
        
        this.robotStatus = {
            isConnected: false,
            batteryLevel: null,
            currentPosture: null,
            errorMessage: null
        };
    }

    async doRender() {
        if (!this.container) {
            throw new Error('Robot control container not found');
        }

        this.container.innerHTML = this.getTemplate();
        this.addStyles();
        this.initializeElements();
    }

    getTemplate() {
        return `
            <div class="robot-control-panel">
                <div class="control-section">
                    <h4>机器人控制</h4>
                    
                    <!-- 连接状态 -->
                    <div class="connection-status mb-3">
                        <div id="connection-indicator" class="status-indicator disconnected">
                            <span class="status-dot"></span>
                            <span id="connection-text">未连接</span>
                        </div>
                    </div>
                    
                    <!-- 姿态控制 -->
                    <div class="posture-controls mb-3">
                        <h6>姿态控制</h6>
                        <div class="btn-group" role="group">
                            <button id="stand-btn" class="btn btn-outline-primary btn-sm" data-posture="STAND">
                                站立
                            </button>
                            <button id="sit-btn" class="btn btn-outline-primary btn-sm" data-posture="SIT">
                                坐下
                            </button>
                            <button id="lie-btn" class="btn btn-outline-primary btn-sm" data-posture="LIE">
                                趴下
                            </button>
                        </div>
                    </div>
                    <!-- 系统控制 -->
                    <div class="system-controls mb-3">
                        <h6>系统控制</h6>
                        <button id="emergency-stop-btn" class="btn btn-danger btn-sm">
                            <i class="fas fa-stop-circle"></i> 紧急停止
                        </button>
                        <button id="reset-btn" class="btn btn-warning btn-sm ml-2" data-action="RESET">
                            <i class="fas fa-redo"></i> 重置
                        </button>
                    </div>
                    <!-- 虚拟摇杆 -->
                    <div class="joystick-container">
                        <h6>移动控制</h6>
                        <div id="virtual-joystick" class="virtual-joystick">
                            <div id="joystick-handle" class="joystick-handle"></div>
                            <div class="joystick-center-dot"></div>
                        </div>
                        <div class="control-info">
                            <div class="row text-center">
                                <div class="col-4">
                                    <small>前后: <span id="control-x" class="font-weight-bold">0.00</span></small>
                                </div>
                                <div class="col-4">
                                    <small>左右: <span id="control-y" class="font-weight-bold">0.00</span></small>
                                </div>
                                <div class="col-4">
                                    <small>旋转: <span id="control-r" class="font-weight-bold">0.00</span></small>
                                </div>
                            </div>
                        </div>
                        <div class="joystick-instructions">
                            <small class="text-muted">拖拽圆点控制机器人移动</small>
                        </div>
                    </div>
                </div>
                <!-- 状态显示 -->
                <div class="status-section">
                    <div id="robot-status-display" class="robot-status">
                        <h4>机器人状态</h4>
                        <div id="status-content">
                            <p class="text-muted">等待连接...</p>
                        </div>
                    </div>
                    
                    <div id="robot-video-container" class="video-container">
                        <h6>机器人视角</h6>
                        <div class="video-wrapper">
                            <img id="robot-video-stream" class="robot-video" alt="等待视频流..." />
                            <div id="video-placeholder" class="video-placeholder">
                                <i class="fas fa-video-slash fa-3x text-muted"></i>
                                <p class="text-muted mt-2">暂无视频</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    addStyles() {
        const styleId = 'robot-controller-styles';
        if (document.getElementById(styleId)) return;

        const style = document.createElement('style');
        style.id = styleId;
        style.textContent = `
            .robot-control-panel {
                display: flex;
                gap: 20px;
                padding: 20px;
                background: white;
                border-radius: 8px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                min-height: 400px;
            }
            
            .control-section {
                flex: 1;
                min-width: 300px;
            }
            
            .status-section {
                flex: 1;
                min-width: 300px;
            }
            
            .status-indicator {
                display: flex;
                align-items: center;
                padding: 8px 12px;
                border-radius: 4px;
                background: #f8f9fa;
            }
            
            .status-dot {
                width: 8px;
                height: 8px;
                border-radius: 50%;
                margin-right: 8px;
                background: #dc3545;
                animation: pulse 2s infinite;
            }
            
            .status-indicator.connected .status-dot {
                background: #28a745;
            }
            
            @keyframes pulse {
                0% { opacity: 1; }
                50% { opacity: 0.5; }
                100% { opacity: 1; }
            }
            
            .virtual-joystick {
                width: 150px;
                height: 150px;
                border: 3px solid #e9ecef;
                border-radius: 50%;
                position: relative;
                margin: 15px auto;
                background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
                box-shadow: inset 0 2px 4px rgba(0,0,0,0.1);
            }
            
            .joystick-handle {
                width: 50px;
                height: 50px;
                background: linear-gradient(135deg, #007bff 0%, #0056b3 100%);
                border: 3px solid white;
                border-radius: 50%;
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                cursor: grab;
                user-select: none;
                box-shadow: 0 2px 8px rgba(0,123,255,0.3);
                transition: box-shadow 0.2s ease;
            }
            
            .joystick-handle:active {
                cursor: grabbing;
                box-shadow: 0 4px 12px rgba(0,123,255,0.5);
            }
            
            .joystick-center-dot {
                width: 4px;
                height: 4px;
                background: #6c757d;
                border-radius: 50%;
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                pointer-events: none;
            }
            
            .control-info {
                margin-top: 10px;
                font-size: 0.875rem;
            }
            
            .joystick-instructions {
                text-align: center;
                margin-top: 10px;
            }
            
            .robot-video {
                max-width: 100%;
                max-height: 200px;
                border: 1px solid #ddd;
                border-radius: 4px;
                display: none;
            }
            
            .video-wrapper {
                position: relative;
                text-align: center;
                min-height: 150px;
                display: flex;
                align-items: center;
                justify-content: center;
                background: #f8f9fa;
                border: 1px solid #e9ecef;
                border-radius: 4px;
            }
            
            .video-placeholder {
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
            }
            
            .robot-status {
                background: #f8f9fa;
                padding: 15px;
                border-radius: 4px;
                margin-bottom: 15px;
                border: 1px solid #e9ecef;
            }
            
            .posture-controls .btn {
                margin-right: 5px;
            }
            
            .posture-controls .btn.active {
                background-color: #007bff;
                color: white;
            }
            
            .disabled {
                opacity: 0.6;
                pointer-events: none;
            }
        `;
        document.head.appendChild(style);
    }

    initializeElements() {
        // 获取DOM元素引用
        this.elements = {
            connectionIndicator: this.querySelector('#connection-indicator'),
            connectionText: this.querySelector('#connection-text'),
            statusContent: this.querySelector('#status-content'),
            videoStream: this.querySelector('#robot-video-stream'),
            videoPlaceholder: this.querySelector('#video-placeholder'),
            controlX: this.querySelector('#control-x'),
            controlY: this.querySelector('#control-y'),
            controlR: this.querySelector('#control-r'),
            joystick: this.querySelector('#virtual-joystick'),
            joystickHandle: this.querySelector('#joystick-handle')
        };
    }

    setupEventListeners() {
        // 姿态控制按钮
        const postureButtons = this.querySelectorAll('[data-posture]');
        postureButtons.forEach(button => {
            this.addEventListener(button, 'click', () => {
                const posture = button.getAttribute('data-posture');
                this.sendPostureCommand(posture);
                this.updatePostureButtonState(posture);
            });
        });

        // 系统控制按钮
        const emergencyBtn = this.querySelector('#emergency-stop-btn');
        if (emergencyBtn) {
            this.addEventListener(emergencyBtn, 'click', () => {
                this.sendSystemCommand(ROBOT_COMMANDS.SYSTEM_ACTIONS.EMERGENCY_STOP);
            });
        }

        const resetBtn = this.querySelector('#reset-btn');
        if (resetBtn) {
            this.addEventListener(resetBtn, 'click', () => {
                this.sendSystemCommand(ROBOT_COMMANDS.SYSTEM_ACTIONS.RESET);
            });
        }

        // 虚拟摇杆
        this.setupVirtualJoystick();

        // 监听机器人状态更新
        this.onEvent(EVENTS.ROBOT_STATUS_UPDATE, (status) => {
            this.updateRobotStatus(status);
        });

        // 监听视频流更新
        this.onEvent(EVENTS.VIDEO_STREAM_UPDATE, (videoData) => {
            this.updateVideoStream(videoData);
        });
    }

    setupVirtualJoystick() {
        const joystick = this.elements.joystick;
        const handle = this.elements.joystickHandle;
        
        if (!joystick || !handle) {
            Logger.warn('Joystick elements not found');
            return;
        }

        let isDragging = false;
        const joystickRect = joystick.getBoundingClientRect();
        const joystickCenter = { x: 75, y: 75 }; // 中心点相对坐标
        const maxDistance = 50; // 最大距离

        // 节流控制发送频率
        const throttledControlSend = Helpers.throttle(() => {
            this.sendControlCommand();
        }, this.controlFrequency);

        const handleStart = (event) => {
            event.preventDefault();
            isDragging = true;
            this.joystickActive = true;
            this.startControlLoop();
            handle.style.cursor = 'grabbing';
        };

        const handleMove = (event) => {
            if (!isDragging) return;

            event.preventDefault();
            const rect = joystick.getBoundingClientRect();
            
            // 获取鼠标或触摸位置
            const clientX = event.clientX || (event.touches && event.touches[0].clientX);
            const clientY = event.clientY || (event.touches && event.touches[0].clientY);
            
            if (!clientX || !clientY) return;
            
            // 计算相对于摇杆中心的位置
            const deltaX = clientX - rect.left - joystickCenter.x;
            const deltaY = clientY - rect.top - joystickCenter.y;
            
            // 计算距离
            const distance = Math.sqrt(deltaX * deltaX + deltaY * deltaY);
            const limitedDistance = Math.min(distance, maxDistance);
            
            let finalX = deltaX;
            let finalY = deltaY;
            
            // 限制在圆形区域内
            if (distance > maxDistance) {
                finalX = (deltaX / distance) * maxDistance;
                finalY = (deltaY / distance) * maxDistance;
            }
            
            // 更新手柄位置
            handle.style.left = `${joystickCenter.x + finalX}px`;
            handle.style.top = `${joystickCenter.y + finalY}px`;
            
            // 计算控制值 (-1 到 1)
            this.currentControl.linearX = -finalY / maxDistance; // Y轴控制前进后退（反向）
            this.currentControl.linearY = -finalX / maxDistance; // X轴控制左右移动（反向）
            this.currentControl.angularZ = -finalX / maxDistance; // X轴也控制旋转（反向）
            
            this.updateControlDisplay();
            throttledControlSend();
        };

        const handleEnd = () => {
            isDragging = false;
            this.joystickActive = false;
            this.stopControlLoop();
            handle.style.cursor = 'grab';
            
            // 重置手柄位置
            handle.style.left = '50%';
            handle.style.top = '50%';
            
            // 重置控制值
            this.currentControl = { linearX: 0, linearY: 0, angularZ: 0 };
            this.updateControlDisplay();
            this.sendControlCommand(); // 发送停止命令
        };

        // 鼠标事件
        this.addEventListener(handle, 'mousedown', handleStart);
        this.addEventListener(document, 'mousemove', handleMove);
        this.addEventListener(document, 'mouseup', handleEnd);

        // 触摸事件
        this.addEventListener(handle, 'touchstart', handleStart);
        this.addEventListener(document, 'touchmove', handleMove);
        this.addEventListener(document, 'touchend', handleEnd);

        // 防止拖拽
        this.addEventListener(handle, 'dragstart', (e) => e.preventDefault());
    }

    startControlLoop() {
        if (this.controlInterval) return;
        
        this.controlInterval = setInterval(() => {
            if (this.joystickActive) {
                this.sendControlCommand();
            }
        }, this.controlFrequency);
    }

    stopControlLoop() {
        if (this.controlInterval) {
            clearInterval(this.controlInterval);
            this.controlInterval = null;
        }
    }

    sendControlCommand() {
        if (window.electronAPI?.sendControlCommand) {
            window.electronAPI.sendControlCommand(this.currentControl);
            Logger.debug('Control command sent:', this.currentControl);
        } else {
            Logger.warn('electronAPI.sendControlCommand not available');
        }
    }

    sendPostureCommand(posture) {
        if (!Object.values(ROBOT_COMMANDS.POSTURES).includes(posture)) {
            Logger.error('Invalid posture:', posture);
            return;
        }

        if (window.electronAPI?.sendPostureCommand) {
            window.electronAPI.sendPostureCommand({ posture });
            Logger.info('Posture command sent:', posture);
        } else {
            Logger.warn('electronAPI.sendPostureCommand not available');
        }
    }

    sendSystemCommand(action) {
        if (!Object.values(ROBOT_COMMANDS.SYSTEM_ACTIONS).includes(action)) {
            Logger.error('Invalid system action:', action);
            return;
        }

        if (window.electronAPI?.sendSystemCommand) {
            window.electronAPI.sendSystemCommand({ action });
            Logger.info('System command sent:', action);
        } else {
            Logger.warn('electronAPI.sendSystemCommand not available');
        }
    }

    updateControlDisplay() {
        if (this.elements.controlX) {
            this.elements.controlX.textContent = this.currentControl.linearX.toFixed(2);
        }
        if (this.elements.controlY) {
            this.elements.controlY.textContent = this.currentControl.linearY.toFixed(2);
        }
        if (this.elements.controlR) {
            this.elements.controlR.textContent = this.currentControl.angularZ.toFixed(2);
        }
    }

    updatePostureButtonState(activePosture) {
        const postureButtons = this.querySelectorAll('[data-posture]');
        postureButtons.forEach(button => {
            const posture = button.getAttribute('data-posture');
            if (posture === activePosture) {
                button.classList.add('active');
            } else {
                button.classList.remove('active');
            }
        });
    }

    updateRobotStatus(status) {
        this.robotStatus = { ...this.robotStatus, ...status };
        
        // 更新连接状态
        if (this.elements.connectionIndicator && this.elements.connectionText) {
            if (status.isConnected) {
                this.elements.connectionIndicator.classList.remove('disconnected');
                this.elements.connectionIndicator.classList.add('connected');
                this.elements.connectionText.textContent = '已连接';
            } else {
                this.elements.connectionIndicator.classList.remove('connected');
                this.elements.connectionIndicator.classList.add('disconnected');
                this.elements.connectionText.textContent = '未连接';
            }
        }

        // 更新状态内容
        if (this.elements.statusContent) {
            const statusHtml = `
                <div class="status-item">
                    <strong>连接状态:</strong> 
                    <span class="badge badge-${status.isConnected ? 'success' : 'danger'}">
                        ${status.isConnected ? '已连接' : '未连接'}
                    </span>
                </div>
                <div class="status-item mt-2">
                    <strong>电池电量:</strong> 
                    <span class="badge badge-${this.getBatteryLevelClass(status.batteryLevel)}">
                        ${status.batteryLevel !== null ? status.batteryLevel + '%' : 'N/A'}
                    </span>
                </div>
                <div class="status-item mt-2">
                    <strong>当前姿态:</strong> 
                    <span class="badge badge-info">
                        ${this.translatePosture(status.currentPosture) || 'N/A'}
                    </span>
                </div>
                ${status.errorMessage ? `
                    <div class="status-item mt-2">
                        <strong>错误信息:</strong> 
                        <span class="text-danger">${status.errorMessage}</span>
                    </div>
                ` : ''}
            `;
            this.elements.statusContent.innerHTML = statusHtml;
        }

        // 更新当前姿态按钮状态
        if (status.currentPosture) {
            this.updatePostureButtonState(status.currentPosture);
        }

        Logger.debug('Robot status updated:', status);
    }

    updateVideoStream(videoData) {
        if (this.elements.videoStream && this.elements.videoPlaceholder) {
            if (videoData && typeof videoData === 'string') {
                this.elements.videoStream.src = videoData;
                this.elements.videoStream.style.display = 'block';
                this.elements.videoPlaceholder.style.display = 'none';
                Logger.debug('Video stream updated');
            } else {
                this.elements.videoStream.style.display = 'none';
                this.elements.videoPlaceholder.style.display = 'flex';
            }
        }
    }

    getBatteryLevelClass(level) {
        if (level === null || level === undefined) return 'secondary';
        if (level > 50) return 'success';
        if (level > 20) return 'warning';
        return 'danger';
    }

    translatePosture(posture) {
        const translations = {
            'STAND': '站立',
            'SIT': '坐下',
            'LIE': '趴下'
        };
        return translations[posture] || posture;
    }

    stopControl() {
        this.joystickActive = false;
        this.stopControlLoop();
        this.currentControl = { linearX: 0, linearY: 0, angularZ: 0 };
        this.sendControlCommand();
        this.updateControlDisplay();
        
        // 重置摇杆位置
        if (this.elements.joystickHandle) {
            this.elements.joystickHandle.style.left = '50%';
            this.elements.joystickHandle.style.top = '50%';
        }
    }

    async beforeCleanup() {
        this.stopControl();
    }
}