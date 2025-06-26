/**
 * @file udp_handler.js
 * @description Generic UDP connection handler for the main process.
 */
const dgram = require('dgram');
const { ipcMain } = require('electron');
const { logger } = require('./utils/logger');

class UDPHandler {
    constructor(window) {
        this.mainWindow = window;
        this.connections = new Map(); // Stores sockets by connectionId
        this._setupIpcListeners();
    }

    _setupIpcListeners() {
        ipcMain.handle('connect-udp', async (event, options) => {
            return this.createConnection(options);
        });

        ipcMain.on('disconnect-udp', (event, connectionId) => {
            this.closeConnection(connectionId);
        });
    }

    createConnection(options) {
        const { connectionId, host, port } = options;
        if (!connectionId || !host || !port) {
            logger.error(`[UDPHandler] Invalid options for connect-udp: ${JSON.stringify(options)}`);
            return { success: false, error: 'Invalid connection options' };
        }

        if (this.connections.has(connectionId)) {
            logger.warn(`[UDPHandler] Connection ${connectionId} already exists.`);
            return { success: true, connectionId };
        }

        const socket = dgram.createSocket('udp4');

        socket.on('message', (msg, rinfo) => {
            this.mainWindow.webContents.send(`udp-message-${connectionId}`, {
                message: msg, // msg is a Buffer
                sender: rinfo
            });
        });

        socket.on('error', (err) => {
            logger.error(`[UDPHandler] Socket error for ${connectionId}:\n${err.stack}`);
            this.mainWindow.webContents.send(`udp-error-${connectionId}`, { error: err.message });
            socket.close();
            this.connections.delete(connectionId);
        });

        socket.on('listening', () => {
            const address = socket.address();
            logger.info(`[UDPHandler] Socket ${connectionId} listening on ${address.address}:${address.port}`);
            this.mainWindow.webContents.send(`udp-connect-${connectionId}`);
        });
        
        socket.on('close', () => {
            logger.info(`[UDPHandler] Socket ${connectionId} closed.`);
            this.mainWindow.webContents.send(`udp-disconnect-${connectionId}`);
            this.connections.delete(connectionId);
        });

        // For UDP, there isn't a 'connect' event like TCP. We consider it "connected"
        // once it's listening and ready to send/receive. The remote address is set here.
        socket.connect(port, host, () => {
             logger.info(`[UDPHandler] UDP socket ${connectionId} connected to ${host}:${port}`);
        });

        this.connections.set(connectionId, socket);

        return { success: true, connectionId };
    }

    closeConnection(connectionId) {
        const socket = this.connections.get(connectionId);
        if (socket) {
            socket.close();
        } else {
            logger.warn(`[UDPHandler] Attempted to close non-existent connection: ${connectionId}`);
        }
    }

    closeAllConnections() {
        logger.info('[UDPHandler] Closing all UDP connections.');
        for (const connectionId of this.connections.keys()) {
            this.closeConnection(connectionId);
        }
    }
}

module.exports = { UDPHandler };
