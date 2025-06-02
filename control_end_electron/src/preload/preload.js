// control_end_electron/src/preload/preload.js
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
    // From Main to Renderer
    onRobotStatus: (callback) => ipcRenderer.on('robot-status', (_event, value) => callback(value)),
    onVideoStream: (callback) => ipcRenderer.on('video-stream', (_event, value) => callback(value)),
    
    // From Renderer to Main
    sendControlCommand: (command) => ipcRenderer.send('send-control-command', command),
    sendSystemCommand: (command) => ipcRenderer.send('send-system-command', command), // ADDED
    sendPostureCommand: (command) => ipcRenderer.send('send-posture-command', command), // ADDED

    // Remove listeners if component unmounts to prevent memory leaks
    removeRobotStatusListener: (callback) => ipcRenderer.removeListener('robot-status', callback),
    removeVideoStreamListener: (callback) => ipcRenderer.removeListener('video-stream', callback),
});
console.log("CE_Preload: electronAPI exposed to renderer.");