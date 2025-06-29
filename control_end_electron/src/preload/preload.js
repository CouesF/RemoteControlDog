// control_end_electron/src/preload/preload.js
const { contextBridge, ipcRenderer } = require('electron');

// Mock API for frontend development (preserved from original file)
const mockData = {
    participants: [
        {
            participantId: 'uuid-p1',
            participantName: '张三',
            year: 5,
            month: 2,
            parentName: '张先生',
            parentPhone: '13800138001',
            diagnosticInfo: '发育迟缓',
            preferenceInfo: '喜欢蓝色和汽车',
        },
        {
            participantId: 'uuid-p2',
            participantName: '李四',
            year: 4,
            month: 8,
            parentName: '李女士',
            parentPhone: '13900139002',
            diagnosticInfo: '自闭症谱系障碍',
            preferenceInfo: '对声音敏感，喜欢安静',
        }
    ],
    maps: [
        {
            mapId: 'uuid-m1',
            mapName: '公园北区',
            mapDescription: '适合初级训练的开阔草地',
            targetCount: 6
        },
        {
            mapId: 'uuid-m2',
            mapName: '小区花园',
            mapDescription: '有更多互动元素的复杂环境',
            targetCount: 10
        }
    ]
};

// Expose a unified API to the renderer process
contextBridge.exposeInMainWorld('api', {
    // --- Camera Gateway API ---
    connectCameraGateway: () => ipcRenderer.invoke('camera-gateway-connect'),
    disconnectCameraGateway: () => ipcRenderer.send('camera-gateway-disconnect'),
    subscribeToCameras: (cameraIds) => ipcRenderer.send('camera-subscribe', cameraIds),
    unsubscribeFromCameras: (cameraIds) => ipcRenderer.send('camera-unsubscribe', cameraIds),
    requestCameraFrame: (cameraId) => ipcRenderer.send('request-camera-frame', cameraId),

    // --- Camera Event Listeners ---
    onCameraList: (callback) => ipcRenderer.on('camera-list', (event, ...args) => callback(...args)),
    onCameraFrame: (callback) => ipcRenderer.on('camera-frame', (event, ...args) => callback(...args)),
    onSubscriptionChange: (callback) => ipcRenderer.on('subscription-changed', (event, ...args) => callback(...args)),
    onCameraConnectionState: (callback) => ipcRenderer.on('camera-connection-state', (event, ...args) => callback(...args)),

    // --- Generic UDP API ---
    connectUDP: (options) => ipcRenderer.invoke('connect-udp', options),
    disconnectUDP: (connectionId) => ipcRenderer.send('disconnect-udp', connectionId),
    onUDPMessage: (connectionId, callback) => {
        const channel = `udp-message-${connectionId}`;
        ipcRenderer.on(channel, (event, ...args) => callback(...args));
        // Return a cleanup function to remove the listener
        return () => ipcRenderer.removeAllListeners(channel);
    },
    onUDPError: (connectionId, callback) => {
        const channel = `udp-error-${connectionId}`;
        ipcRenderer.on(channel, (event, ...args) => callback(...args));
        return () => ipcRenderer.removeAllListeners(channel);
    },
    onUDPConnect: (connectionId, callback) => {
        const channel = `udp-connect-${connectionId}`;
        ipcRenderer.on(channel, (event, ...args) => callback(...args));
        return () => ipcRenderer.removeAllListeners(channel);
    },
    onUDPDisconnect: (connectionId, callback) => {
        const channel = `udp-disconnect-${connectionId}`;
        ipcRenderer.on(channel, (event, ...args) => callback(...args));
        return () => ipcRenderer.removeAllListeners(channel);
    },

    // --- Mock Data API (Preserved) ---
    getParticipants: () => Promise.resolve(mockData.participants),
    createParticipant: (participant) => {
        const newParticipant = { ...participant, participantId: `uuid-p${mockData.participants.length + 1}` };
        mockData.participants.push(newParticipant);
        return Promise.resolve(newParticipant);
    },
    getMaps: () => Promise.resolve(mockData.maps),
    createMap: (map) => {
        const newMap = { ...map, mapId: `uuid-m${mockData.maps.length + 1}`, targetCount: 0 };
        mockData.maps.push(newMap);
        return Promise.resolve(newMap);
    },
    startSession: (participantId, mapId) => {
        const newSession = {
            sessionId: `session-${Date.now()}`,
            participantId,
            mapId,
            startTime: new Date().toISOString(),
            status: 'started',
        };
        return Promise.resolve(newSession);
    },
    endSession: (sessionId) => {
        console.log(`Ending session ${sessionId}`);
        return Promise.resolve({ sessionId, status: 'ended', endTime: new Date().toISOString() });
    }
});

console.log("CE_Preload: Unified API exposed to renderer.");
