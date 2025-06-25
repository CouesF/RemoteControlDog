// control_end_electron/src/main/camera_udp_handler.js
const dgram = require('dgram');

class CameraUDPManager {
    constructor() {
        this.connections = new Map();
        this.mainWindow = null;
        this.isInitialized = false;
    }

    initialize(mainWindow) {
        this.mainWindow = mainWindow;
        this.isInitialized = true;
        console.log('Camera UDP Manager initialized');
    }

    async createConnection(connectionId, config) {
        if (this.connections.has(connectionId)) {
            console.warn(`Connection ${connectionId} already exists`);
            return this.connections.get(connectionId);
        }

        const connection = new CameraUDPConnection(connectionId, config, this);
        this.connections.set(connectionId, connection);
        
        console.log(`Created camera UDP connection: ${connectionId}`);
        return connection;
    }

    async removeConnection(connectionId) {
        const connection = this.connections.get(connectionId);
        if (connection) {
            await connection.disconnect();
            this.connections.delete(connectionId);
            console.log(`Removed camera UDP connection: ${connectionId}`);
        }
    }

    getConnection(connectionId) {
        return this.connections.get(connectionId);
    }

    notifyRenderer(event, data) {
        if (this.mainWindow && this.mainWindow.webContents && !this.mainWindow.isDestroyed()) {
            this.mainWindow.webContents.send(event, data);
        }
    }

    cleanup() {
        for (const connection of this.connections.values()) {
            connection.disconnect();
        }
        this.connections.clear();
        console.log('Camera UDP Manager cleaned up');
    }
}

class CameraUDPConnection {
    constructor(id, config, manager) {
        this.id = id;
        this.config = config;
        this.manager = manager;
        this.socket = null;
        this.isConnected = false;
        this.messageHandlers = new Map();
        this.fragmentBuffers = new Map();
        this.stats = {
            messagesSent: 0,
            messagesReceived: 0,
            errors: 0
        };
    }

    async connect() {
        try {
            this.socket = dgram.createSocket('udp4');
            
            this.socket.on('error', (err) => {
                console.error(`Camera UDP connection ${this.id} error:`, err);
                this.stats.errors++;
                this.updateConnectionStatus(false, err.message);
            });

            this.socket.on('message', (msg, rinfo) => {
                this.handleMessage(msg, rinfo);
            });

            // Bind to local port if specified
            if (this.config.localPort && this.config.localPort > 0) {
                await new Promise((resolve, reject) => {
                    this.socket.bind(this.config.localPort, () => {
                        console.log(`Camera UDP connection ${this.id} bound to local port ${this.config.localPort}`);
                        resolve();
                    });
                    this.socket.on('error', (err) => {
                        console.error(`Camera UDP socket error during bind on port ${this.config.localPort}:`, err);
                        reject(err);
                    });
                });
            }

            this.isConnected = true;
            this.updateConnectionStatus(true);
            
            console.log(`Camera UDP connection ${this.id} established to ${this.config.host}:${this.config.port}`);
            
        } catch (error) {
            this.stats.errors++;
            throw error;
        }
    }

    async disconnect() {
        if (this.socket) {
            this.socket.close();
            this.socket = null;
        }
        this.isConnected = false;
        this.updateConnectionStatus(false);
        console.log(`Camera UDP connection ${this.id} disconnected`);
    }

    async sendMessage(message) {
        if (!this.isConnected || !this.socket) {
            throw new Error(`Connection ${this.id} is not connected`);
        }

        try {
            const packet = this.preparePacket(message);
            const fragments = this.fragmentPacket(packet);

            for (const fragment of fragments) {
                await new Promise((resolve, reject) => {
                    this.socket.send(fragment, this.config.port, this.config.host, (err) => {
                        if (err) reject(err);
                        else resolve();
                    });
                });
            }

            this.stats.messagesSent++;
            return true;

        } catch (error) {
            this.stats.errors++;
            console.error(`Failed to send message on connection ${this.id}:`, error);
            throw error;
        }
    }

    preparePacket(data) {
        const timestamp = Date.now();
        const packet = {
            timestamp,
            data
        };
        
        return JSON.stringify(packet);
    }

    fragmentPacket(packet) {
        const packetBytes = Buffer.from(packet, 'utf8');
        const maxSize = 1400; // Safe UDP size
        
        if (packetBytes.length <= maxSize) {
            return [packetBytes];
        }

        // Fragment large packets
        const fragments = [];
        const fragmentId = Math.random().toString(36).substr(2, 8);
        const chunkSize = maxSize - 100; // Reserve space for fragment header
        const totalFragments = Math.ceil(packetBytes.length / chunkSize);

        for (let i = 0; i < totalFragments; i++) {
            const start = i * chunkSize;
            const end = Math.min(start + chunkSize, packetBytes.length);
            const chunk = packetBytes.slice(start, end);

            const fragmentHeader = {
                fragment_id: fragmentId,
                fragment_index: i,
                total_fragments: totalFragments,
                is_last: i === totalFragments - 1
            };

            const headerBytes = Buffer.from(JSON.stringify(fragmentHeader), 'utf8');
            const headerSize = Buffer.alloc(2);
            headerSize.writeUInt16BE(headerBytes.length, 0);

            const fragment = Buffer.concat([headerSize, headerBytes, chunk]);
            fragments.push(fragment);
        }

        return fragments;
    }

    handleMessage(data, rinfo) {
        try {
            this.stats.messagesReceived++;
            
            // 检查是否为二进制帧数据
            if (data.length > 0 && (data[0] === 0xFF || data[0] === 0xFE)) {
                this.handleBinaryFrame(data, rinfo);
                return;
            }
            
            // 处理JSON数据包
            const packet = this.processReceivedPacket(data, rinfo);
            if (!packet) return;

            // Notify renderer process
            this.manager.notifyRenderer('udp-message', {
                connectionId: this.id,
                message: packet.data,
                timestamp: packet.timestamp
            });

        } catch (error) {
            this.stats.errors++;
            console.error(`Error handling message on connection ${this.id}:`, error);
        }
    }

    processReceivedPacket(data, addr) {
        try {
            // Check if this is a fragmented packet
            if (data.length < 2) return null;

            const headerSize = data.readUInt16BE(0);
            if (data.length < 2 + headerSize) return null;

            const headerBytes = data.slice(2, 2 + headerSize);
            const header = JSON.parse(headerBytes.toString('utf8'));

            // Handle fragmented packets
            if (header.fragment_id) {
                return this.handleFragment(header, data.slice(2 + headerSize), addr);
            } else {
                // Complete packet - handle both security header and direct data
                const packetData = data.slice(2 + headerSize);
                
                // Check if this has a security signature (backend format)
                if (header.signature && header.size) {
                    // Backend format with security header
                    return JSON.parse(packetData.toString('utf8'));
                } else {
                    // Direct JSON data
                    return JSON.parse(packetData.toString('utf8'));
                }
            }

        } catch (error) {
            console.error(`Error processing packet:`, error);
            return null;
        }
    }

    handleFragment(header, chunk, addr) {
        const fragmentId = header.fragment_id;
        const fragmentIndex = header.fragment_index;
        const totalFragments = header.total_fragments;

        // Initialize fragment buffer
        if (!this.fragmentBuffers.has(fragmentId)) {
            this.fragmentBuffers.set(fragmentId, {
                chunks: {},
                totalFragments,
                addr,
                timestamp: Date.now()
            });
        }

        // Store fragment
        const buffer = this.fragmentBuffers.get(fragmentId);
        buffer.chunks[fragmentIndex] = chunk;

        // Check if all fragments received
        if (Object.keys(buffer.chunks).length === totalFragments) {
            // Reassemble packet
            let completeData = Buffer.alloc(0);
            for (let i = 0; i < totalFragments; i++) {
                completeData = Buffer.concat([completeData, buffer.chunks[i]]);
            }

            // Clean up
            this.fragmentBuffers.delete(fragmentId);

            // Parse complete packet
            try {
                return JSON.parse(completeData.toString('utf8'));
            } catch (error) {
                console.error('Error parsing reassembled packet:', error);
                return null;
            }
        }

        return null; // Still waiting for more fragments
    }

    handleBinaryFrame(data, rinfo) {
        try {
            if (data[0] === 0xFF) {
                // 完整二进制帧
                this.processBinaryFrame(data);
            } else if (data[0] === 0xFE) {
                // 分片二进制帧
                this.processBinaryFragment(data);
            }
        } catch (error) {
            console.error(`Error handling binary frame:`, error);
            this.stats.errors++;
        }
    }

    processBinaryFrame(data) {
        try {
            // 解析二进制帧头部
            // 格式: 魔数(1) + 时间戳(8) + 摄像头ID(2) + 宽度(2) + 高度(2) + 质量(1) + 帧ID(8) + 数据长度(4)
            if (data.length < 28) return;

            let offset = 1; // 跳过魔数
            
            // 读取时间戳 (8字节，大端序)
            const timestamp = data.readBigUInt64BE(offset) / 1000000; // 转换为秒
            offset += 8;
            
            // 读取摄像头ID (2字节)
            const cameraId = data.readUInt16BE(offset);
            offset += 2;
            
            // 读取分辨率 (4字节)
            const width = data.readUInt16BE(offset);
            offset += 2;
            const height = data.readUInt16BE(offset);
            offset += 2;
            
            // 读取质量 (1字节)
            const quality = data.readUInt8(offset);
            offset += 1;
            
            // 读取帧ID (8字节)
            const frameIdBytes = data.slice(offset, offset + 8);
            const frameId = frameIdBytes.toString('ascii').replace(/\0/g, '');
            offset += 8;
            
            // 读取数据长度 (4字节)
            const dataLength = data.readUInt32BE(offset);
            offset += 4;
            
            // 读取图像数据
            if (data.length < offset + dataLength) {
                console.warn('Incomplete binary frame data');
                return;
            }
            
            const imageData = data.slice(offset, offset + dataLength);
            
            // 转换为Base64用于前端显示
            const base64Data = imageData.toString('base64');
            
            // 通知渲染进程
            this.manager.notifyRenderer('camera-frame', {
                connectionId: this.id,
                cameraId,
                frameId,
                timestamp,
                resolution: [width, height],
                quality,
                data: base64Data,
                dataUrl: `data:image/jpeg;base64,${base64Data}`
            });
            
        } catch (error) {
            console.error('Error processing binary frame:', error);
            this.stats.errors++;
        }
    }

    processBinaryFragment(data) {
        try {
            // 解析分片头部
            // 格式: 魔数(1) + 分片ID(8) + 分片索引(2) + 总分片数(2) + 数据长度(2)
            if (data.length < 15) return;

            let offset = 1; // 跳过魔数
            
            // 读取分片ID (8字节)
            const fragmentId = data.slice(offset, offset + 8).toString('ascii');
            offset += 8;
            
            // 读取分片索引 (2字节)
            const fragmentIndex = data.readUInt16BE(offset);
            offset += 2;
            
            // 读取总分片数 (2字节)
            const totalFragments = data.readUInt16BE(offset);
            offset += 2;
            
            // 读取数据长度 (2字节)
            const chunkLength = data.readUInt16BE(offset);
            offset += 2;
            
            // 读取分片数据
            const chunkData = data.slice(offset, offset + chunkLength);
            
            // 初始化分片缓冲区
            if (!this.fragmentBuffers.has(fragmentId)) {
                this.fragmentBuffers.set(fragmentId, {
                    chunks: {},
                    totalFragments,
                    timestamp: Date.now()
                });
            }
            
            // 存储分片
            const buffer = this.fragmentBuffers.get(fragmentId);
            buffer.chunks[fragmentIndex] = chunkData;
            
            // 检查是否收集完所有分片
            if (Object.keys(buffer.chunks).length === totalFragments) {
                // 重组完整数据
                let completeData = Buffer.alloc(0);
                for (let i = 0; i < totalFragments; i++) {
                    completeData = Buffer.concat([completeData, buffer.chunks[i]]);
                }
                
                // 清理缓冲区
                this.fragmentBuffers.delete(fragmentId);
                
                // 处理重组后的完整帧
                this.processBinaryFrame(completeData);
            }
            
        } catch (error) {
            console.error('Error processing binary fragment:', error);
            this.stats.errors++;
        }
    }

    updateConnectionStatus(isConnected, error = null) {
        this.isConnected = isConnected;
        
        this.manager.notifyRenderer('connection-status-change', {
            connectionId: this.id,
            isConnected,
            error
        });
    }

    registerMessageHandler(messageType, handler) {
        this.messageHandlers.set(messageType, handler);
    }

    unregisterMessageHandler(messageType) {
        this.messageHandlers.delete(messageType);
    }
}

// Global instance
let cameraUDPManager = null;

function getCameraUDPManager() {
    if (!cameraUDPManager) {
        cameraUDPManager = new CameraUDPManager();
    }
    return cameraUDPManager;
}

module.exports = {
    getCameraUDPManager,
    CameraUDPManager,
    CameraUDPConnection
};
