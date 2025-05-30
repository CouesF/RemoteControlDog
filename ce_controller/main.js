const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const dgram = require('dgram');
const { v4: uuidv4 } = require('uuid');
require('dotenv').config({ path: path.join(__dirname, '..', '.env') }); // Added


// Load compiled protobufjs module (messages_pb.js)
// Ensure messages_pb.js is in the same directory or provide correct path
const pb = require('./messages_pb'); // Loads the generated messages_pb.js

// Configuration
const CE_CLIENT_ID = "controller_main";
const RD_CLIENT_ID = "robot_dog_alpha"; // Expected source for data
const CS_HOST = process.env.TARGET_CS_HOST || "127.0.0.1";       // Changed
const CS_PORT = parseInt(process.env.TARGET_CS_PORT || "9000", 10); // Changed and parsed
const CE_LISTEN_PORT = parseInt(process.env.CE_LISTEN_PORT || "0", 10); // Changed 

let mainWindow;
const udpClient = dgram.createSocket('udp4');

function getFormattedTimestampMs() {
    return Date.now();
}

function createHeader(sourceId, targetId) {
    const header = new pb.dog_system.v1.Header(); // Use fully qualified name
    header.message_id = uuidv4();
    header.timestamp_utc_ms = getFormattedTimestampMs();
    header.source_id = sourceId;
    header.target_id = targetId;
    return header;
}

function createWindow() {
    mainWindow = new BrowserWindow({
        width: 1000,
        height: 800,
        webPreferences: {
            preload: path.join(__dirname, 'preload.js'),
            contextIsolation: true,
            nodeIntegration: false
        }
    });

    mainWindow.loadFile('index.html');
    // mainWindow.webContents.openDevTools(); // Optional: for debugging
}

app.whenReady().then(() => {
    createWindow();

    udpClient.on('error', (err) => {
        console.error(`CE: UDP client error:\n${err.stack}`);
        udpClient.close();
    });

    udpClient.on('message', (msg, rinfo) => {
        // console.log(`CE: Received ${msg.length} bytes from ${rinfo.address}:${rinfo.port}`);
        try {
            const wrapper = pb.dog_system.v1.UdpPacketWrapper.decode(msg);
            // console.log("CE: Decoded UdpPacketWrapper, actual_message_type:", wrapper.actual_message_type);

            if (wrapper.actual_message_type === "dog_system.v1.RobotStatusUpdate") {
                const statusUpdate = pb.dog_system.v1.RobotStatusUpdate.decode(wrapper.actual_message_data);
                // console.log("CE: Decoded RobotStatusUpdate:", statusUpdate.battery_percent);
                if (mainWindow) {
                    mainWindow.webContents.send('robot-status', JSON.parse(JSON.stringify(statusUpdate)));
                }
            } else if (wrapper.actual_message_type === "dog_system.v1.VideoStreamPacket") {
                const videoPacket = pb.dog_system.v1.VideoStreamPacket.decode(wrapper.actual_message_data);
                // console.log("CE: Decoded VideoStreamPacket, frame_id:", videoPacket.frame_id);
                if (mainWindow && videoPacket.frame_data && videoPacket.frame_data.length > 0) {
                     // Convert Uint8Array to base64 string for display in <img>
                    const base64Frame = Buffer.from(videoPacket.frame_data).toString('base64');
                    mainWindow.webContents.send('video-stream', `data:image/jpeg;base64,${base64Frame}`);
                }
            } else if (wrapper.actual_message_type === "dog_system.v1.RegisterClientResponse") {
                const regResponse = pb.dog_system.v1.RegisterClientResponse.decode(wrapper.actual_message_data);
                console.log(`CE: Received RegisterClientResponse: Success=${regResponse.success}, Msg=${regResponse.message}`);
            }

        } catch (e) {
            console.error('CE: Failed to decode incoming message:', e);
        }
    });

    udpClient.bind(CE_LISTEN_PORT, () => {
        const address = udpClient.address();
        console.log(`CE: Controller End '${CE_CLIENT_ID}' listening on ${address.address}:${address.port}`);
        
        // Register with Cloud Server
        const regRequest = new pb.dog_system.v1.RegisterClientRequest();
        regRequest.header = createHeader(CE_CLIENT_ID, "server");
        regRequest.client_type = pb.dog_system.v1.ClientType.CONTROLLER_END;
        regRequest.client_id = CE_CLIENT_ID;
        regRequest.client_version = "0.1.0";

        const wrapperReg = new pb.dog_system.v1.UdpPacketWrapper();
        wrapperReg.header = createHeader(CE_CLIENT_ID, "server");
        wrapperReg.target_client_id_for_relay = "server"; // For the server itself
        wrapperReg.actual_message_type = "dog_system.v1.RegisterClientRequest";
        wrapperReg.actual_message_data = pb.dog_system.v1.RegisterClientRequest.encode(regRequest).finish();
        
        const buffer = pb.dog_system.v1.UdpPacketWrapper.encode(wrapperReg).finish();
        udpClient.send(buffer, CS_PORT, CS_HOST, (err) => {
            if (err) {
                console.error('CE: Failed to send registration message:', err);
            } else {
                console.log('CE: Sent RegisterClientRequest to CS');
            }
        });
    });

    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) createWindow();
    });
});

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') {
        app.quit();
    }
    udpClient.close();
});