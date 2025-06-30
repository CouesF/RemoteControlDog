// 机器狗控制组件
import BaseComponent from './BaseComponent.js';
import { EVENTS } from '../utils/constants.js';
import { Helpers } from '../utils/helpers.js';
import Logger from '../utils/logger.js';
import CONFIG from '../config.js';

export default class RobotDogController extends BaseComponent {
    constructor(containerId) {
        super(containerId);
        
        // 控制状态
        this.controlState = {
            // 模式状态
            currentMode: 'damp',
            // XYR控制
            x: 0,
            y: 0,
            r: 0,
            // 抬腿角度
            angle1: 0,
            angle2: 0,
            // 头部控制
            headPitch: 0,
            headYaw: 0
        };
        
        // 控制发送间隔
        this.sendInterval = null;
        this.sendFrequency = 100; // 10Hz
        
        // 控制端口
        this.controlPort = 58990;
        this.controlHost = CONFIG.API.BACKEND_HOST || '118.31.58.101';
        
        // UDP连接
        this.connectionId = 'robot-dog-control';
        this.isConnected = false;
    }

    async doRender() {
        if (!this.container) {
            throw new Error('Robot dog control container not found');
        }

        this.container.innerHTML = this.getTemplate();
        this.addStyles();
        this.initializeElements();
    }

    getTemplate() {
        return `
            <div class="robot-dog-control-panel">
                <div class="card-header">
                    <h5 class="mb-0"><i class="fas fa-robot"></i> 机器狗模式控制</h5>
                </div>
                <div class="card-body">
                    <!-- 模式切换 -->
                    <div class="mode-section">
                        <div class="mode-buttons">
                            <button class="mode-btn" data-mode="damp">阻尼模式</button>
                            <button class="mode-btn" data-mode="high_stand">高层站立</button>
                            <button class="mode-btn" data-mode="low_stand">底层站立</button>
                            <button class="mode-btn" data-mode="low_left_raise">底层左抬腿</button>
                            <button class="mode-btn" data-mode="low_right_raise">底层右抬腿</button>
                            <button class="mode-btn" data-mode="high_lie">高层趴下</button>
                        </div>
                        <div id="connection-status" class="connection-status">
                            <span class="status-dot"></span>
                            <span id="status-text">未连接</span>
                            <div class="debug-info ml-3">
                                <small>控制端点: ${this.controlHost}:${this.controlPort}</small>
                            </div>
                        </div>
                    </div>

                <!-- Joystick Controls Wrapper -->
                <div class="joystick-controls-wrapper">
                    <!-- 移动控制 -->
                    <div class="movement-section">
                        <div class="movement-controls">
                            <!-- XR摇杆 -->
                            <div class="joystick-wrapper">
                                <label>前后/旋转</label>
                                <div id="xr-joystick" class="joystick">
                                    <div class="joystick-handle" data-joystick="xr"></div>
                                    <div class="joystick-center"></div>
                                </div>
                                <div class="joystick-values">
                                    <span>X: <span id="x-value" class="joystick-value">0.00</span></span>
                                    <span>R: <span id="r-value" class="joystick-value">0.00</span></span>
                                </div>
                            </div>
                            
                            <!-- Y控制按钮 -->
                            <div class="y-control">
                                <label>左右移动</label>
                                <div class="y-buttons">
                                    <button id="y-left-btn" class="control-btn">
                                        <i class="fas fa-arrow-left"></i>
                                    </button>
                                    <span id="y-value">0.00</span>
                                    <button id="y-right-btn" class="control-btn">
                                        <i class="fas fa-arrow-right"></i>
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- 抬腿控制 -->
                    <div class="leg-section">
                        <div class="leg-controls">
                            <div class="joystick-wrapper">
                                <label>抬腿角度</label>
                                <div id="angle-joystick" class="joystick">
                                    <div class="joystick-handle" data-joystick="angle"></div>
                                    <div class="joystick-center"></div>
                                </div>
                                <div class="joystick-values">
                                    <span>A1: <span id="angle1-value" class="joystick-value">0.00</span></span>
                                    <span>A2: <span id="angle2-value" class="joystick-value">0.00</span></span>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- 头部控制 -->
                    <div class="head-section">
                        <div class="head-controls">
                            <div class="joystick-wrapper">
                                <label>头部姿态</label>
                                <div id="head-joystick" class="joystick">
                                    <div class="joystick-handle" data-joystick="head"></div>
                                    <div class="joystick-center"></div>
                                </div>
                                <div class="joystick-values">
                                    <span>俯仰: <span id="pitch-value" class="joystick-value">0.00</span></span>
                                    <span>偏航: <span id="yaw-value" class="joystick-value">0.00</span></span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                </div>
            </div>
        `;
    }

    addStyles() {
        const styleId = 'robot-dog-controller-styles';
        if (document.getElementById(styleId)) return;

        const style = document.createElement('style');
        style.id = styleId;
        style.textContent = `
            .robot-dog-control-panel .card-header {
                display: none;
                padding: 0.75rem 0.75rem;
                background-color: rgba(0,0,0,.03);
                border-bottom: 1px solid rgba(0,0,0,.125);
            }
            .robot-dog-control-panel .card-body {
                padding: 0rem;
            }
            
            .robot-dog-control-panel > div {
                margin-bottom: 0rem;
                padding-bottom: 0rem;
                border-bottom: 1px solid #e9ecef;
            }
            
            .robot-dog-control-panel > div:last-child {
                border-bottom: none;
                margin-bottom: 0;
            }
            
            .mode-buttons {
                display: flex;
                flex-wrap: wrap;
                justify-content: center;
                gap: 10px;
                margin-top: 10px;
            }
            
            .mode-btn {
                padding: 10px 15px;
                border: 2px solid #007bff;
                background: white;
                color: #007bff;
                border-radius: 5px;
                cursor: pointer;
                transition: all 0.3s;
                font-weight: 500;
            }
            
            .mode-btn:hover {
                background: #e7f1ff;
            }
            
            .mode-btn.active {
                background: #007bff;
                color: white;
            }
            
            .movement-controls {
                display: flex;
                flex-direction: column;
                gap: 1rem;
                align-items: center;
            }
            
            .joystick-wrapper {
                text-align: center;
            }
            
            .joystick-wrapper label {
                display: block;
                margin-bottom: 10px;
                font-weight: 500;
            }
            
            .joystick {
                width: 100px;
                height: 100px;
                border: 3px solid #dee2e6;
                border-radius: 50%;
                position: relative;
                margin: 0 auto 10px;
                background: #f8f9fa;
                touch-action: none;
            }
            
            .joystick-handle {
                width: 35px;
                height: 35px;
                background: #007bff;
                border: 3px solid white;
                border-radius: 50%;
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                cursor: grab;
                box-shadow: 0 2px 6px rgba(0,123,255,0.4);
                transition: box-shadow 0.2s;
            }
            
            .joystick-handle:active {
                cursor: grabbing;
                box-shadow: 0 4px 10px rgba(0,123,255,0.6);
            }
            
            .joystick-center {
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
            
            .joystick-values {
                display: flex;
                justify-content: center;
                gap: 20px;
                font-size: 0.5rem;
            }
            
            .joystick-values span {
                background: #f8f9fa;
                padding: 2px 8px;
                border-radius: 3px;
                font-family: monospace;
            }

            .joystick-value {
                display: inline-block;
                width: 45px;
                text-align: right;
            }
            
            .y-control {
                text-align: center;
            }
            
            .y-control label {
                display: block;
                margin-bottom: 10px;
                font-weight: 500;
            }
            
            .y-buttons {
                display: flex;
                align-items: center;
                gap: 10px;
            }
            
            .control-btn {
                padding: 8px 15px;
                border: 1px solid #6c757d;
                background: white;
                color: #6c757d;
                border-radius: 5px;
                cursor: pointer;
                transition: all 0.2s;
            }
            
            .control-btn:active {
                background: #6c757d;
                color: white;
            }
            
            #y-value {
                background: #f8f9fa;
                padding: 5px 10px;
                border-radius: 3px;
                font-family: monospace;
                min-width: 60px;
                display: inline-block;
            }
            
            .leg-controls, .head-controls {
                display: flex;
                justify-content: center;
            }
            
            .connection-status {
                display: flex;
                align-items: center;
                gap: 8px;
            }
            
            .status-dot {
                width: 10px;
                height: 10px;
                border-radius: 50%;
                background: #dc3545;
                animation: pulse 2s infinite;
            }
            
            .status-dot.connected {
                background: #28a745;
            }
            
            @keyframes pulse {
                0% { opacity: 1; }
                50% { opacity: 0.5; }
                100% { opacity: 1; }
            }
            
            .debug-info {
                color: #6c757d;
            }
        `;
        document.head.appendChild(style);
    }

    initializeElements() {
        this.elements = {
            // 模式按钮
            modeButtons: this.querySelectorAll('.mode-btn'),
            // XR摇杆
            xrJoystick: this.querySelector('#xr-joystick'),
            xValue: this.querySelector('#x-value'),
            rValue: this.querySelector('#r-value'),
            // Y控制
            yLeftBtn: this.querySelector('#y-left-btn'),
            yRightBtn: this.querySelector('#y-right-btn'),
            yValue: this.querySelector('#y-value'),
            // 角度摇杆
            angleJoystick: this.querySelector('#angle-joystick'),
            angle1Value: this.querySelector('#angle1-value'),
            angle2Value: this.querySelector('#angle2-value'),
            // 头部摇杆
            headJoystick: this.querySelector('#head-joystick'),
            pitchValue: this.querySelector('#pitch-value'),
            yawValue: this.querySelector('#yaw-value'),
            // 状态
            statusDot: this.querySelector('.status-dot'),
            statusText: this.querySelector('#status-text')
        };
    }

    setupEventListeners() {
        // 初始化UDP连接
        this.initializeUDPConnection();
        
        // 模式按钮
        this.elements.modeButtons.forEach(btn => {
            this.addEventListener(btn, 'click', () => {
                const mode = btn.getAttribute('data-mode');
                this.switchMode(mode);
            });
        });
        
        // 设置摇杆
        this.setupJoystick('xr', (x, y) => {
            this.controlState.x = y;  // 前后
            this.controlState.r = x;  // 旋转
            this.updateXRDisplay();
        });
        
        this.setupJoystick('angle', (x, y) => {
            this.controlState.angle1 = x;
            this.controlState.angle2 = y;
            this.updateAngleDisplay();
        });
        
        this.setupJoystick('head', (x, y) => {
            this.controlState.headYaw = x;
            this.controlState.headPitch = y;
            this.updateHeadDisplay();
        });
        
        // Y控制按钮
        this.setupYControl();
        
        // 开始发送控制命令
        this.startControlLoop();
        
        // 设置初始模式
        // this.switchMode('damp');
    }

    setupJoystick(type, callback) {
        const joystickId = `${type}-joystick`;
        const joystick = this.querySelector(`#${joystickId}`);
        const handle = joystick.querySelector('.joystick-handle');
        
        if (!joystick || !handle) return;
        
        let isDragging = false;
        const radius = 40; // 最大移动半径
        
        const handleStart = (e) => {
            e.preventDefault();
            isDragging = true;
            handle.style.cursor = 'grabbing';
        };
        
        const handleMove = (e) => {
            if (!isDragging) return;
            e.preventDefault();
            
            const rect = joystick.getBoundingClientRect();
            const centerX = rect.left + rect.width / 2;
            const centerY = rect.top + rect.height / 2;
            
            const clientX = e.clientX || (e.touches && e.touches[0].clientX);
            const clientY = e.clientY || (e.touches && e.touches[0].clientY);
            
            if (!clientX || !clientY) return;
            
            let deltaX = clientX - centerX;
            let deltaY = clientY - centerY;
            
            // 限制在圆形区域内
            const distance = Math.sqrt(deltaX * deltaX + deltaY * deltaY);
            if (distance > radius) {
                deltaX = (deltaX / distance) * radius;
                deltaY = (deltaY / distance) * radius;
            }
            
            // 更新手柄位置
            handle.style.transform = `translate(calc(-50% + ${deltaX}px), calc(-50% + ${deltaY}px))`;
            
            // 归一化到-1到1
            const normalizedX = deltaX / radius;
            const normalizedY = -deltaY / radius; // Y轴反向
            
            callback(normalizedX, normalizedY);
        };
        
        const handleEnd = () => {
            if (!isDragging) return;
            isDragging = false;
            handle.style.cursor = 'grab';
            
            // 重置位置
            handle.style.transform = 'translate(-50%, -50%)';
            
            // 重置值
            callback(0, 0);
        };
        
        // 鼠标事件
        this.addEventListener(handle, 'mousedown', handleStart);
        this.addEventListener(document, 'mousemove', handleMove);
        this.addEventListener(document, 'mouseup', handleEnd);
        
        // 触摸事件
        this.addEventListener(handle, 'touchstart', handleStart);
        this.addEventListener(document, 'touchmove', handleMove);
        this.addEventListener(document, 'touchend', handleEnd);
    }

    setupYControl() {
        let yInterval = null;
        const ySpeed = 0.3;
        
        // 左移按钮
        this.addEventListener(this.elements.yLeftBtn, 'mousedown', () => {
            this.controlState.y = ySpeed;
            this.updateYDisplay();
            yInterval = setInterval(() => {
                this.controlState.y = ySpeed;
            }, 100);
        });
        
        this.addEventListener(this.elements.yLeftBtn, 'mouseup', () => {
            clearInterval(yInterval);
            this.controlState.y = 0;
            this.updateYDisplay();
        });
        
        this.addEventListener(this.elements.yLeftBtn, 'mouseleave', () => {
            clearInterval(yInterval);
            this.controlState.y = 0;
            this.updateYDisplay();
        });
        
        // 右移按钮
        this.addEventListener(this.elements.yRightBtn, 'mousedown', () => {
            this.controlState.y = -ySpeed;
            this.updateYDisplay();
            yInterval = setInterval(() => {
                this.controlState.y = -ySpeed;
            }, 100);
        });
        
        this.addEventListener(this.elements.yRightBtn, 'mouseup', () => {
            clearInterval(yInterval);
            this.controlState.y = 0;
            this.updateYDisplay();
        });
        
        this.addEventListener(this.elements.yRightBtn, 'mouseleave', () => {
            clearInterval(yInterval);
            this.controlState.y = 0;
            this.updateYDisplay();
        });
    }

    switchMode(mode) {
        this.controlState.currentMode = mode;
        
        // 更新按钮状态
        this.elements.modeButtons.forEach(btn => {
            if (btn.getAttribute('data-mode') === mode) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });
        
        // 发送模式切换命令
        this.sendCommand({
            command_type: 'state_switch',
            target: 'body',
            data: {
                state: mode
            }
        });
        
        Logger.info(`Switched to mode: ${mode}`);
    }

    updateXRDisplay() {
        this.elements.xValue.textContent = this.controlState.x.toFixed(2);
        this.elements.rValue.textContent = this.controlState.r.toFixed(2);
    }

    updateYDisplay() {
        this.elements.yValue.textContent = this.controlState.y.toFixed(2);
    }

    updateAngleDisplay() {
        this.elements.angle1Value.textContent = this.controlState.angle1.toFixed(2);
        this.elements.angle2Value.textContent = this.controlState.angle2.toFixed(2);
    }

    updateHeadDisplay() {
        this.elements.pitchValue.textContent = this.controlState.headPitch.toFixed(2);
        this.elements.yawValue.textContent = this.controlState.headYaw.toFixed(2);
    }

    startControlLoop() {
        // 定期发送控制命令
        this.sendInterval = setInterval(() => {
            // 发送XYR控制
            if (Math.abs(this.controlState.x) > 0.01 || 
                Math.abs(this.controlState.y) > 0.01 || 
                Math.abs(this.controlState.r) > 0.01 ||
                Math.abs(this.controlState.angle1) > 0.1 ||
                Math.abs(this.controlState.angle2) > 0.1) {
                
                this.sendCommand({
                    command_type: 'xyr_control',
                    target: 'body',
                    data: {
                        x: this.controlState.x,
                        y: this.controlState.y,
                        r: this.controlState.r
                    }
                });
            }
            if (Math.abs(this.controlState.angle1) > 0.1 ||
                Math.abs(this.controlState.angle2) > 0.1) {
                
                this.sendCommand({
                    command_type: 'object_control',
                    target: 'leg',
                    data: {
                        angle1: this.controlState.angle1,
                        angle2: this.controlState.angle2
                    }
                });
            }
            // 发送头部控制
            if (Math.abs(this.controlState.headPitch) > 0.1 || 
                Math.abs(this.controlState.headYaw) > 0.1) {
                
                this.sendCommand({
                    command_type: 'object_control',
                    target: 'head',
                    data: {
                        pitch: this.controlState.headPitch,
                        yaw: this.controlState.headYaw,
                        expression: 'c'
                    }
                });
            }
        }, this.sendFrequency);
    }

    async initializeUDPConnection() {
        try {
            if (!window.api) {
                Logger.error('Window API not available');
                return;
            }
            
            // 创建UDP连接
            const result = await window.api.connectUDP({
                connectionId: this.connectionId,
                host: this.controlHost,
                port: this.controlPort
            });
            
            if (result.success) {
                this.isConnected = true;
                Logger.info(`UDP connection established to ${this.controlHost}:${this.controlPort}`);
                
                // 设置错误处理
                window.api.onUDPError(this.connectionId, (error) => {
                    Logger.error('UDP error:', error);
                    this.updateConnectionStatus(false);
                });
                
                // 设置连接状态监听
                window.api.onUDPConnect(this.connectionId, () => {
                    this.isConnected = true;
                    this.updateConnectionStatus(true);
                });
                
                window.api.onUDPDisconnect(this.connectionId, () => {
                    this.isConnected = false;
                    this.updateConnectionStatus(false);
                });
                
                this.updateConnectionStatus(true);
            } else {
                Logger.error('Failed to establish UDP connection:', result.error);
                this.updateConnectionStatus(false);
            }
        } catch (error) {
            Logger.error('Error initializing UDP connection:', error);
            this.updateConnectionStatus(false);
        }
    }

    async sendCommand(command) {
        try {
            if (!this.isConnected) {
                Logger.warn('UDP not connected, attempting to reconnect...');
                await this.initializeUDPConnection();
                if (!this.isConnected) return;
            }
            
            const packet = {
                timestamp: Date.now() / 1000,
                data: command
            };
            
            const message = JSON.stringify(packet);
            
            // 使用UDP发送到后端
            if (window.api?.sendUDP) {
                window.api.sendUDP(this.connectionId, message);
                Logger.debug('Command sent:', command);
            } else {
                Logger.error('UDP send API not available');
                this.updateConnectionStatus(false);
            }
        } catch (error) {
            Logger.error('Failed to send command:', error);
            this.updateConnectionStatus(false);
        }
    }

    updateConnectionStatus(connected) {
        if (connected) {
            this.elements.statusDot.classList.add('connected');
            this.elements.statusText.textContent = '已连接';
        } else {
            this.elements.statusDot.classList.remove('connected');
            this.elements.statusText.textContent = '未连接';
        }
    }

    async beforeCleanup() {
        // 停止控制循环
        if (this.sendInterval) {
            clearInterval(this.sendInterval);
            this.sendInterval = null;
        }
        
        // 发送停止命令
        this.controlState = {
            x: 0, y: 0, r: 0,
            angle1: 0, angle2: 0,
            headPitch: 0, headYaw: 0
        };
        
        await this.sendCommand({
            command_type: 'xyr_control',
            target: 'body',
            data: {
                x: 0, y: 0, r: 0
            }
        });
        
        // 断开UDP连接
        if (this.isConnected && window.api?.disconnectUDP) {
            window.api.disconnectUDP(this.connectionId);
            this.isConnected = false;
        }
    }
}
