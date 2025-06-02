// control_end_electron/src/main/udp_handler.js
const dgram = require('dgram');
const protobufHandler = require('./protobuf_handler'); // Assuming it's in the same directory

let udpClient;
let mainWindowRef; // To send data to renderer process
let CE_CLIENT_ID_REF;
let CS_HOST_REF;
let CS_PORT_REF;

function initUdpClient(ceClientId, csHost, csPort, ceListenPort, mainWindow) {
    CE_CLIENT_ID_REF = ceClientId;
    CS_HOST_REF = csHost;
    CS_PORT_REF = csPort;
    mainWindowRef = mainWindow;

    udpClient = dgram.createSocket('udp4');

    udpClient.on('error', (err) => {
        console.error(`CE_UDP: UDP client error:\n${err.stack}`);
        if (udpClient) udpClient.close();
    });

    udpClient.on('message', (msg, rinfo) => {
        console.log(`CE_UDP: Received ${msg.length} bytes from ${rinfo.address}:${rinfo.port}`);
        try {
            const wrapper = protobufHandler.decodeUdpPacketWrapper(msg);
            // console.log(`CE_UDP: Decoded Wrapper: type='${wrapper.actualMessageType}', src='${wrapper.header.sourceId}', relay_target='${wrapper.targetClientIdForRelay}'`);

            const actualMessage = protobufHandler.decodeActualMessage(wrapper);
            if (!actualMessage) {
                console.warn(`CE_UDP: Could not decode actual message from type: ${wrapper.actualMessageType}`);
                return;
            }
            
            // Handle based on actual message type
            if (wrapper.actualMessageType === "dog_system.v1.RobotStatusUpdate") {
                if (mainWindowRef && mainWindowRef.webContents && !mainWindowRef.isDestroyed()) {
                    // console.log("CE_UDP: Sending 'robot-status' to renderer. Data:", JSON.stringify(actualMessage).substring(0, 200) + "...");
                    mainWindowRef.webContents.send('robot-status', actualMessage);
                }
            } else if (wrapper.actualMessageType === "dog_system.v1.VideoStreamPacket") {
                if (mainWindowRef && mainWindowRef.webContents && !mainWindowRef.isDestroyed() && actualMessage.frameData && actualMessage.frameData.length > 0) {
                    // frameData from toObject with bytes: String might be base64. If it's a Buffer, convert.
                    // Assuming actualMessage.frameData is already base64 string due to toObject options
                    const base64Frame = actualMessage.frameData; // If it's raw bytes, use Buffer.from(actualMessage.frameData).toString('base64');
                    mainWindowRef.webContents.send('video-stream', `data:image/jpeg;base64,${base64Frame}`);
                }
            } else if (wrapper.actualMessageType === "dog_system.v1.RegisterClientResponse") {
                console.log(`CE_UDP: Received RegisterClientResponse: Success=${actualMessage.success}, Msg='${actualMessage.message}'`);
                // Potentially update UI or state based on registration success
            } else {
                console.log(`CE_UDP: Received unhandled message type: ${wrapper.actualMessageType}`);
            }

        } catch (e) {
            console.error('CE_UDP: Failed to decode or process incoming message:', e);
            console.error('CE_UDP: Offending message buffer (first 100 bytes hex):', msg.slice(0, 100).toString('hex'));
        }
    });

    udpClient.bind(ceListenPort, () => {
        const address = udpClient.address();
        console.log(`CE_UDP: Controller End '${CE_CLIENT_ID_REF}' listening on ${address.address}:${address.port}.`);
        console.log(`CE_UDP: Will connect to CS at ${CS_HOST_REF}:${CS_PORT_REF}`);
        
        // Send initial registration message
        registerWithServer();
    });
}

function registerWithServer() {
    if (!udpClient || !CE_CLIENT_ID_REF || !CS_HOST_REF || !CS_PORT_REF) {
        console.error("CE_UDP: Cannot register, UDP client or config not initialized.");
        return;
    }
    try {
        const regRequestInstance = protobufHandler.createRegisterClientRequest(CE_CLIENT_ID_REF, "0.2.0");
        const bufferToSend = protobufHandler.wrapForServer(
            regRequestInstance,
            "dog_system.v1.RegisterClientRequest",
            CE_CLIENT_ID_REF,
            "server" // Registration message is for the server itself
        );

        udpClient.send(bufferToSend, CS_PORT_REF, CS_HOST_REF, (err) => {
            if (err) {
                console.error('CE_UDP: Failed to send registration message:', err);
            } else {
                console.log('CE_UDP: Sent RegisterClientRequest to CS');
            }
        });
    } catch (e) {
        console.error('CE_UDP: Error preparing or sending registration message:', e);
    }
}

function sendControlCommandToRobot(robotClientId, linearX, linearY, angularZ) {
    if (!udpClient || !CE_CLIENT_ID_REF || !CS_HOST_REF || !CS_PORT_REF) {
        console.error("CE_UDP: Cannot send control command, UDP client or config not initialized.");
        return;
    }
    try {
        const controlCommandInstance = protobufHandler.createControlCommand(linearX, linearY, angularZ, CE_CLIENT_ID_REF, robotClientId);
        const bufferToSend = protobufHandler.wrapForServer(
            controlCommandInstance,
            "dog_system.v1.ControlCommand", // Make sure this type is defined in proto and handler
            CE_CLIENT_ID_REF,         // Source of the wrapper
            robotClientId             // Final destination for relay
        );

        udpClient.send(bufferToSend, CS_PORT_REF, CS_HOST_REF, (err) => {
            if (err) {
                console.error(`CE_UDP: Failed to send ControlCommand to ${robotClientId}:`, err);
            } else {
                console.log(`CE_UDP: Sent ControlCommand to ${robotClientId} via CS`);
            }
        });
    } catch (e) {
        console.error('CE_UDP: Error preparing or sending ControlCommand:', e);
    }
}


function closeUdpClient() {
    if (udpClient) {
        udpClient.close();
        udpClient = null;
        console.log("CE_UDP: UDP client closed.");
    }
}

module.exports = {
    initUdpClient,
    registerWithServer, // Could be called on a timer for re-registration if needed
    sendControlCommandToRobot,
    closeUdpClient
};