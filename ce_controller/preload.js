const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('api', {
    receive: (channel, func) => {
        const validChannels = ['robot-status', 'video-stream'];
        if (validChannels.includes(channel)) {
            // Deliberately strip event as it includes `sender`
            ipcRenderer.on(channel, (event, ...args) => func(...args));
        }
    },
    // Example for sending data from renderer to main, not used in this basic setup yet
    // send: (channel, data) => {
    //     const validChannels = ['some-command-to-main'];
    //     if (validChannels.includes(channel)) {
    //         ipcRenderer.send(channel, data);
    //     }
    // }
});