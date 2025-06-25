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
                    this.socket.bind(this.config.localPort, (err) => {
                        if (err) reject(err);
                        else resolve();
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
