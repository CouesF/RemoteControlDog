// 机器狗控制面板组件 - 支持XYR控制、状态切换、对象控制
import BaseComponent from './BaseComponent.js';
import { getUDPManager } from './UDPConnectionManager.js';
import { EVENTS } from '../utils/constants.js';
import Logger from '../utils/logger.js';

export default class RobotControlPanel extends BaseComponent {
    constructor(containerId, options = {}) {
        super(containerId);
        
        this.options = {
            showJoystick: true,
            showStateControls: true,
            showObjectControls: true,
            enableKeyboard: true,
            joystickSensitivity: 1.0,
            ...options
        };
        
        this.isActive = false;
        this.udpManager = null;
        this.controlConnection = null;
        
        // 控制状态
        this.controlState = {
            x: 0,    // 前后移动
            y: 0,    // 左右移动  
            r: 0,    // 旋转
            target: 'body', // 控制对象：body/head
            mode: 'manual'  // 控制模式
        };
        
        // 键盘控制状态
        this.keyboardState = {
            keys: new Set(),
            isActive: false
        };
        
        // 发送控制命令的节流
        this.lastSendTime = 0;
        this.sendInterval = 50; // 20Hz发送频率
        
        this.stats = {
            commandsSent: 0,
            lastCommandTime: null,
            connectionStatus: 'disconnected'
        };
    }

    async doRender() {
        if (!this.container) {
            throw new Error('Robot control panel container not found');
        }

        this.container.innerHTML = this.getTemplate();
        this.addStyles();
        this.initializeElements();
        
        // 初始化UDP连接
        await this.initializeUDPConnection();
        
        // 初始化虚拟摇杆
        if (this.options.showJoystick) {
            this.initializeJoystick();
        }
        
        // 初始化键盘控制
        if (this.options.enableKeyboard) {
            this.initializeKeyboardControl();
        }
    }

    getTemplate() {
        return `
            <div class="robot-control-panel">
                <!-- 连接状态 -->
                <div class="control-header">
                    <div class="connection-status">
                        <div class="status-indicator" id="connection-indicator"></div>
                        <span id="connection-text">未连接</span>
                    </div>
                    <div class="control-stats">
                        <span class="stat-item">命令: <span id="commands-count">0</span></span>
                        <span class="stat-item">延迟: <span id="latency">-</span>ms</span>
                    </div>
                </div>

                <!-- 状态控制 -->
                <div class="state-controls" ${this.options.showStateControls ? '' : 'style="display: none;"'}>
                    <h6>状态控制</h6>
                    <div class="btn-group" role="group">
                        <button id="stand-btn" class="btn btn-primary btn-sm">
                            <i class="fas fa-arrow-up"></i> 站立
                        </button>
                        <button id="sit-btn" class="btn btn-secondary btn-sm">
                            <i class="fas fa-arrow-down"></i> 坐下
                        </button>
                        <button id="lie-btn" class="btn btn-outline-secondary btn-sm">
                            <i class="fas fa-bed"></i> 趴下
                        </button>
                        <button id="stop-btn" class="btn btn-danger btn-sm">
                            <i class="fas fa-stop"></i> 停止
                        </button>
                    </div>
                </div>

                <!-- 对象控制 -->
                <div class="object-controls" ${this.options.showObjectControls ? '' : 'style="display: none;"'}>
                    <h6>控制对象</h6>
                    <div class="btn-group" role="group">
                        <input type="radio" class="btn-check" name="control-target" id="body-radio" value="body" checked>
                        <label class="btn btn-outline-primary btn-sm" for="body-radio">
                            <i class="fas fa-dog"></i> 身体
                        </label>
                        
                        <input type="radio" class="btn-check" name="control-target" id="head-radio" value="head">
                        <label class="btn btn-outline-primary btn-sm" for="head-radio">
                            <i class="fas fa-eye"></i> 头部
                        </label>
                    </div>
                </div>

                <!-- 虚拟摇杆 -->
                <div class="joystick-container" ${this.options.showJoystick ? '' : 'style="display: none;"'}>
                    <div class="joystick-section">
                        <h6>移动控制 (XY)</h6>
                        <div class="joystick-wrapper">
                            <div id="movement-joystick" class="joystick">
                                <div class="joystick-base">
                                    <div class="joystick-handle" id="movement-handle"></div>
                                </div>
                                <div class="joystick-labels">
                                    <span class="label-top">前进</span>
                                    <span class="label-bottom">后退</span>
                                    <span class="label-left">左移</span>
                                    <span class="label-right">右移</span>
                                </div>
                            </div>
                            <div class="joystick-values">
                                <div>X: <span id="x-value">0.00</span></div>
                                <div>Y: <span id="y-value">0.00</span></div>
                            </div>
                        </div>
                    </div>

                    <div class="joystick-section">
                        <h6>旋转控制 (R)</h6>
                        <div class="rotation-control">
                            <div class="rotation-slider-container">
                                <input type="range" id="rotation-slider" class="rotation-slider" 
                                       min="-100" max="100" value="0" step="1">
                                <div class="rotation-labels">
                                    <span class="label-left">左转</span>
                                    <span class="label-center">0</span>
                                    <span class="label-right">右转</span>
                                </div>
                            </div>
                            <div class="rotation-value">
                                R: <span id="r-value">0.00</span>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- 键盘控制说明 -->
                <div class="keyboard-help" ${this.options.enableKeyboard ? '' : 'style="display: none;"'}>
                    <h6>键盘控制</h6>
                    <div class="keyboard-layout">
                        <div class="key-group">
                            <div class="key-row">
                                <span class="key">W</span>
                                <span class="key-desc">前进</span>
                            </div>
                            <div class="key-row">
                                <span class="key">A</span><span class="key">S</span><span class="key">D</span>
                                <span class="key-desc">左移/后退/右移</span>
                            </div>
                            <div class="key-row">
                                <span class="key">Q</span><span class="key">E</span>
                                <span class="key-desc">左转/右转</span>
                            </div>
                        </div>
                        <div class="key-status">
                            <span id="keyboard-status">键盘控制: <span id="keyboard-active">未激活</span></span>
                        </div>
                    </div>
                </div>

                <!-- 控制面板 -->
                <div class="control-actions">
                    <button id="activate-btn" class="btn btn-success">
                        <i class="fas fa-power-off"></i> 激活控制
                    </button>
                    <button id="deactivate-btn" class="btn btn-outline-danger" disabled>
                        <i class="fas fa-power-off"></i> 停用控制
                    </button>
                    <button id="emergency-stop-btn" class="btn btn-danger">
                        <i class="fas fa-exclamation-triangle"></i> 紧急停止
                    </button>
                </div>
            </div>
        `;
    }

    addStyles() {
        const styleId = 'robot-control-panel-styles';
        if (document.getElementById(styleId)) return;

        const style = document.createElement('style');
        style.id = styleId;
        style.textContent = `
            .robot-control-panel {
                display: flex;
                flex-direction: column;
                gap: 20px;
                padding: 20px;
                background: white;
                border-radius: 8px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            }
            
            .control-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding-bottom: 15px;
                border-bottom: 1px solid #e9ecef;
            }
            
            .connection-status {
                display: flex;
                align-items: center;
                gap: 8px;
                font-weight: 600;
            }
            
            .status-indicator {
                width: 12px;
                height: 12px;
                border-radius: 50%;
                background: #dc3545;
                transition: background-color 0.3s;
            }
            
            .status-indicator.connected {
                background: #28a745;
                animation: pulse 2s infinite;
            }
            
            .control-stats {
                display: flex;
                gap: 15px;
                font-size: 0.875rem;
                color: #6c757d;
            }
            
            .state-controls, .object-controls {
                display: flex;
                flex-direction: column;
                gap: 10px;
            }
            
            .state-controls h6, .object-controls h6 {
                margin: 0;
                font-weight: 600;
                color: #495057;
            }
            
            .joystick-container {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 30px;
            }
            
            .joystick-section {
                display: flex;
                flex-direction: column;
                gap: 15px;
            }
            
            .joystick-section h6 {
                margin: 0;
                font-weight: 600;
                color: #495057;
                text-align: center;
            }
            
            .joystick-wrapper {
                display: flex;
                flex-direction: column;
                align-items: center;
                gap: 15px;
            }
            
            .joystick {
                position: relative;
                width: 200px;
                height: 200px;
            }
            
            .joystick-base {
                width: 100%;
                height: 100%;
                border: 3px solid #007bff;
                border-radius: 50%;
                background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
                position: relative;
                box-shadow: inset 0 2px 8px rgba(0,0,0,0.1);
            }
            
            .joystick-handle {
                width: 40px;
                height: 40px;
                background: #007bff;
                border-radius: 50%;
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                cursor: grab;
                box-shadow: 0 2px 8px rgba(0,0,0,0.2);
                transition: box-shadow 0.2s;
            }
            
            .joystick-handle:active {
                cursor: grabbing;
                box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            }
            
            .joystick-labels {
                position: absolute;
                width: 100%;
                height: 100%;
                pointer-events: none;
            }
            
            .joystick-labels span {
                position: absolute;
                font-size: 0.75rem;
                font-weight: 500;
                color: #6c757d;
            }
            
            .label-top { top: -20px; left: 50%; transform: translateX(-50%); }
            .label-bottom { bottom: -20px; left: 50%; transform: translateX(-50%); }
            .label-left { left: -30px; top: 50%; transform: translateY(-50%); }
            .label-right { right: -30px; top: 50%; transform: translateY(-50%); }
            
            .joystick-values {
                display: flex;
                gap: 20px;
                font-family: monospace;
                font-size: 0.5rem;
                color: #495057;
            }
            
            .rotation-control {
                display: flex;
                flex-direction: column;
                align-items: center;
                gap: 15px;
            }
            
            .rotation-slider-container {
                position: relative;
                width: 200px;
            }
            
            .rotation-slider {
                width: 100%;
                height: 8px;
                border-radius: 4px;
                background: #e9ecef;
                outline: none;
                -webkit-appearance: none;
            }
            
            .rotation-slider::-webkit-slider-thumb {
                -webkit-appearance: none;
                width: 20px;
                height: 20px;
                border-radius: 50%;
                background: #007bff;
                cursor: pointer;
                box-shadow: 0 2px 4px rgba(0,0,0,0.2);
            }
            
            .rotation-slider::-moz-range-thumb {
                width: 20px;
                height: 20px;
                border-radius: 50%;
                background: #007bff;
                cursor: pointer;
                border: none;
                box-shadow: 0 2px 4px rgba(0,0,0,0.2);
            }
            
            .rotation-labels {
                display: flex;
                justify-content: space-between;
                margin-top: 5px;
                font-size: 0.75rem;
                color: #6c757d;
            }
            
            .rotation-value {
                font-family: monospace;
                font-size: 0.875rem;
                color: #495057;
            }
            
            .keyboard-help {
                background: #f8f9fa;
                padding: 15px;
                border-radius: 6px;
                border: 1px solid #e9ecef;
            }
            
            .keyboard-help h6 {
                margin: 0 0 10px 0;
                font-weight: 600;
                color: #495057;
            }
            
            .keyboard-layout {
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            
            .key-group {
                display: flex;
                flex-direction: column;
                gap: 5px;
            }
            
            .key-row {
                display: flex;
                align-items: center;
                gap: 5px;
            }
            
            .key {
                display: inline-block;
                padding: 4px 8px;
                background: white;
                border: 1px solid #ced4da;
                border-radius: 4px;
                font-family: monospace;
                font-size: 0.75rem;
                font-weight: 600;
                min-width: 24px;
                text-align: center;
            }
            
            .key-desc {
                font-size: 0.75rem;
                color: #6c757d;
                margin-left: 10px;
            }
            
            .key-status {
                font-size: 0.875rem;
                color: #495057;
            }
            
            .control-actions {
                display: flex;
                gap: 10px;
                justify-content: center;
                padding-top: 15px;
                border-top: 1px solid #e9ecef;
            }
            
            .btn-group .btn {
                margin-right: 5px;
            }
            
            .btn-group .btn:last-child {
                margin-right: 0;
            }
            
            @keyframes pulse {
                0% { opacity: 1; }
                50% { opacity: 0.5; }
                100% { opacity: 1; }
            }
            
            @media (max-width: 768px) {
                .joystick-container {
                    grid-template-columns: 1fr;
                    gap: 20px;
                }
                
                .joystick {
                    width: 150px;
                    height: 150px;
                }
                
                .rotation-slider-container {
                    width: 150px;
                }
            }
        `;
        document.head.appendChild(style);
    }

    initializeElements() {
        this.elements = {
            connectionIndicator: this.querySelector('#connection-indicator'),
            connectionText: this.querySelector('#connection-text'),
            commandsCount: this.querySelector('#commands-count'),
            latency: this.querySelector('#latency'),
            
            // 状态控制按钮
            standBtn: this.querySelector('#stand-btn'),
            sitBtn: this.querySelector('#sit-btn'),
            lieBtn: this.querySelector('#lie-btn'),
            stopBtn: this.querySelector('#stop-btn'),
            
            // 对象控制
            bodyRadio: this.querySelector('#body-radio'),
            headRadio: this.querySelector('#head-radio'),
            
            // 摇杆元素
            movementJoystick: this.querySelector('#movement-joystick'),
            movementHandle: this.querySelector('#movement-handle'),
            rotationSlider: this.querySelector('#rotation-slider'),
            
            // 数值显示
            xValue: this.querySelector('#x-value'),
            yValue: this.querySelector('#y-value'),
            rValue: this.querySelector('#r-value'),
            
            // 键盘状态
            keyboardActive: this.querySelector('#keyboard-active'),
            
            // 控制按钮
            activateBtn: this.querySelector('#activate-btn'),
            deactivateBtn: this.querySelector('#deactivate-btn'),
            emergencyStopBtn: this.querySelector('#emergency-stop-btn')
        };
    }

    setupEventListeners() {
        // 状态控制按钮
        this.addEventListener(this.elements.standBtn, 'click', () => {
            this.sendStateCommand('stand');
        });

        this.addEventListener(this.elements.sitBtn, 'click', () => {
            this.sendStateCommand('sit');
        });

        this.addEventListener(this.elements.lieBtn, 'click', () => {
            this.sendStateCommand('lie');
        });

        this.addEventListener(this.elements.stopBtn, 'click', () => {
            this.sendStateCommand('stop');
        });

        // 对象控制
        this.addEventListener(this.elements.bodyRadio, 'change', () => {
            this.controlState.target = 'body';
        });

        this.addEventListener(this.elements.headRadio, 'change', () => {
            this.controlState.target = 'head';
        });

        // 旋转滑块
        this.addEventListener(this.elements.rotationSlider, 'input', (e) => {
            this.controlState.r = parseFloat(e.target.value) / 100;
            this.updateValueDisplay();
            this.sendControlCommand();
        });

        // 控制按钮
        this.addEventListener(this.elements.activateBtn, 'click', () => {
            this.activateControl();
        });

        this.addEventListener(this.elements.deactivateBtn, 'click', () => {
            this.deactivateControl();
        });

        this.addEventListener(this.elements.emergencyStopBtn, 'click', () => {
            this.emergencyStop();
        });

        // UDP连接事件
        this.onEvent(EVENTS.UDP_CONNECTION_ESTABLISHED, (data) => {
            if (data.connectionId === 'control') {
                this.onControlConnectionEstablished();
            }
        });

        this.onEvent(EVENTS.UDP_CONNECTION_STATUS_CHANGED, (data) => {
            if (data.connectionId === 'control') {
                this.updateConnectionStatus(data.isConnected);
            }
        });
    }

    async initializeUDPConnection() {
        try {
            this.udpManager = getUDPManager();
            
            // 创建控制连接
            this.controlConnection = await this.udpManager.createConnection('control');
            
            Logger.info('机器狗控制UDP连接初始化完成');
            
        } catch (error) {
            Logger.error('机器狗控制UDP连接初始化失败:', error);
            this.updateConnectionStatus(false);
        }
    }

    initializeJoystick() {
        const joystick = this.elements.movementJoystick;
        const handle = this.elements.movementHandle;
        
        let isDragging = false;
        let joystickRect = null;
        let centerX = 0;
        let centerY = 0;
        let maxRadius = 0;

        const updateJoystickGeometry = () => {
            joystickRect = joystick.getBoundingClientRect();
            centerX = joystickRect.width / 2;
            centerY = joystickRect.height / 2;
            maxRadius = Math.min(centerX, centerY) - 20; // 留出手柄半径的空间
        };

        const startDrag = (e) => {
            isDragging = true;
            updateJoystickGeometry();
            handle.style.transition = 'none';
            document.addEventListener('mousemove', onDrag);
            document.addEventListener('mouseup', stopDrag);
            document.addEventListener('touchmove', onDrag, { passive: false });
            document.addEventListener('touchend', stopDrag);
        };

        const onDrag = (e) => {
            if (!isDragging) return;
            
            e.preventDefault();
            
            const clientX = e.clientX || (e.touches && e.touches[0].clientX);
            const clientY = e.clientY || (e.touches && e.touches[0].clientY);
            
            const x = clientX - joystickRect.left - centerX;
            const y = clientY - joystickRect.top - centerY;
            
            const distance = Math.sqrt(x * x + y * y);
            const angle = Math.atan2(y, x);
            
            const constrainedDistance = Math.min(distance, maxRadius);
            const constrainedX = Math.cos(angle) * constrainedDistance;
            const constrainedY = Math.sin(angle) * constrainedDistance;
            
            handle.style.transform = `translate(${constrainedX}px, ${constrainedY}px)`;
            
            // 更新控制状态 (注意坐标系转换)
            this.controlState.x = -constrainedY / maxRadius; // Y轴反向为前进
            this.controlState.y = constrainedX / maxRadius;   // X轴为左右
            
            this.updateValueDisplay();
            this.sendControlCommand();
        };

        const stopDrag = () => {
            if (!isDragging) return;
            
            isDragging = false;
            handle.style.transition = 'transform 0.2s ease-out';
            handle.style.transform = 'translate(0px, 0px)';
            
            // 重置控制状态
            this.controlState.x = 0;
            this.controlState.y = 0;
            
            this.updateValueDisplay();
            this.sendControlCommand();
            
            document.removeEventListener('mousemove', onDrag);
            document.removeEventListener('mouseup', stopDrag);
            document.removeEventListener('touchmove', onDrag);
            document.removeEventListener('touchend', stopDrag);
        };

        // 鼠标事件
        handle.addEventListener('mousedown', startDrag);
        
        // 触摸事件
        handle.addEventListener('touchstart', startDrag, { passive: false });
        
        // 窗口大小变化时更新几何信息
        window.addEventListener('resize', updateJoystickGeometry);
        
        // 初始化几何信息
        setTimeout(updateJoystickGeometry, 100);
    }

    initializeKeyboardControl() {
        const keyMap = {
            'KeyW': { x: 1, y: 0, r: 0 },    // 前进
            'KeyS': { x: -1, y: 0, r: 0 },   // 后退
            'KeyA': { x: 0, y: -1, r: 0 },   // 左移
            'KeyD': { x: 0, y: 1, r: 0 },    // 右移
            'KeyQ': { x: 0, y: 0, r: -1 },   // 左转
            'KeyE': { x: 0, y: 0, r: 1 }     // 右转
        };

        const updateKeyboardControl = () => {
            let x = 0, y = 0, r = 0;
            
            for (const key of this.keyboardState.keys) {
                if (keyMap[key]) {
                    x += keyMap[key].x;
                    y += keyMap[key].y;
                    r += keyMap[key].r;
                }
            }
            
            // 归一化
            const magnitude = Math.sqrt(x * x + y * y);
            if (magnitude > 1) {
                x /= magnitude;
                y /= magnitude;
            }
            
            r = Math.max(-1, Math.min(1, r));
            
            this.controlState.x = x;
            this.controlState.y = y;
            this.controlState.r = r;
            
            this.updateValueDisplay();
            this.sendControlCommand();
        };

        document.addEventListener('keydown', (e) => {
            if (!this.keyboardState.isActive) return;
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
            
            if (keyMap[e.code] && !this.keyboardState.keys.has(e.code)) {
                e.preventDefault();
                this.keyboardState.keys.add(e.code);
                updateKeyboardControl();
            }
        });

        document.addEventListener('keyup', (e) => {
            if (!this.keyboardState.isActive) return;
            
            if (keyMap[e.code] && this.keyboardState.keys.has(e.code)) {
                e.preventDefault();
                this.keyboardState.keys.delete(e.code);
                updateKeyboardControl();
            }
        });

        // 失去焦点时清除所有按键
        window.addEventListener('blur', () => {
            this.keyboardState.keys.clear();
            if (this.keyboardState.isActive) {
                this.controlState.x = 0;
                this.controlState.y = 0;
                this.controlState.r = 0;
                this.updateValueDisplay();
                this.sendControlCommand();
            }
        });
    }

    updateValueDisplay() {
        if (this.elements.xValue) {
            this.elements.xValue.textContent = this.controlState.x.toFixed(2);
        }
        if (this.elements.yValue) {
            this.elements.yValue.textContent = this.controlState.y.toFixed(2);
        }
        if (this.elements.rValue) {
            this.elements.rValue.textContent = this.controlState.r.toFixed(2);
        }
        
        // 更新旋转滑块
        if (this.elements.rotationSlider) {
            this.elements.rotationSlider.value = this.controlState.r * 100;
        }
    }

    async sendControlCommand() {
        const now = Date.now();
        if (now - this.lastSendTime < this.sendInterval) {
            return; // 节流
        }
        
        if (!this.isActive || !this.controlConnection || !this.controlConnection.isConnected) {
            return;
        }

        try {
            const command = {
                command_type: 'xyr_control',
                target: this.controlState.target,
                data: {
                    x: this.controlState.x,
                    y: this.controlState.y,
                    r: this.controlState.r
                },
                command_id: `cmd_${Date.now()}`,
                timestamp: now
            };

            await this.controlConnection.sendMessage(command);
            
            this.stats.commandsSent++;
            this.stats.lastCommandTime = now;
            this.lastSendTime = now;
            
            this.updateStats();
            
        } catch (error) {
            Logger.error('发送控制命令失败:', error);
        }
    }

    async sendStateCommand(state) {
        if (!this.controlConnection || !this.controlConnection.isConnected) {
            Logger.warn('控制连接未建立，无法发送状态命令');
            return;
        }

        try {
            const command = {
                command_type: 'state_switch',
                target: 'system',
                data: {
                    state: state
                },
                command_id: `state_${Date.now()}`,
                timestamp: Date.now()
            };

            await this.controlConnection.sendMessage(command);
            
            this.stats.commandsSent++;
            this.updateStats();
            
            Logger.info(`发送状态命令: ${state}`);
            
        } catch (error) {
            Logger.error('发送状态命令失败:', error);
        }
    }

    async sendObjectCommand(action, data = {}) {
        if (!this.controlConnection || !this.controlConnection.isConnected) {
            Logger.warn('控制连接未建立，无法发送对象命令');
            return;
        }

        try {
            const command = {
                command_type: 'object_control',
                target: this.controlState.target,
                data: {
                    action: action,
                    ...data
                },
                command_id: `obj_${Date.now()}`,
                timestamp: Date.now()
            };

            await this.controlConnection.sendMessage(command);
            
            this.stats.commandsSent++;
            this.updateStats();
            
            Logger.info(`发送对象命令: ${action} -> ${this.controlState.target}`);
            
        } catch (error) {
            Logger.error('发送对象命令失败:', error);
        }
    }

    activateControl() {
        this.isActive = true;
        this.keyboardState.isActive = true;
        
        this.elements.activateBtn.disabled = true;
        this.elements.deactivateBtn.disabled = false;
        
        if (this.elements.keyboardActive) {
            this.elements.keyboardActive.textContent = '已激活';
            this.elements.keyboardActive.style.color = '#28a745';
        }
        
        Logger.info('机器狗控制已激活');
    }

    deactivateControl() {
        this.isActive = false;
        this.keyboardState.isActive = false;
        this.keyboardState.keys.clear();
        
        // 重置控制状态
        this.controlState.x = 0;
        this.controlState.y = 0;
        this.controlState.r = 0;
        
        this.updateValueDisplay();
        this.sendControlCommand(); // 发送停止命令
        
        this.elements.activateBtn.disabled = false;
        this.elements.deactivateBtn.disabled = true;
        
        if (this.elements.keyboardActive) {
            this.elements.keyboardActive.textContent = '未激活';
            this.elements.keyboardActive.style.color = '#6c757d';
        }
        
        Logger.info('机器狗控制已停用');
    }

    async emergencyStop() {
        // 立即停止所有运动
        this.controlState.x = 0;
        this.controlState.y = 0;
        this.controlState.r = 0;
        
        this.updateValueDisplay();
        
        // 发送紧急停止命令
        await this.sendStateCommand('emergency_stop');
        await this.sendControlCommand();
        
        // 停用控制
        this.deactivateControl();
        
        Logger.warn('执行紧急停止');
    }

    onControlConnectionEstablished() {
        this.updateConnectionStatus(true);
        Logger.info('机器狗控制连接已建立');
    }

    updateConnectionStatus(isConnected) {
        this.stats.connectionStatus = isConnected ? 'connected' : 'disconnected';
        
        if (this.elements.connectionIndicator) {
            this.elements.connectionIndicator.classList.toggle('connected', isConnected);
        }
        
        if (this.elements.connectionText) {
            this.elements.connectionText.textContent = isConnected ? '已连接' : '未连接';
            this.elements.connectionText.style.color = isConnected ? '#28a745' : '#dc3545';
        }
        
        // 如果连接断开，自动停用控制
        if (!isConnected && this.isActive) {
            this.deactivateControl();
        }
    }

    updateStats() {
        if (this.elements.commandsCount) {
            this.elements.commandsCount.textContent = this.stats.commandsSent;
        }
        
        // 计算延迟（简化版本）
        if (this.stats.lastCommandTime && this.elements.latency) {
            const latency = Date.now() - this.stats.lastCommandTime;
            this.elements.latency.textContent = latency < 1000 ? latency : '-';
        }
    }

    getControlState() {
        return {
            ...this.controlState,
            isActive: this.isActive,
            keyboardActive: this.keyboardState.isActive
        };
    }

    getStats() {
        return {
            ...this.stats,
            controlState: this.getControlState()
        };
    }

    async beforeCleanup() {
        // 停用控制
        if (this.isActive) {
            await this.emergencyStop();
        }
        
        // 清理UDP连接
        if (this.udpManager && this.controlConnection) {
            await this.udpManager.removeConnection('control');
        }
        
        // 清理事件监听器
        this.keyboardState.keys.clear();
        
        Logger.info('机器狗控制面板已清理');
    }
}
