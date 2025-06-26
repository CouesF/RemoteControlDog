/**
 * @file camera_udp_handler.js
 * @description Handles UDP communication with the camera gateway server.
 *
 * This module is responsible for:
 * - Managing a UDP socket to communicate with the camera gateway.
 * - Sending requests to get camera lists and subscribe/unsubscribe to streams.
 * - Receiving binary video frames and JSON responses.
 * - Reassembling fragmented data packets.
 * - Forwarding processed data to the renderer process via IPC.
 */

const dgram = require('dgram');
const { v4: uuidv4 } = require('uuid');
const { ipcMain } = require('electron');
const { logger } = require('./utils/logger');

// --- Constants ---
const SERVER_HOST = '118.31.58.101';
const SERVER_PORT = 48991;
const MAX_UDP_SIZE = 65507;
const FRAGMENT_TIMEOUT = 5000; // 5 seconds

// --- Protocol Constants ---
const MAGIC_BINARY_FRAME = 0xFF;
const MAGIC_FRAGMENT = 0xFE;

class CameraUDPHandler {
    constructor(window) {
        this.mainWindow = window;
        this.socket = dgram.createSocket('udp4');
        this.sessionId = null;
        this.subscribedCameras = new Set();
        this.fragmentBuffer = new Map();

        this._setupSocketListeners();
        this._setupIpcListeners();
    }

    _setupSocketListeners() {
        this.socket.on('message', (msg, rinfo) => {
            this._processReceivedData(msg);
        });

        this.socket.on('error', (err) => {
            logger.error(`Camera UDP socket error:\n${err.stack}`);
            this.socket.close();
        });

        this.socket.on('listening', () => {
            const address = this.socket.address();
            logger.info(`Camera UDP socket listening ${address.address}:${address.port}`);
        });
    }

    _setupIpcListeners() {
        ipcMain.handle('camera-gateway-connect', async () => {
            this.connect();
        });
        ipcMain.on('camera-gateway-disconnect', () => {
            this.disconnect();
        });
        ipcMain.on('camera-subscribe', (event, cameraIds) => {
            this.subscribe(cameraIds);
        });
        ipcMain.on('camera-unsubscribe', (event, cameraIds) => {
            this.unsubscribe(cameraIds);
        });
    }

    connect() {
        logger.info('Requesting camera list to test connection...');
        this.sessionId = uuidv4();
        this._sendPacket({ request_type: 'get_camera_list' });
        // Cleanup expired fragments periodically
        this.fragmentCleanupInterval = setInterval(() => this._cleanupExpiredFragments(), FRAGMENT_TIMEOUT);
    }

    disconnect() {
        if (this.subscribedCameras.size > 0) {
            this.unsubscribe(Array.from(this.subscribedCameras));
        }
        if (this.fragmentCleanupInterval) {
            clearInterval(this.fragmentCleanupInterval);
        }
        logger.info('Camera UDP handler disconnected.');
    }

    subscribe(cameraIds) {
        const newSubscriptions = cameraIds.filter(id => !this.subscribedCameras.has(id));
        if (newSubscriptions.length === 0) return;

        newSubscriptions.forEach(id => this.subscribedCameras.add(id));
        this._sendPacket({
            request_type: 'subscribe',
            camera_ids: Array.from(this.subscribedCameras),
            session_id: this.sessionId
        });
    }

    unsubscribe(cameraIds) {
        const idsToUnsubscribe = cameraIds.filter(id => this.subscribedCameras.has(id));
        if (idsToUnsubscribe.length === 0) return;

        idsToUnsubscribe.forEach(id => this.subscribedCameras.delete(id));
        
        const request = {
            request_type: this.subscribedCameras.size > 0 ? 'subscribe' : 'unsubscribe',
            camera_ids: Array.from(this.subscribedCameras),
            session_id: this.sessionId
        };
        this._sendPacket(request);

        // Notify the renderer process about the change in subscription
        this.mainWindow.webContents.send('subscription-changed', Array.from(this.subscribedCameras));
    }

    _sendPacket(data) {
        const payload = { timestamp: Date.now(), data };
        const payloadBytes = Buffer.from(JSON.stringify(payload));
        const headerBytes = Buffer.from('{}'); // Empty JSON header
        const headerLenPacked = Buffer.alloc(2);
        headerLenPacked.writeUInt16BE(headerBytes.length, 0);

        const fullPacket = Buffer.concat([headerLenPacked, headerBytes, payloadBytes]);
        this.socket.send(fullPacket, SERVER_PORT, SERVER_HOST, (err) => {
            if (err) logger.error(`Failed to send packet: ${err}`);
        });
    }

    _processReceivedData(data) {
        if (data.length === 0) return;
        const magic = data[0];

        if (magic === MAGIC_BINARY_FRAME) {
            this._handleBinaryFrame(data);
        } else if (magic === MAGIC_FRAGMENT) {
            const reassembled = this._addFragment(data);
            if (reassembled) {
                this._processReceivedData(reassembled);
            }
        } else {
            this._handleJsonPacket(data);
        }
    }

    _handleBinaryFrame(data) {
        try {
            // Format: Magic(B), Timestamp(Q), CamID(H), W(H), H(H), Quality(B), FrameID(8s), DataLen(I)
            const headerSize = 28; // Corrected: 1 + 8 + 2 + 2 + 2 + 1 + 8 + 4 = 28
            if (data.length < headerSize) return;

            const timestamp_us = data.readBigUInt64BE(1);
            const cameraId = data.readUInt16BE(9);
            const width = data.readUInt16BE(11);
            const height = data.readUInt16BE(13);
            const quality = data.readUInt8(15);
            const frameId = data.slice(16, 24).toString('ascii').trim();
            const dataLength = data.readUInt32BE(24); // This ends at byte 28
            const frameData = data.slice(headerSize, headerSize + dataLength);

            // Convert buffer to Base64 in the main process to avoid IPC issues.
            const frameDataB64 = frameData.toString('base64');

            this.mainWindow.webContents.send('camera-frame', {
                cameraId,
                frameData: frameDataB64, // Send as Base64 string
                timestamp: Number(timestamp_us) / 1e6,
                frameId,
                resolution: [width, height],
                quality,
            });
        } catch (e) {
            logger.error(`Error parsing binary frame: ${e.message}`);
        }
    }

    _addFragment(data) {
        try {
            // Format: Magic(B), FragID(8s), Index(H), Total(H), Length(H)
            if (data.length < 15) return null;

            const fragId = data.slice(1, 9).toString('ascii');
            const index = data.readUInt16BE(9);
            const total = data.readUInt16BE(11);
            const length = data.readUInt16BE(13);
            const chunk = data.slice(15, 15 + length);

            if (!this.fragmentBuffer.has(fragId)) {
                this.fragmentBuffer.set(fragId, {
                    chunks: new Array(total),
                    count: 0,
                    total,
                    timestamp: Date.now(),
                });
            }

            const buffer = this.fragmentBuffer.get(fragId);
            if (!buffer.chunks[index]) {
                buffer.chunks[index] = chunk;
                buffer.count++;
            }

            if (buffer.count === buffer.total) {
                const fullData = Buffer.concat(buffer.chunks);
                this.fragmentBuffer.delete(fragId);
                return fullData;
            }
            return null;
        } catch (e) {
            logger.error(`Error reassembling fragment: ${e.message}`);
            return null;
        }
    }

    _handleJsonPacket(data) {
        try {
            const headerLen = data.readUInt16BE(0);
            const payloadJson = data.slice(2 + headerLen).toString('utf-8');
            const packet = JSON.parse(payloadJson);

            if (packet.data) {
                this._handleResponse(packet.data);
            }
        } catch (e) {
            logger.error(`Failed to parse JSON packet: ${e.message}`);
        }
    }

    _handleResponse(response) {
        const msgType = response.message;
        if (msgType === 'camera_list') {
            // Defensive coding: Ensure we send an array, even if the response is missing the 'cameras' key.
            const cameras = response.cameras || [];
            this.mainWindow.webContents.send('camera-list', cameras);
        } else if (msgType === 'subscription_confirmed') {
            const cameraIds = response.camera_ids || [];
            this.mainWindow.webContents.send('subscription-changed', cameraIds);
        } else {
            logger.info(`Server message: ${JSON.stringify(response)}`);
        }
    }

    _cleanupExpiredFragments() {
        const now = Date.now();
        for (const [fragId, buffer] of this.fragmentBuffer.entries()) {
            if (now - buffer.timestamp > FRAGMENT_TIMEOUT) {
                this.fragmentBuffer.delete(fragId);
                logger.warn(`Cleaned up expired fragment buffer: ${fragId}`);
            }
        }
    }
}

module.exports = { CameraUDPHandler };
