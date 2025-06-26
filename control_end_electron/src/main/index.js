// control_end_electron/src/main/index.js
const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const dotenv = require('dotenv');
const { CameraUDPHandler } = require('./camera_udp_handler');
const { UDPHandler } = require('./udp_handler');

// --- Configuration ---
dotenv.config({ path: path.join(__dirname, '..', '..', '..', '.env'), override: true });

let mainWindow;
let cameraHandler;
let udpHandler;

function createWindow() {
    mainWindow = new BrowserWindow({
        width: 1200,
        height: 900,
        webPreferences: {
            preload: path.join(__dirname, '..', 'preload', 'preload.js'),
            contextIsolation: true,
            nodeIntegration: false
        }
    });
    mainWindow.loadFile(path.join(__dirname, '..', 'renderer', 'index.html'));
    mainWindow.webContents.openDevTools();
}

app.whenReady().then(() => {
    createWindow();

    // Initialize handlers
    cameraHandler = new CameraUDPHandler(mainWindow);
    udpHandler = new UDPHandler(mainWindow);

    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) {
            createWindow();
        }
    });
});

app.on('window-all-closed', () => {
    if (cameraHandler) {
        cameraHandler.disconnect();
    }
    if (udpHandler) {
        udpHandler.closeAllConnections();
    }
    if (process.platform !== 'darwin') {
        app.quit();
    }
    console.log("CE_Main: App quit.");
});

// Keep existing IPC handlers for robot control if they are still needed.
// For this refactoring, we are focusing on camera logic.
// All camera-related IPC is now handled within CameraUDPHandler.
