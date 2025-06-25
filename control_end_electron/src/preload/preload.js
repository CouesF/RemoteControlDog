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

    // UDP Connection Management for Camera
    initializeUDP: () => ipcRenderer.invoke('initialize-udp'),
    connectUDP: (connectionId, config) => ipcRenderer.invoke('connect-udp', connectionId, config),
    disconnectUDP: (connectionId) => ipcRenderer.invoke('disconnect-udp', connectionId),
    sendUDPMessage: (connectionId, message) => ipcRenderer.invoke('send-udp-message', connectionId, message),
    onUDPMessage: (callback) => ipcRenderer.on('udp-message', (_event, data) => callback(data)),
    onConnectionStatusChange: (callback) => ipcRenderer.on('connection-status-change', (_event, status) => callback(status)),

    // Remove listeners if component unmounts to prevent memory leaks
    removeRobotStatusListener: (callback) => ipcRenderer.removeListener('robot-status', callback),
    removeVideoStreamListener: (callback) => ipcRenderer.removeListener('video-stream', callback),
    removeUDPMessageListener: (callback) => ipcRenderer.removeListener('udp-message', callback),
    removeConnectionStatusListener: (callback) => ipcRenderer.removeListener('connection-status-change', callback),
});

// Mock API for frontend development
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

contextBridge.exposeInMainWorld('api', {
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
        // In a real app, you'd store this session in a sessions array.
        return Promise.resolve(newSession);
    },
    endSession: (sessionId) => {
        // In a real app, you'd find the session and update its status and end time.
        console.log(`Ending session ${sessionId}`);
        return Promise.resolve({ sessionId, status: 'ended', endTime: new Date().toISOString() });
    }
});
console.log("CE_Preload: electronAPI exposed to renderer.");
