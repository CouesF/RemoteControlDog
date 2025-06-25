// 应用主控制器 - 管理全局状态和初始化
import Router from './router.js';
import EventBus from './eventBus.js';
import Logger from './utils/logger.js';
import { EVENTS } from './utils/constants.js';

export default class App {
    constructor() {
        this.router = null;
        this.initialized = false;
        this.currentSession = null;
    }

    async initialize() {
        if (this.initialized) {
            Logger.warn('Application already initialized');
            return;
        }

        try {
            // 初始化事件总线
            this.setupGlobalEventListeners();
            
            // 初始化路由
            this.router = new Router();
            await this.router.initialize();
            
            // 设置全局错误处理
            this.setupErrorHandling();
            
            // 启动默认页面
            await this.router.navigate('participant_management');
            
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

    setupErrorHandling() {
        window.addEventListener('error', (event) => {
            Logger.error('Global error:', event.error);
        });

        window.addEventListener('unhandledrejection', (event) => {
            Logger.error('Unhandled promise rejection:', event.reason);
        });
    }

    getCurrentSession() {
        return this.currentSession;
    }
}