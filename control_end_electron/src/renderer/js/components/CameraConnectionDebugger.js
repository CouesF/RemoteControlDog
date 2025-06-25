// 摄像头连接调试器 - 专门用于诊断摄像头连接问题
import BaseComponent from './BaseComponent.js';
import Logger from '../utils/logger.js';

export default class CameraConnectionDebugger extends BaseComponent {
    constructor(containerId) {
        super(containerId);
        
        this.debugInfo = {
            electronAPI: null,
            udpConnections: {},
            connectionAttempts: [],
            errors: [],
            networkTests: {}
        };
        
        this.testResults = new Map();
        this.isRunning = false;
    }

    async doRender() {
        if (!this.container) {
            throw new Error('Camera connection debugger container not found');
        }

        this.container.innerHTML = this.getTemplate();
        this.addStyles();
        this.initializeElements();
        
        // 立即开始诊断
        await this.startDiagnosis();
    }

    getTemplate() {
        return `
            <div class="camera-debug-panel">
                <div class="debug-header">
                    <h5><i class="fas fa-bug"></i> 摄像头连接调试器</h5>
                    <div class="debug-controls">
                        <button id="start-debug-btn" class="btn btn-primary btn-sm">
                            <i class="fas fa-play"></i> 开始诊断
                        </button>
                        <button id="stop-debug-btn" class="btn btn-danger btn-sm" disabled>
                            <i class="fas fa-stop"></i> 停止诊断
                        </button>
                        <button id="clear-debug-btn" class="btn btn-secondary btn-sm">
                            <i class="fas fa-trash"></i> 清空日志
                        </button>
                    </div>
                </div>
                
                <div class="debug-content">
                    <div class="debug-section">
                        <h6><i class="fas fa-info-circle"></i> 系统信息</h6>
                        <div id="system-info" class="debug-info-panel">
                            <div class="loading">正在检测系统信息...</div>
                        </div>
                    </div>
                    
                    <div class="debug-section">
                        <h6><i class="fas fa-plug"></i> ElectronAPI 状态</h6>
                        <div id="electron-api-status" class="debug-info-panel">
                            <div class="loading">正在检测 ElectronAPI...</div>
                        </div>
                    </div>
                    
                    <div class="debug-section">
                        <h6><i class="fas fa-network-wired"></i> 网络连接测试</h6>
                        <div id="network-test-results" class="debug-info-panel">
                            <div class="loading">正在测试网络连接...</div>
                        </div>
                    </div>
                    
                    <div class="debug-section">
                        <h6><i class="fas fa-video"></i> 摄像头连接状态</h6>
                        <div id="camera-connection-status" class="debug-info-panel">
                            <div class="loading">正在检测摄像头连接...</div>
                        </div>
                    </div>
                    
                    <div class="debug-section">
                        <h6><i class="fas fa-list"></i> 实时日志</h6>
                        <div id="debug-log" class="debug-log-panel">
                            <!-- 日志将在这里显示 -->
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    addStyles() {
        const styleId = 'camera-debug-styles';
        if (document.getElementById(styleId)) return;

        const style = document.createElement('style');
        style.id = styleId;
        style.textContent = `
            .camera-debug-panel {
                background: white;
                border-radius: 8px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                overflow: hidden;
            }
            
            .debug-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 15px 20px;
                background: #f8f9fa;
                border-bottom: 1px solid #e9ecef;
            }
            
            .debug-header h5 {
                margin: 0;
                color: #495057;
                font-weight: 600;
            }
            
            .debug-controls {
                display: flex;
                gap: 8px;
            }
            
            .debug-content {
                padding: 20px;
                max-height: 600px;
                overflow-y: auto;
            }
            
            .debug-section {
                margin-bottom: 25px;
            }
            
            .debug-section:last-child {
                margin-bottom: 0;
            }
            
            .debug-section h6 {
                margin: 0 0 10px 0;
                color: #495057;
                font-weight: 600;
                font-size: 0.9rem;
            }
            
            .debug-info-panel {
                background: #f8f9fa;
                border: 1px solid #e9ecef;
                border-radius: 6px;
                padding: 15px;
                font-family: 'Courier New', monospace;
                font-size: 0.85rem;
                line-height: 1.4;
            }
            
            .debug-log-panel {
                background: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #333;
                border-radius: 6px;
                padding: 15px;
                font-family: 'Courier New', monospace;
                font-size: 0.8rem;
                line-height: 1.4;
                max-height: 300px;
                overflow-y: auto;
            }
            
            .loading {
                color: #6c757d;
                font-style: italic;
            }
            
            .status-item {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 8px;
                padding: 8px 0;
                border-bottom: 1px solid #e9ecef;
            }
            
            .status-item:last-child {
                border-bottom: none;
                margin-bottom: 0;
            }
            
            .status-label {
                font-weight: 500;
                color: #495057;
            }
            
            .status-value {
                font-family: 'Courier New', monospace;
                font-size: 0.85rem;
            }
            
            .status-success {
                color: #28a745;
                font-weight: 600;
            }
            
            .status-error {
                color: #dc3545;
                font-weight: 600;
            }
            
            .status-warning {
                color: #ffc107;
                font-weight: 600;
            }
            
            .status-info {
                color: #17a2b8;
                font-weight: 600;
            }
            
            .log-entry {
                margin-bottom: 5px;
                padding: 3px 0;
            }
            
            .log-timestamp {
                color: #6c757d;
                margin-right: 8px;
            }
            
            .log-level {
                margin-right: 8px;
                font-weight: 600;
                min-width: 50px;
                display: inline-block;
            }
            
            .log-level.INFO {
                color: #17a2b8;
            }
            
            .log-level.WARN {
                color: #ffc107;
            }
            
            .log-level.ERROR {
                color: #dc3545;
            }
            
            .log-level.DEBUG {
                color: #6f42c1;
            }
            
            .log-message {
                color: #d4d4d4;
            }
            
            .test-result {
                display: flex;
                align-items: center;
                gap: 8px;
                margin-bottom: 8px;
            }
            
            .test-icon {
                width: 16px;
                text-align: center;
            }
            
            .test-icon.success {
                color: #28a745;
            }
            
            .test-icon.error {
                color: #dc3545;
            }
            
            .test-icon.warning {
                color: #ffc107;
            }
            
            .test-icon.loading {
                color: #6c757d;
            }
        `;
        document.head.appendChild(style);
    }

    initializeElements() {
        this.elements = {
            startBtn: this.querySelector('#start-debug-btn'),
            stopBtn: this.querySelector('#stop-debug-btn'),
            clearBtn: this.querySelector('#clear-debug-btn'),
            systemInfo: this.querySelector('#system-info'),
            electronApiStatus: this.querySelector('#electron-api-status'),
            networkTestResults: this.querySelector('#network-test-results'),
            cameraConnectionStatus: this.querySelector('#camera-connection-status'),
            debugLog: this.querySelector('#debug-log')
        };
    }

    setupEventListeners() {
        this.addEventListener(this.elements.startBtn, 'click', () => {
            this.startDiagnosis();
        });

        this.addEventListener(this.elements.stopBtn, 'click', () => {
            this.stopDiagnosis();
        });

        this.addEventListener(this.elements.clearBtn, 'click', () => {
            this.clearDebugLog();
        });
    }

    async startDiagnosis() {
        if (this.isRunning) return;
        
        this.isRunning = true;
        this.elements.startBtn.disabled = true;
        this.elements.stopBtn.disabled = false;
        
        this.log('INFO', '开始摄像头连接诊断...');
        
        try {
            // 1. 检测系统信息
            await this.checkSystemInfo();
            
            // 2. 检测 ElectronAPI
            await this.checkElectronAPI();
            
            // 3. 测试网络连接
            await this.testNetworkConnections();
            
            // 4. 检测摄像头连接
            await this.checkCameraConnections();
            
            this.log('INFO', '诊断完成');
            
        } catch (error) {
            this.log('ERROR', `诊断过程中发生错误: ${error.message}`);
        }
    }

    stopDiagnosis() {
        this.isRunning = false;
        this.elements.startBtn.disabled = false;
        this.elements.stopBtn.disabled = true;
        
        this.log('INFO', '诊断已停止');
    }

    clearDebugLog() {
        this.elements.debugLog.innerHTML = '';
        this.log('INFO', '调试日志已清空');
    }

    async checkSystemInfo() {
        this.log('INFO', '检测系统信息...');
        
        const systemInfo = {
            userAgent: navigator.userAgent,
            platform: navigator.platform,
            language: navigator.language,
            cookieEnabled: navigator.cookieEnabled,
            onLine: navigator.onLine,
            timestamp: new Date().toISOString(),
            url: window.location.href,
            protocol: window.location.protocol
        };
        
        let html = '';
        for (const [key, value] of Object.entries(systemInfo)) {
            html += `
                <div class="status-item">
                    <span class="status-label">${key}:</span>
                    <span class="status-value">${value}</span>
                </div>
            `;
        }
        
        this.elements.systemInfo.innerHTML = html;
        this.log('INFO', '系统信息检测完成');
    }

    async checkElectronAPI() {
        this.log('INFO', '检测 ElectronAPI 状态...');
        
        const apiTests = {
            'window.electronAPI': !!window.electronAPI,
            'electronAPI.initializeUDP': !!(window.electronAPI?.initializeUDP),
            'electronAPI.connectUDP': !!(window.electronAPI?.connectUDP),
            'electronAPI.disconnectUDP': !!(window.electronAPI?.disconnectUDP),
            'electronAPI.sendUDPMessage': !!(window.electronAPI?.sendUDPMessage),
            'electronAPI.onUDPMessage': !!(window.electronAPI?.onUDPMessage),
            'electronAPI.onConnectionStatusChange': !!(window.electronAPI?.onConnectionStatusChange)
        };
        
        let html = '';
        for (const [api, available] of Object.entries(apiTests)) {
            const statusClass = available ? 'status-success' : 'status-error';
            const statusText = available ? '✓ 可用' : '✗ 不可用';
            
            html += `
                <div class="status-item">
                    <span class="status-label">${api}:</span>
                    <span class="status-value ${statusClass}">${statusText}</span>
                </div>
            `;
            
            this.log(available ? 'INFO' : 'ERROR', `${api}: ${statusText}`);
        }
        
        this.elements.electronApiStatus.innerHTML = html;
        
        // 测试 UDP 初始化
        if (window.electronAPI?.initializeUDP) {
            try {
                this.log('INFO', '尝试初始化 UDP...');
                const result = await window.electronAPI.initializeUDP();
                this.log('INFO', `UDP 初始化结果: ${JSON.stringify(result)}`);
            } catch (error) {
                this.log('ERROR', `UDP 初始化失败: ${error.message}`);
            }
        }
    }

    async testNetworkConnections() {
        this.log('INFO', '测试网络连接...');
        
        const testTargets = [
            { name: '摄像头服务器', host: '118.31.58.101', port: 48991 },
            { name: '控制服务器', host: '118.31.58.101', port: 48990 },
            { name: '主服务器', host: '118.31.58.101', port: 48995 }
        ];
        
        let html = '';
        
        for (const target of testTargets) {
            this.log('INFO', `测试连接到 ${target.name} (${target.host}:${target.port})...`);
            
            try {
                // 使用 fetch 测试连接（虽然可能会失败，但可以检测网络可达性）
                const startTime = Date.now();
                
                // 创建一个简单的连接测试
                const testResult = await this.testConnection(target.host, target.port);
                const duration = Date.now() - startTime;
                
                const statusClass = testResult.success ? 'status-success' : 'status-error';
                const statusText = testResult.success ? `✓ 连接成功 (${duration}ms)` : `✗ 连接失败: ${testResult.error}`;
                
                html += `
                    <div class="test-result">
                        <i class="fas fa-circle test-icon ${testResult.success ? 'success' : 'error'}"></i>
                        <span class="status-label">${target.name}:</span>
                        <span class="status-value ${statusClass}">${statusText}</span>
                    </div>
                `;
                
                this.log(testResult.success ? 'INFO' : 'WARN', `${target.name}: ${statusText}`);
                
            } catch (error) {
                html += `
                    <div class="test-result">
                        <i class="fas fa-circle test-icon error"></i>
                        <span class="status-label">${target.name}:</span>
                        <span class="status-value status-error">✗ 测试异常: ${error.message}</span>
                    </div>
                `;
                
                this.log('ERROR', `${target.name} 测试异常: ${error.message}`);
            }
        }
        
        this.elements.networkTestResults.innerHTML = html;
    }

    async testConnection(host, port) {
        return new Promise((resolve) => {
            // 由于浏览器安全限制，我们无法直接测试 UDP 连接
            // 这里我们尝试一个简单的网络可达性测试
            const img = new Image();
            const timeout = setTimeout(() => {
                resolve({ success: false, error: '连接超时' });
            }, 5000);
            
            img.onload = () => {
                clearTimeout(timeout);
                resolve({ success: true });
            };
            
            img.onerror = () => {
                clearTimeout(timeout);
                resolve({ success: false, error: '网络不可达' });
            };
            
            // 尝试加载一个小图片来测试网络连接
            img.src = `http://${host}:${port}/favicon.ico?t=${Date.now()}`;
        });
    }

    async checkCameraConnections() {
        this.log('INFO', '检测摄像头连接状态...');
        
        let html = '<div class="loading">正在检测摄像头连接...</div>';
        this.elements.cameraConnectionStatus.innerHTML = html;
        
        try {
            // 尝试创建摄像头连接
            if (window.electronAPI?.connectUDP) {
                this.log('INFO', '尝试建立摄像头 UDP 连接...');
                
                const cameraConfig = {
                    host: '118.31.58.101',
                    port: 48991,
                    type: 'camera',
                    autoReconnect: true
                };
                
                const result = await window.electronAPI.connectUDP('camera_debug', cameraConfig);
                
                this.log('INFO', `摄像头连接结果: ${JSON.stringify(result)}`);
                
                if (result.success) {
                    html = `
                        <div class="test-result">
                            <i class="fas fa-circle test-icon success"></i>
                            <span class="status-label">摄像头连接:</span>
                            <span class="status-value status-success">✓ 连接成功</span>
                        </div>
                    `;
                    
                    // 尝试发送测试消息
                    this.log('INFO', '发送摄像头列表请求...');
                    
                    const messageResult = await window.electronAPI.sendUDPMessage('camera_debug', {
                        request_type: 'get_camera_list'
                    });
                    
                    this.log('INFO', `消息发送结果: ${JSON.stringify(messageResult)}`);
                    
                    html += `
                        <div class="test-result">
                            <i class="fas fa-circle test-icon ${messageResult.success ? 'success' : 'error'}"></i>
                            <span class="status-label">消息发送:</span>
                            <span class="status-value ${messageResult.success ? 'status-success' : 'status-error'}">
                                ${messageResult.success ? '✓ 发送成功' : '✗ 发送失败'}
                            </span>
                        </div>
                    `;
                    
                } else {
                    html = `
                        <div class="test-result">
                            <i class="fas fa-circle test-icon error"></i>
                            <span class="status-label">摄像头连接:</span>
                            <span class="status-value status-error">✗ 连接失败: ${result.error}</span>
                        </div>
                    `;
                }
                
            } else {
                html = `
                    <div class="test-result">
                        <i class="fas fa-circle test-icon error"></i>
                        <span class="status-label">ElectronAPI:</span>
                        <span class="status-value status-error">✗ connectUDP 方法不可用</span>
                    </div>
                `;
                this.log('ERROR', 'electronAPI.connectUDP 方法不可用');
            }
            
        } catch (error) {
            html = `
                <div class="test-result">
                    <i class="fas fa-circle test-icon error"></i>
                    <span class="status-label">摄像头连接:</span>
                    <span class="status-value status-error">✗ 连接异常: ${error.message}</span>
                </div>
            `;
            this.log('ERROR', `摄像头连接异常: ${error.message}`);
        }
        
        this.elements.cameraConnectionStatus.innerHTML = html;
    }

    log(level, message) {
        const timestamp = new Date().toLocaleTimeString();
        const logEntry = document.createElement('div');
        logEntry.className = 'log-entry';
        logEntry.innerHTML = `
            <span class="log-timestamp">[${timestamp}]</span>
            <span class="log-level ${level}">${level}</span>
            <span class="log-message">${message}</span>
        `;
        
        this.elements.debugLog.appendChild(logEntry);
        this.elements.debugLog.scrollTop = this.elements.debugLog.scrollHeight;
        
        // 同时输出到控制台
        console.log(`[CameraDebug] ${level}: ${message}`);
        
        // 使用 Logger 记录
        switch (level) {
            case 'ERROR':
                Logger.error(`[CameraDebug] ${message}`);
                break;
            case 'WARN':
                Logger.warn(`[CameraDebug] ${message}`);
                break;
            case 'DEBUG':
                Logger.debug(`[CameraDebug] ${message}`);
                break;
            default:
                Logger.info(`[CameraDebug] ${message}`);
        }
    }

    async beforeCleanup() {
        this.stopDiagnosis();
        
        // 清理测试连接
        try {
            if (window.electronAPI?.disconnectUDP) {
                await window.electronAPI.disconnectUDP('camera_debug');
            }
        } catch (error) {
            this.log('WARN', `清理测试连接失败: ${error.message}`);
        }
    }
}
