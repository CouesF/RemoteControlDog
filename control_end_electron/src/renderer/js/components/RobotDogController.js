// 机器狗控制组件
import BaseComponent from './BaseComponent.js';
import { EVENTS } from '../utils/constants.js';
import { Helpers } from '../utils/helpers.js';
import Logger from '../utils/logger.js';
import CONFIG from '../config.js';
import GamepadManager from '../utils/GamepadManager.js';
import { SPEECH_COMMANDS } from '../config/speech-config.js';

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
            headYaw: 0,
            
            // 上次发送的控制值
            lastSentXYR: { x: 0, y: 0, r: 0 },
            lastSentAngles: { angle1: 0, angle2: 0 },
            lastSentHead: { pitch: 0, yaw: 0 },
            lastHeadCommandTime: 0
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

        // Gamepad
        this.gamepadManager = new GamepadManager();

        // Keyboard state
        this.keyState = {
            w: false,
            a: false,
            s: false,
            d: false,
        };

        // Body Log
        this.bodyLogInterval = null;
        this.bodyLogMapping = {
            0: "初始化完成",
            1: "启动主控线程",
            2: "DDS 通道初始化成功",
            3: "收到新指令",
            4: "系统正常退出",
        
            10: "当前是HIGH_LEVEL_DAMP",
            11: "当前是LOW_LEVEL_DAMP",
            12: "当前是HIGH_LEVEL_STAND",
            13: "当前是LOW_LEVEL_STAND",
            14: "当前是LOW_LEVEL_RAISE_LEG",
            15: "当前是HIGH_LEVEL_WALK",
            16: "当前是HIGH_LEVEL_STAND_DOWN",
            17: "当前是LOW_LEVEL_LIE_DOWN",
        
            20: "执行 StandUp",
            21: "执行 StandDown",
            22: "执行 BalanceStand",
            23: "执行 Damp",
            24: "执行 Walk",
        
            30: "抬腿流程开始",
            31: "抬腿流程结束",
            32: "接收并处理抬腿角度指令",
            33: "抬腿坐标不可达",
            34: "抬腿关节超限",
        
            90: "非法状态切换（已拒绝）",
            91: "速度超限（已拒绝）",
            92: "DDS 指令解析异常",
            93: "低层线程未正常停止",
            94: "未识别的状态机异常",
            95: "运动模式切换失败",
            96: "退出时尝试切阻尼失败",
            97: "未知命令类型（忽略）",
            98: "系统内部异常",
            99: "CRITICAL ERROR",
        }
        

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
        const speechButtonsHtml = Object.values(SPEECH_COMMANDS).map(command => `
            <button class="speech-btn" data-text="${command.text}">${command.label}</button>
        `).join('');

        return `
            <div class="robot-dog-control-panel">
                <div class="card-header">
                    <h5 class="mb-0"><i class="fas fa-robot"></i> 机器狗模式控制</h5>
                </div>
                <div class="card-body">
                    <!-- 模式切换 -->
                    <div class="mode-section">
                        <div class="mode-buttons">
                            <button class="mode-btn" data-mode="damp">阻尼</button>
                            <button class="mode-btn" data-mode="high_stand">高站</button>
                            <button class="mode-btn" data-mode="low_stand">底站</button>
                            <button class="mode-btn" data-mode="low_left_raise">底左抬</button>
                            <button class="mode-btn" data-mode="low_right_raise">底右抬</button>
                            <button class="mode-btn" data-mode="high_lie">高趴</button>
                        </div>
                        <div id="connection-status" class="connection-status">
                            <span class="status-dot"></span>
                            <span id="status-text">未连接</span>
                        </div>
                        <div id="body-log-status" class="body-log-status">
                            <span id="body-log-value">--</span>
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

                <!-- 语音合成 -->
                <div class="speech-section">
                    <div class="speech-buttons">
                        ${speechButtonsHtml}
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
                gap: 6px;
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
                gap: 0px;
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

            .body-log-status {
                display: flex;
                align-items: center;
                gap: 8px;
                background: #f8f9fa;
                padding: 5px 10px;
                border-radius: 3px;
                font-family: monospace;
                margin-left: auto;
            }

            .log-label {
                font-weight: 500;
                color: #495057;
            }

            #body-log-value {
                font-weight: bold;
                font-size: xx-small;
                color: #007bff;
            }

            .speech-section {
                padding: 10px;
                border-top: 1px solid #e9ecef;
            }

            .speech-buttons {
                display: flex;
                flex-wrap: wrap;
                justify-content: center;
                gap: 10px;
            }

            .speech-btn {
                padding: 10px 15px;
                border: 2px solid #17a2b8;
                background: white;
                color: #17a2b8;
                border-radius: 5px;
                cursor: pointer;
                transition: all 0.3s;
                font-weight: 500;
            }

            .speech-btn:hover {
                background: #e2f3f5;
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
            statusText: this.querySelector('#status-text'),
            bodyLogValue: this.querySelector('#body-log-value'),
            // 语音按钮
            speechButtons: this.querySelectorAll('.speech-btn')
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
        this.xrJoystickController = this.setupJoystick('xr', (x, y) => {
            this.controlState.x = y;  // 前后
            this.controlState.r = x;  // 旋转
        });
        
        this.setupJoystick('angle', (x, y) => {
            this.controlState.angle1 = x;
            this.controlState.angle2 = y;
            this.updateAngleDisplay();
        });
        
        this.headJoystickController = this.setupJoystick('head', (x, y) => {
            this.controlState.headYaw = x;
            this.controlState.headPitch = y;
            this.updateHeadDisplay();
        }, { 
            autoReset: false, // Do not auto-reset
            onMove: (x, y) => {
                // Dispatch an event when the joystick is moved manually
                this.dispatchEvent(new CustomEvent('head-joystick-move', {
                    detail: { x, y },
                    bubbles: true,
                    composed: true
                }));
            }
        });
        
        // Y控制按钮
        this.setupYControl();
        
        // 开始发送控制命令
        this.startControlLoop();
        
        // 开始获取机身日志
        this.startBodyLogUpdates();

        // 设置初始模式
        // this.switchMode('damp');

        // 键盘控制
        this.setupKeyboardControls();

        // 语音按钮
        this.elements.speechButtons.forEach(btn => {
            this.addEventListener(btn, 'click', () => {
                const text = btn.getAttribute('data-text');
                this.synthesisSpeech(text);
            });
        });
    }

    setupJoystick(type, callback, options = {}) {
        const joystickId = `${type}-joystick`;
        const joystick = this.querySelector(`#${joystickId}`);
        const handle = joystick.querySelector('.joystick-handle');

        if (!joystick || !handle) return null;

        let isDragging = false;
        const radius = 40; // 最大移动半径
        const autoReset = options.autoReset !== false; // Default to true

        const setPosition = (normalizedX, normalizedY) => {
            const deltaX = normalizedX * radius;
            const deltaY = -normalizedY * radius; // Y轴反向

            handle.style.transform = `translate(calc(-50% + ${deltaX}px), calc(-50% + ${deltaY}px))`;
            callback(normalizedX, normalizedY);
        };

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

            const distance = Math.sqrt(deltaX * deltaX + deltaY * deltaY);
            if (distance > radius) {
                deltaX = (deltaX / distance) * radius;
                deltaY = (deltaY / distance) * radius;
            }

            const normalizedX = deltaX / radius;
            const normalizedY = -deltaY / radius;

            setPosition(normalizedX, normalizedY);
            
            // If there's a move handler, call it
            if (options.onMove) {
                options.onMove(normalizedX, normalizedY);
            }
        };

        const handleEnd = () => {
            if (!isDragging) return;
            isDragging = false;
            handle.style.cursor = 'grab';

            if (autoReset) {
                setPosition(0, 0);
                if (options.onMove) {
                    options.onMove(0, 0);
                }
            }
        };

        this.addEventListener(handle, 'mousedown', handleStart);
        this.addEventListener(document, 'mousemove', handleMove);
        this.addEventListener(document, 'mouseup', handleEnd);
        this.addEventListener(handle, 'touchstart', handleStart);
        this.addEventListener(document, 'touchmove', handleMove);
        this.addEventListener(document, 'touchend', handleEnd);

        // Return the public interface for this joystick
        return {
            setPosition
        };
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

    updateXRDisplay(gamepadState = { axes: [0,0,0,0], buttons: [] }) {
        const speedLimit = 0.5;
        const x_val = (gamepadState.axes[1] || 0) * -1 * speedLimit;
        const r_val = (gamepadState.axes[0] || 0) * speedLimit;

        let keyboardX = 0;
        let keyboardR = 0;

        if (this.keyState.w) keyboardX = 0.4;
        else if (this.keyState.s) keyboardX = -0.4;

        if (this.keyState.a) keyboardR = -0.4;
        else if (this.keyState.d) keyboardR = 0.4;

        // Keyboard overrides joystick and gamepad
        const finalX = keyboardX !== 0 ? keyboardX : this.controlState.x + x_val;
        const finalR = keyboardR !== 0 ? keyboardR : this.controlState.r + r_val;

        const combinedX = Helpers.clamp(finalX, -1, 1);
        const combinedR = Helpers.clamp(finalR, -1, 1);

        this.elements.xValue.textContent = combinedX.toFixed(2);
        this.elements.rValue.textContent = combinedR.toFixed(2);

        // Update joystick UI from keyboard
        if (this.xrJoystickController && (this.keyState.w || this.keyState.s || this.keyState.a || this.keyState.d)) {
            // Note: joystick's setPosition expects (x, y) which maps to (r, x) for us
            this.xrJoystickController.setPosition(combinedR, combinedX);
        }
    }

    updateYDisplay(gamepadState = { axes: [0,0,0,0], buttons: [] }) {
        let y_val = 0;
        if (gamepadState.buttons[14]) { // D-pad 左
            y_val = 0.5;
        } else if (gamepadState.buttons[15]) { // D-pad 右
            y_val = -0.5;
        }
        const combinedY = this.controlState.y + y_val;
        this.elements.yValue.textContent = combinedY.toFixed(2);
    }

    updateAngleDisplay() {
        this.elements.angle1Value.textContent = this.controlState.angle1.toFixed(2);
        this.elements.angle2Value.textContent = this.controlState.angle2.toFixed(2);
    }

    updateHeadDisplay(gamepadState = { axes: [0,0,0,0] }) {
        const combinedPitch = this.controlState.headPitch + (gamepadState.axes[3] || 0);
        const combinedYaw = this.controlState.headYaw + (gamepadState.axes[2] || 0);
        this.elements.pitchValue.textContent = combinedPitch.toFixed(2);
        this.elements.yawValue.textContent = combinedYaw.toFixed(2);
    }

    async fetchBodyLog() {
        try {
            const response = await fetch(`${CONFIG.API.BASE_URL}${CONFIG.API.ENDPOINTS.ROBOT_STATUS}`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            const logValue = data.body_log;
            const logText = this.bodyLogMapping[logValue] || '未知状态';
            this.elements.bodyLogValue.textContent = `${logText} (${logValue})`;
        } catch (error) {
            Logger.error('Failed to fetch body log:', error);
            this.elements.bodyLogValue.textContent = '获取失败';
        }
    }

    startBodyLogUpdates() {
        this.fetchBodyLog(); // Initial fetch
        this.bodyLogInterval = setInterval(() => {
            this.fetchBodyLog();
        }, 500);
    }

    startControlLoop() {
        // 定期发送控制命令
        this.sendInterval = setInterval(() => {
            // 获取手柄状态
            const gamepadState = this.gamepadManager.getState();
    
            // 更新显示
            this.updateXRDisplay(gamepadState);
            this.updateYDisplay(gamepadState);
            this.updateHeadDisplay(gamepadState);
    
            // --- 摇杆和按钮映射 ---
            // 左摇杆: axes[0] (左右), axes[1] (前后)
            // 右摇杆: axes[2] (左右), axes[3] (前后)
            // D-pad: buttons[14] (左), buttons[15] (右)
    
            // --- 速度和控制逻辑 ---
            const speedLimit = 0.5;
    
            // 前后控制 (左摇杆 Y轴)
            const x_val = (gamepadState.axes[1] || 0) * -1 * speedLimit; // Y轴反向
            // 旋转控制 (左摇杆 X轴)
            const r_val = (gamepadState.axes[0] || 0) * speedLimit;
    
            // 左右移动控制 (D-pad)
            let y_val = 0;
            if (gamepadState.buttons[14]) { // D-pad 左
                y_val = 0.5;
            } else if (gamepadState.buttons[15]) { // D-pad 右
                y_val = -0.5;
            }
    
            // 头部控制 (右摇杆)
            const head_yaw = this.controlState.headYaw + (gamepadState.axes[2] || 0);
            const head_pitch = this.controlState.headPitch + (gamepadState.axes[3] || 0) * -1; // Y轴反向
    
            // 合并UI, 手柄和键盘控制
            let keyboardX = 0;
            let keyboardR = 0;
            if (this.keyState.w) keyboardX = 0.2;
            else if (this.keyState.s) keyboardX = -0.2;

            if (this.keyState.a) keyboardR = -0.2;
            else if (this.keyState.d) keyboardR = 0.2;

            const finalX = keyboardX !== 0 ? keyboardX : this.controlState.x + x_val;
            const finalR = keyboardR !== 0 ? keyboardR : this.controlState.r + r_val;

            const combinedX = Helpers.clamp(finalX, -1, 1);
            const combinedY = Helpers.clamp(this.controlState.y + y_val, -1, 1);
            const combinedR = Helpers.clamp(finalR, -1, 1);
    
            // --- 发送控制命令 ---
            const epsilon = 1e-5;

            // 身体控制
            const { x: lastX, y: lastY, r: lastR } = this.controlState.lastSentXYR;
            const xyrChanged = Math.abs(combinedX - lastX) > epsilon || 
                               Math.abs(combinedY - lastY) > epsilon || 
                               Math.abs(combinedR - lastR) > epsilon;
            const xyrAboveThreshold = Math.abs(combinedX) > 0.01 || Math.abs(combinedY) > 0.01 || Math.abs(combinedR) > 0.01;

            if (xyrChanged || xyrAboveThreshold) {
                this.sendCommand({
                    command_type: 'xyr_control',
                    target: 'body',
                    data: { x: combinedX, y: combinedY, r: combinedR }
                });
                this.controlState.lastSentXYR = { x: combinedX, y: combinedY, r: combinedR };
            }

            // 抬腿控制
            const { angle1, angle2 } = this.controlState;
            const { angle1: lastAngle1, angle2: lastAngle2 } = this.controlState.lastSentAngles;
            const anglesChanged = Math.abs(angle1 - lastAngle1) > epsilon || Math.abs(angle2 - lastAngle2) > epsilon;
            const anglesAboveThreshold = Math.abs(angle1) > 0.1 || Math.abs(angle2) > 0.1;

            if (anglesChanged || anglesAboveThreshold) {
                this.sendCommand({
                    command_type: 'object_control',
                    target: 'leg',
                    data: { angle1, angle2 }
                });
                this.controlState.lastSentAngles = { angle1, angle2 };
            }

            // 头部控制
            const now = Date.now();
            const { pitch: lastPitch, yaw: lastYaw } = this.controlState.lastSentHead;
            const headChanged = Math.abs(head_pitch - lastPitch) > epsilon || Math.abs(head_yaw - lastYaw) > epsilon;
            const headIsActive = Math.abs(head_pitch) > 0.01 || Math.abs(head_yaw) > 0.01;

            let shouldSend = false;
            if (headChanged) {
                shouldSend = true;
                // Reset the timer whenever there's a change
                this.controlState.lastHeadCommandTime = now;
            } else {
                // If no change, check if we are within the 2-second resend window
                const timeSinceLastChange = now - this.controlState.lastHeadCommandTime;
                if (headIsActive && timeSinceLastChange < 2000) {
                    shouldSend = true;
                }
            }

            if (shouldSend) {
                this.sendCommand({
                    command_type: 'object_control',
                    target: 'head',
                    data: { pitch: head_pitch, yaw: head_yaw, expression: 'c' }
                });
                this.controlState.lastSentHead = { pitch: head_pitch, yaw: head_yaw };
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

    // 停止控制方法 - 用于结束实验时调用
    async stopControl() {
        Logger.info('Stopping robot control...');
        
        // 停止控制循环
        if (this.sendInterval) {
            clearInterval(this.sendInterval);
            this.sendInterval = null;
        }

        if (this.bodyLogInterval) {
            clearInterval(this.bodyLogInterval);
            this.bodyLogInterval = null;
        }
        
        // 重置控制状态
        this.controlState.x = 0;
        this.controlState.y = 0;
        this.controlState.r = 0;
        this.controlState.angle1 = 0;
        this.controlState.angle2 = 0;
        this.controlState.headPitch = 0;
        this.controlState.headYaw = 0;
        
        // 发送停止命令
        await this.sendCommand({
            command_type: 'xyr_control',
            target: 'body',
            data: {
                x: 0, y: 0, r: 0
            }
        });
        
        // 切换到阻尼模式
        this.switchMode('damp');
        
        Logger.info('Robot control stopped successfully');
    }

    async beforeCleanup() {
        // 调用停止控制方法
        await this.stopControl();
        
        // 断开UDP连接
        if (this.isConnected && window.api?.disconnectUDP) {
            window.api.disconnectUDP(this.connectionId);
            this.isConnected = false;
        }
    }

    setupKeyboardControls() {
        this.addEventListener(document, 'keydown', (e) => {
            const key = e.key.toLowerCase();
            if (key in this.keyState) {
                this.keyState[key] = true;
            }
        });

        this.addEventListener(document, 'keyup', (e) => {
            const key = e.key.toLowerCase();
            if (key in this.keyState) {
                this.keyState[key] = false;
                // If all keys are up, reset the joystick UI if it was keyboard-controlled
                if (!Object.values(this.keyState).some(v => v)) {
                    this.xrJoystickController.setPosition(0, 0);
                }
            }
        });
    }

    async synthesisSpeech(text) {
        try {
            const response = await fetch(`${CONFIG.API.BASE_URL}/api/synthesis_speech`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ text: text })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const result = await response.json();
            Logger.info('Speech synthesis request successful:', result);
        } catch (error) {
            Logger.error('Failed to send speech synthesis request:', error);
        }
    }
}
