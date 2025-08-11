// 应用主控制器 - 管理全局状态和初始化
import Router from './router.js';
import EventBus from './eventBus.js';
import Logger from './utils/logger.js';
import { EVENTS } from './utils/constants.js';
import CONFIG from './config.js';
import { AudioPlayer } from './AudioPlayer.js';
import NotificationManager from './components/NotificationManager.js';

export default class App {
    constructor() {
        this.router = null;
        this.initialized = false;
        this.currentSession = null;
        this.audioPlayer = null;
        this.isMicListening = false;
    }

    async initialize() {
        if (this.initialized) {
            Logger.warn('Application already initialized');
            return;
        }

        try {
            // 初始化通知管理器
            this.initializeNotificationManager();
            
            // 初始化事件总线
            this.setupGlobalEventListeners();
            
            // 初始化路由
            this.router = new Router();
            await this.router.initialize();
            
            // 设置全局错误处理
            this.setupErrorHandling();
            
            // 启动默认页面
            await this.router.navigate('participant_management');

            // 初始化音频控制
            this.setupAudioControls();
            
            this.initialized = true;
            Logger.info('App initialization completed');
            
        } catch (error) {
            Logger.error('App initialization failed:', error);
            throw error;
        }
    }

    setupGlobalEventListeners() {
        // 监听会话状态变化
        EventBus.on(EVENTS.SESSION_STARTED, (sessionData) => {
            this.currentSession = sessionData;
            Logger.info('Session started:', sessionData);
        });

        EventBus.on(EVENTS.SESSION_ENDED, () => {
            this.currentSession = null;
            Logger.info('Session ended');
        });

        // 监听机器人状态
        if (window.electronAPI?.onRobotStatus) {
            window.electronAPI.onRobotStatus((status) => {
                EventBus.emit(EVENTS.ROBOT_STATUS_UPDATE, status);
            });
        }

        // 监听视频流
        if (window.electronAPI?.onVideoStream) {
            window.electronAPI.onVideoStream((videoData) => {
                EventBus.emit(EVENTS.VIDEO_STREAM_UPDATE, videoData);
            });
        }
    }

    /**
     * 初始化通知管理器
     */
    initializeNotificationManager() {
        if (!window.NotificationManager) {
            window.NotificationManager = new NotificationManager();
            Logger.info('NotificationManager initialized');
        }
    }

    setupErrorHandling() {
        window.addEventListener('error', (event) => {
            Logger.error('Global error:', event.error);
            // 使用新的通知系统显示错误
            if (window.NotificationManager) {
                window.NotificationManager.error('系统错误', '发生了未处理的错误，请查看控制台');
            }
        });

        window.addEventListener('unhandledrejection', (event) => {
            Logger.error('Unhandled promise rejection:', event.reason);
            // 使用新的通知系统显示错误
            if (window.NotificationManager) {
                window.NotificationManager.error('Promise错误', '发生了未处理的Promise错误');
            }
        });
    }

    getCurrentSession() {
        return this.currentSession;
    }

    setupAudioControls() {
        const micToggleButton = document.getElementById('mic-toggle-btn');
        if (!micToggleButton) {
            Logger.error("Microphone toggle button not found.");
            return;
        }

        // 从config.js构建正确的WebSocket URL
        const wsUrl = CONFIG.API.BASE_URL.replace(/^http/, 'ws') + '/api/ws/mic';
        Logger.info(`Connecting to microphone WebSocket at: ${wsUrl}`);
        
        this.audioPlayer = new AudioPlayer(wsUrl, { sampleRate: 16000 });

        micToggleButton.addEventListener('click', () => this.toggleMicListening());
    }

    async toggleMicListening() {
        const micToggleButton = document.getElementById('mic-toggle-btn');
        const icon = micToggleButton.querySelector('i');
        const text = micToggleButton.querySelector('span');

        this.isMicListening = !this.isMicListening;

        if (this.isMicListening) {
            try {
                await this.audioPlayer.connect();
                Logger.info("Microphone listening started.");
                micToggleButton.classList.remove('btn-secondary');
                micToggleButton.classList.add('btn-danger');
                icon.className = 'fas fa-microphone';
                text.textContent = 'off';
            } catch (error) {
                Logger.error("Failed to start microphone listening:", error);
                this.isMicListening = false; // Revert state on failure
            }
        } else {
            this.audioPlayer.disconnect();
            Logger.info("Microphone listening stopped.");
            micToggleButton.classList.remove('btn-danger');
            micToggleButton.classList.add('btn-secondary');
            icon.className = 'fas fa-microphone-slash';
            text.textContent = 'on';
        }
    }
}
