// control_end_electron/src/main/index.js
const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const dotenv = require('dotenv');

const protobufHandler = require('./protobuf_handler');
const udpHandler = require('./udp_handler');

// --- Configuration ---
// Load .env from project root: RemoteControlDog/.env
const projectRootEnvPath = path.join(__dirname, '..', '..', '..', '.env');
if (require('fs').existsSync(projectRootEnvPath)) {
    dotenv.config({ path: projectRootEnvPath, override: true });
    console.log(`CE_Main: Loaded .env from project root: ${projectRootEnvPath}`);
} else {
    // Fallback to .env in control_end_electron/ if root .env not found
    const localEnvPath = path.join(__dirname, '..', '..', '.env');
    if (require('fs').existsSync(localEnvPath)) {
        dotenv.config({ path: localEnvPath, override: true });
        console.log(`CE_Main: Loaded .env from local: ${localEnvPath}`);
    } else {
        console.warn(`CE_Main: Warning - .env file not found at ${projectRootEnvPath} or ${localEnvPath}. Using defaults or environment variables.`);
    }
}

const CE_CLIENT_ID = process.env.CE_CLIENT_ID || "controller_main_default";
const TARGET_CS_HOST = process.env.TARGET_CS_HOST || "127.0.0.1";
const TARGET_CS_PORT = parseInt(process.env.TARGET_CS_PORT || "9000", 10);
const CE_LISTEN_PORT = parseInt(process.env.CE_LISTEN_PORT || "0", 10); // 0 for random
const RD_TARGET_CLIENT_ID = process.env.RD_CLIENT_ID || "robot_dog_alpha"; // For sending commands

let mainWindow;

function createWindow() {
    mainWindow = new BrowserWindow({
        width: 1000,
        height: 800,
        webPreferences: {
            preload: path.join(__dirname, '..', 'preload', 'preload.js'), // Correct path to preload
            contextIsolation: true,
            nodeIntegration: false
        }
    });
    // mainWindow.loadFile('index.html'); // This will be relative to project root if not careful
    mainWindow.loadFile(path.join(__dirname, '..', 'renderer', 'index.html')); // Correct path to index.html
    // mainWindow.webContents.openDevTools();
}

app.whenReady().then(async () => {
    try {
        await protobufHandler.loadProtoDefinitions();
        console.log("CE_Main: Protobuf definitions initialized.");
    } catch (error) {
        console.error("CE_Main: Critical error loading protobuf definitions. Application will exit.", error);
        app.quit();
        return;
    }

    createWindow();
    udpHandler.initUdpClient(CE_CLIENT_ID, TARGET_CS_HOST, TARGET_CS_PORT, CE_LISTEN_PORT, mainWindow);

    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) {
            createWindow();
        }
    });
});

app.on('window-all-closed', () => {
    udpHandler.closeUdpClient();
    if (process.platform !== 'darwin') {
        app.quit();
    }
    console.log("CE_Main: App quit.");
});

// IPC example for sending control commands from renderer
ipcMain.on('send-control-command', (event, command) => {
    // command = { linearX: 0.5, linearY: 0.0, angularZ: 0.1 }
    console.log("CE_Main: Received 'send-control-command' from renderer:", command);
    if (command && typeof command.linearX === 'number' && 
        typeof command.linearY === 'number' && 
        typeof command.angularZ === 'number') {
        udpHandler.sendControlCommandToRobot(
            RD_TARGET_CLIENT_ID, 
            command.linearX, 
            command.linearY, 
            command.angularZ
        );
    } else {
        console.warn("CE_Main: Invalid control command received via IPC:", command);
    }
});