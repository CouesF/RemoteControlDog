/**
 * @file remote_control_handler.js
 * @description 远程控制WebSocket客户端处理器
 */
const WebSocket = require('ws');
const { ipcMain } = require('electron');
const { logger } = require('./utils/logger');

class RemoteControlHandler {
    constructor(window) {
        this.mainWindow = window;
        this.ws = null;
        this.isConnected = false;
        this.isAuthenticated = false;
        this.reconnectTimer = null;
        this.heartbeatTimer = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 10;
        this.reconnectDelay = 5000; // 5秒
        
        // 配置参数
        this.config = {
            serverUrl: 'ws://121.43.134.209:5000/socket.io/?EIO=4&transport=websocket',
            token: 'remote_control_2024',
            clientType: 'electron'
        };
        
        this._setupIpcListeners();
        this.connect();
    }

    _setupIpcListeners() {
        // 监听来自renderer的远程控制状态请求
        ipcMain.handle('get-remote-control-status', () => {
            return {
                isConnected: this.isConnected,
                isAuthenticated: this.isAuthenticated,
                reconnectAttempts: this.reconnectAttempts
            };
        });

        // 监听来自renderer的手动连接请求
        ipcMain.on('connect-remote-control', () => {
            this.connect();
        });

        // 监听来自renderer的断开连接请求
        ipcMain.on('disconnect-remote-control', () => {
            this.disconnect();
        });

        // 监听来自renderer的命令执行结果
        ipcMain.on('remote-control-result', (event, result) => {
            this.sendCommandResult(result);
        });
    }

    connect() {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            logger.info('[RemoteControl] Already connected');
            return;
        }

        try {
            logger.info('[RemoteControl] Attempting to connect to remote control server...');
            
            // 使用Socket.IO客户端连接
            const io = require('socket.io-client');
            this.ws = io('http://121.43.134.209:5000', {
                transports: ['websocket'],
                autoConnect: true
            });

            this._setupWebSocketEventHandlers();

        } catch (error) {
            logger.error(`[RemoteControl] Connection failed: ${error.message}`);
            this._scheduleReconnect();
        }
    }

    _setupWebSocketEventHandlers() {
        this.ws.on('connect', () => {
            logger.info('[RemoteControl] Connected to remote control server');
            this.isConnected = true;
            this.reconnectAttempts = 0;
            
            // 发送认证信息
            this._authenticate();
            
            // 通知renderer进程连接状态
            this._notifyRenderer('remote-control-connected');
            
            // 开始心跳
            this._startHeartbeat();
        });

        this.ws.on('disconnect', () => {
            logger.info('[RemoteControl] Disconnected from remote control server');
            this.isConnected = false;
            this.isAuthenticated = false;
            
            // 通知renderer进程断开连接
            this._notifyRenderer('remote-control-disconnected');
            
            // 停止心跳
            this._stopHeartbeat();
            
            // 尝试重连
            this._scheduleReconnect();
        });

        this.ws.on('auth_response', (data) => {
            if (data.success) {
                logger.info('[RemoteControl] Authentication successful');
                this.isAuthenticated = true;
                this._notifyRenderer('remote-control-authenticated');
            } else {
                logger.error(`[RemoteControl] Authentication failed: ${data.message}`);
                this._notifyRenderer('remote-control-auth-failed', data.message);
            }
        });

        this.ws.on('remote_command', (data) => {
            logger.info(`[RemoteControl] Received remote command: ${data.action}`);
            this._handleRemoteCommand(data);
        });

        this.ws.on('status_update', (data) => {
            this._notifyRenderer('remote-control-status-update', data);
        });

        this.ws.on('pong', (data) => {
            // 心跳响应
        });

        this.ws.on('connect_error', (error) => {
            logger.error(`[RemoteControl] Connection error: ${error.message}`);
            this._scheduleReconnect();
        });

        this.ws.on('error', (error) => {
            logger.error(`[RemoteControl] WebSocket error: ${error.message}`);
        });
    }

    _authenticate() {
        if (!this.ws || !this.isConnected) {
            return;
        }

        this.ws.emit('auth', {
            client_type: this.config.clientType,
            token: this.config.token
        });
    }

    _handleRemoteCommand(data) {
        const { action, from_client, timestamp } = data;
        
        try {
            // 发送命令到renderer进程处理
            this.mainWindow.webContents.send('remote-control-command', {
                action,
                from_client,
                timestamp
            });

            // 记录命令接收
            logger.info(`[RemoteControl] Command '${action}' forwarded to renderer`);

        } catch (error) {
            logger.error(`[RemoteControl] Error handling remote command: ${error.message}`);
            
            // 发送错误结果回服务器
            this._sendCommandResult({
                action,
                success: false,
                message: `命令处理错误: ${error.message}`
            });
        }
    }

    _sendCommandResult(result) {
        if (!this.ws || !this.isAuthenticated) {
            return;
        }

        this.ws.emit('command_result', result);
        logger.info(`[RemoteControl] Command result sent: ${result.action} - ${result.success}`);
    }

    _notifyRenderer(event, data = null) {
        if (this.mainWindow && this.mainWindow.webContents) {
            this.mainWindow.webContents.send(event, data);
        }
    }

    _startHeartbeat() {
        this._stopHeartbeat();
        
        this.heartbeatTimer = setInterval(() => {
            if (this.ws && this.isConnected) {
                this.ws.emit('ping', { timestamp: Date.now() });
            }
        }, 30000); // 每30秒发送心跳
    }

    _stopHeartbeat() {
        if (this.heartbeatTimer) {
            clearInterval(this.heartbeatTimer);
            this.heartbeatTimer = null;
        }
    }

    _scheduleReconnect() {
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
        }

        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            logger.error('[RemoteControl] Max reconnection attempts reached');
            this._notifyRenderer('remote-control-max-reconnect-reached');
            return;
        }

        this.reconnectAttempts++;
        const delay = this.reconnectDelay * this.reconnectAttempts;
        
        logger.info(`[RemoteControl] Scheduling reconnection attempt ${this.reconnectAttempts} in ${delay}ms`);
        
        this.reconnectTimer = setTimeout(() => {
            this.connect();
        }, delay);
    }

    disconnect() {
        logger.info('[RemoteControl] Manually disconnecting...');
        
        // 清理定时器
        this._stopHeartbeat();
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }

        // 断开连接
        if (this.ws) {
            this.ws.disconnect();
            this.ws = null;
        }

        this.isConnected = false;
        this.isAuthenticated = false;
        this.reconnectAttempts = 0;
        
        this._notifyRenderer('remote-control-disconnected');
    }

    // 从renderer进程接收命令执行结果
    sendCommandResult(result) {
        this._sendCommandResult(result);
    }

    cleanup() {
        logger.info('[RemoteControl] Cleaning up...');
        this.disconnect();
        
        // 移除IPC监听器
        ipcMain.removeAllListeners('get-remote-control-status');
        ipcMain.removeAllListeners('connect-remote-control');
        ipcMain.removeAllListeners('disconnect-remote-control');
        ipcMain.removeAllListeners('remote-control-result');
    }
}

module.exports = { RemoteControlHandler };