// UDP连接管理器 - 组件化设计，支持动态添加/移除
import BaseComponent from './BaseComponent.js';
import { EVENTS } from '../utils/constants.js';
import Logger from '../utils/logger.js';

export default class UDPConnectionManager extends BaseComponent {
    constructor() {
        super();
        
        this.connections = new Map(); // 连接池
        this.isInitialized = false;
        this.reconnectIntervals = new Map(); // 重连定时器
        this.maxRetries = 10;
        this.baseRetryDelay = 1000;
        
        // 连接配置
        this.connectionConfigs = {
            control: {
                host: '118.31.58.101',
                port: 48990,
                localPort: 8990,
                type: 'control',
                autoReconnect: true
            },
            camera: {
                host: '118.31.58.101', 
                port: 48991,
                localPort: 8991,
                type: 'camera',
                autoReconnect: true
            }
        };
        
        this.stats = {
            totalConnections: 0,
            activeConnections: 0,
            packetsReceived: 0,
            packetsSent: 0,
            errors: 0
        };
    }

    async initialize() {
        if (this.isInitialized) return;
        
        try {
            // 初始化UDP客户端
            if (window.electronAPI?.initializeUDP) {
                const result = await window.electronAPI.initializeUDP();
                if (!result.success) {
                    throw new Error(result.error || 'UDP初始化失败');
                }
                Logger.info('UDP客户端初始化成功');
            }
            
            // 监听UDP消息
            this.setupEventListeners();
            
            this.isInitialized = true;
            Logger.info('UDP连接管理器初始化完成');
            
        } catch (error) {
            Logger.error('UDP连接管理器初始化失败:', error);
            throw error;
        }
    }

    setupEventListeners() {
        // 监听UDP消息
        if (window.electronAPI?.onUDPMessage) {
            window.electronAPI.onUDPMessage((data) => {
                this.handleUDPMessage(data);
            });
        }

        // 监听连接状态变化
        if (window.electronAPI?.onConnectionStatusChange) {
            window.electronAPI.onConnectionStatusChange((status) => {
                this.handleConnectionStatusChange(status);
            });
        }
    }

    /**
     * 创建连接
     * @param {string} connectionId - 连接ID
     * @param {Object} config - 连接配置
     * @returns {Promise<UDPConnection>}
     */
    async createConnection(connectionId, config = null) {
        if (this.connections.has(connectionId)) {
            Logger.warn(`连接 ${connectionId} 已存在`);
            return this.connections.get(connectionId);
        }

        const connectionConfig = config || this.connectionConfigs[connectionId];
        if (!connectionConfig) {
            throw new Error(`未找到连接配置: ${connectionId}`);
        }

        const connection = new UDPConnection(connectionId, connectionConfig, this);
        this.connections.set(connectionId, connection);
        this.stats.totalConnections++;

        Logger.info(`创建连接: ${connectionId}`);
        
        // 自动连接
        if (connectionConfig.autoReconnect) {
            await this.connectWithRetry(connectionId);
        }

        return connection;
    }

    /**
     * 移除连接
     * @param {string} connectionId - 连接ID
     */
    async removeConnection(connectionId) {
        const connection = this.connections.get(connectionId);
        if (!connection) {
            Logger.warn(`连接 ${connectionId} 不存在`);
            return;
        }

        // 停止重连
        this.stopReconnect(connectionId);
        
        // 断开连接
        await connection.disconnect();
        
        // 从连接池移除
        this.connections.delete(connectionId);
        
        Logger.info(`移除连接: ${connectionId}`);
        
        // 触发事件
        this.emitEvent(EVENTS.UDP_CONNECTION_REMOVED, { connectionId });
    }

    /**
     * 获取连接
     * @param {string} connectionId - 连接ID
     * @returns {UDPConnection|null}
     */
    getConnection(connectionId) {
        return this.connections.get(connectionId) || null;
    }

    /**
     * 带重试的连接
     * @param {string} connectionId - 连接ID
     */
    async connectWithRetry(connectionId) {
        const connection = this.connections.get(connectionId);
        if (!connection) {
            Logger.error(`连接 ${connectionId} 不存在`);
            return;
        }

        let retryCount = 0;
        const maxRetries = this.maxRetries;

        const attemptConnect = async () => {
            try {
                await connection.connect();
                retryCount = 0; // 重置重试计数
                this.stats.activeConnections++;
                
                Logger.info(`连接 ${connectionId} 建立成功`);
                this.emitEvent(EVENTS.UDP_CONNECTION_ESTABLISHED, { 
                    connectionId, 
                    config: connection.config 
                });
                
            } catch (error) {
                retryCount++;
                Logger.warn(`连接 ${connectionId} 失败 (尝试 ${retryCount}/${maxRetries}): ${error.message}`);
                
                if (retryCount < maxRetries && connection.config.autoReconnect) {
                    const delay = this.baseRetryDelay * Math.pow(2, Math.min(retryCount - 1, 5));
                    Logger.info(`${delay}ms 后重试连接 ${connectionId}`);
                    
                    const timeoutId = setTimeout(attemptConnect, delay);
                    this.reconnectIntervals.set(connectionId, timeoutId);
                } else {
                    Logger.error(`连接 ${connectionId} 达到最大重试次数，停止重连`);
                    this.emitEvent(EVENTS.UDP_CONNECTION_FAILED, { 
                        connectionId, 
                        error: error.message 
                    });
                }
            }
        };

        await attemptConnect();
    }

    /**
     * 停止重连
     * @param {string} connectionId - 连接ID
     */
    stopReconnect(connectionId) {
        const timeoutId = this.reconnectIntervals.get(connectionId);
        if (timeoutId) {
            clearTimeout(timeoutId);
            this.reconnectIntervals.delete(connectionId);
            Logger.info(`停止重连: ${connectionId}`);
        }
    }

    /**
     * 处理UDP消息
     * @param {Object} data - 消息数据
     */
    handleUDPMessage(data) {
        const { connectionId, message, timestamp } = data;
        this.stats.packetsReceived++;
        
        const connection = this.connections.get(connectionId);
        if (connection) {
            connection.handleMessage(message, timestamp);
        } else {
            Logger.warn(`收到未知连接的消息: ${connectionId}`);
        }
    }

    /**
     * 处理连接状态变化
     * @param {Object} status - 状态信息
     */
    handleConnectionStatusChange(status) {
        const { connectionId, isConnected, error } = status;
        const connection = this.connections.get(connectionId);
        
        if (connection) {
            connection.updateStatus(isConnected, error);
            
            if (!isConnected && connection.config.autoReconnect) {
                Logger.info(`连接 ${connectionId} 断开，启动自动重连`);
                this.connectWithRetry(connectionId);
            }
        }
    }

    /**
     * 发送消息
     * @param {string} connectionId - 连接ID
     * @param {Object} message - 消息内容
     * @returns {Promise<boolean>}
     */
    async sendMessage(connectionId, message) {
        const connection = this.connections.get(connectionId);
        if (!connection) {
            Logger.error(`连接 ${connectionId} 不存在`);
            return false;
        }

        return await connection.sendMessage(message);
    }

    /**
     * 获取所有连接状态
     * @returns {Object}
     */
    getConnectionsStatus() {
        const status = {};
        for (const [id, connection] of this.connections) {
            status[id] = {
                id,
                type: connection.config.type,
                isConnected: connection.isConnected,
                lastActivity: connection.lastActivity,
                stats: connection.stats
            };
        }
        return status;
    }

    /**
     * 获取统计信息
     * @returns {Object}
     */
    getStats() {
        return {
            ...this.stats,
            connections: this.getConnectionsStatus()
        };
    }

    /**
     * 清理资源
     */
    async cleanup() {
        Logger.info('清理UDP连接管理器...');
        
        // 停止所有重连
        for (const connectionId of this.reconnectIntervals.keys()) {
            this.stopReconnect(connectionId);
        }
        
        // 断开所有连接
        const disconnectPromises = [];
        for (const connection of this.connections.values()) {
            disconnectPromises.push(connection.disconnect());
        }
        
        await Promise.all(disconnectPromises);
        
        // 清空连接池
        this.connections.clear();
        this.isInitialized = false;
        
        Logger.info('UDP连接管理器清理完成');
    }
}

/**
 * UDP连接类
 */
class UDPConnection {
    constructor(id, config, manager) {
        this.id = id;
        this.config = config;
        this.manager = manager;
        this.isConnected = false;
        this.lastActivity = null;
        this.messageHandlers = new Map();
        this.stats = {
            messagesSent: 0,
            messagesReceived: 0,
            errors: 0,
            lastError: null
        };
    }

    /**
     * 连接
     */
    async connect() {
        try {
            // 尝试新的API命名方式
            if (window.electronAPI?.connectUDP) {
                const result = await window.electronAPI.connectUDP(this.id, this.config);
                if (!result.success) {
                    throw new Error(result.error || '连接失败');
                }
                this.isConnected = true;
                this.lastActivity = Date.now();
                Logger.info(`UDP连接 ${this.id} 已建立`);
            } else if (window.electronAPI?.['connect-udp']) {
                // 尝试旧的API命名方式
                const result = await window.electronAPI['connect-udp'](this.id, this.config);
                if (!result.success) {
                    throw new Error(result.error || '连接失败');
                }
                this.isConnected = true;
                this.lastActivity = Date.now();
                Logger.info(`UDP连接 ${this.id} 已建立`);
            } else {
                throw new Error('UDP连接API不可用 (connectUDP 或 connect-udp)');
            }
        } catch (error) {
            this.stats.errors++;
            this.stats.lastError = error.message;
            Logger.error(`UDP连接失败 [${this.id}]:`, error);
            throw error;
        }
    }

    /**
     * 断开连接
     */
    async disconnect() {
        try {
            if (window.electronAPI?.disconnectUDP) {
                await window.electronAPI.disconnectUDP(this.id);
            } else if (window.electronAPI?.['disconnect-udp']) {
                await window.electronAPI['disconnect-udp'](this.id);
            }
            this.isConnected = false;
            Logger.info(`UDP连接 ${this.id} 已断开`);
        } catch (error) {
            Logger.error(`断开连接 ${this.id} 失败:`, error);
        }
    }

    /**
     * 发送消息
     * @param {Object} message - 消息内容
     * @returns {Promise<boolean>}
     */
    async sendMessage(message) {
        if (!this.isConnected) {
            Logger.warn(`连接 ${this.id} 未建立，无法发送消息`);
            return false;
        }

        try {
            if (window.electronAPI?.sendUDPMessage) {
                const result = await window.electronAPI.sendUDPMessage(this.id, message);
                if (!result.success) {
                    throw new Error(result.error || '发送失败');
                }
                this.stats.messagesSent++;
                this.lastActivity = Date.now();
                this.manager.stats.packetsSent++;
                return true;
            } else if (window.electronAPI?.['send-udp-message']) {
                const result = await window.electronAPI['send-udp-message'](this.id, message);
                if (!result.success) {
                    throw new Error(result.error || '发送失败');
                }
                this.stats.messagesSent++;
                this.lastActivity = Date.now();
                this.manager.stats.packetsSent++;
                return true;
            } else {
                throw new Error('UDP消息发送API不可用 (sendUDPMessage 或 send-udp-message)');
            }
        } catch (error) {
            this.stats.errors++;
            this.stats.lastError = error.message;
            Logger.error(`发送消息失败 [${this.id}]:`, error);
            return false;
        }
    }

    /**
     * 处理接收到的消息
     * @param {Object} message - 消息内容
     * @param {number} timestamp - 时间戳
     */
    handleMessage(message, timestamp) {
        this.stats.messagesReceived++;
        this.lastActivity = Date.now();

        // 根据消息类型分发处理
        const messageType = message.message_type || message.type || 'default';
        const handler = this.messageHandlers.get(messageType);
        
        if (handler) {
            try {
                handler(message, timestamp);
            } catch (error) {
                Logger.error(`消息处理失败 [${this.id}/${messageType}]:`, error);
            }
        } else {
            // 默认处理：触发事件
            this.manager.emitEvent(EVENTS.UDP_MESSAGE_RECEIVED, {
                connectionId: this.id,
                messageType,
                message,
                timestamp
            });
        }
    }

    /**
     * 注册消息处理器
     * @param {string} messageType - 消息类型
     * @param {Function} handler - 处理函数
     */
    registerMessageHandler(messageType, handler) {
        this.messageHandlers.set(messageType, handler);
        Logger.debug(`注册消息处理器 [${this.id}/${messageType}]`);
    }

    /**
     * 移除消息处理器
     * @param {string} messageType - 消息类型
     */
    unregisterMessageHandler(messageType) {
        this.messageHandlers.delete(messageType);
        Logger.debug(`移除消息处理器 [${this.id}/${messageType}]`);
    }

    /**
     * 更新连接状态
     * @param {boolean} isConnected - 是否连接
     * @param {string} error - 错误信息
     */
    updateStatus(isConnected, error = null) {
        const wasConnected = this.isConnected;
        this.isConnected = isConnected;
        
        if (error) {
            this.stats.errors++;
            this.stats.lastError = error;
        }

        // 触发状态变化事件
        if (wasConnected !== isConnected) {
            this.manager.emitEvent(EVENTS.UDP_CONNECTION_STATUS_CHANGED, {
                connectionId: this.id,
                isConnected,
                error
            });
        }
    }
}

// 全局UDP连接管理器实例
let globalUDPManager = null;

/**
 * 获取全局UDP连接管理器
 * @returns {UDPConnectionManager}
 */
export function getUDPManager() {
    if (!globalUDPManager) {
        globalUDPManager = new UDPConnectionManager();
    }
    return globalUDPManager;
}

/**
 * 初始化全局UDP连接管理器
 * @returns {Promise<UDPConnectionManager>}
 */
export async function initializeUDPManager() {
    const manager = getUDPManager();
    if (!manager.isInitialized) {
        await manager.initialize();
    }
    return manager;
}
