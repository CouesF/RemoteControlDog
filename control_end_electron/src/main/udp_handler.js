// control_end_electron/src/main/udp_handler.js
const dgram = require('dgram');
const protobufHandler = require('./protobuf_handler');

let udpClient;
let mainWindowRef;
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
        // console.log(`CE_UDP: Received ${msg.length} bytes from ${rinfo.address}:${rinfo.port}`);
        try {
            const wrapper = protobufHandler.decodeUdpPacketWrapper(msg);
            const actualMessage = protobufHandler.decodeActualMessage(wrapper);
            if (!actualMessage) {
                console.warn(`CE_UDP: Could not decode actual message from type: ${wrapper.actualMessageType}`);
                return;
            }
            
            if (wrapper.actualMessageType === "dog_system.v1.RobotStatusUpdate") {
                if (mainWindowRef && mainWindowRef.webContents && !mainWindowRef.isDestroyed()) {
                    mainWindowRef.webContents.send('robot-status', actualMessage);
                }
            } else if (wrapper.actualMessageType === "dog_system.v1.VideoStreamPacket") {
                if (mainWindowRef && mainWindowRef.webContents && !mainWindowRef.isDestroyed() && actualMessage.frameData && actualMessage.frameData.length > 0) {
                    const base64Frame = actualMessage.frameData; 
                    mainWindowRef.webContents.send('video-stream', `data:image/jpeg;base64,${base64Frame}`);
                }
            } else if (wrapper.actualMessageType === "dog_system.v1.RegisterClientResponse") {
                console.log(`CE_UDP: Received RegisterClientResponse: Success=${actualMessage.success}, Msg='${actualMessage.message}'`);
            } else {
                // console.log(`CE_UDP: Received unhandled message type: ${wrapper.actualMessageType}`);
            }

        } catch (e) {
            console.error('CE_UDP: Failed to decode or process incoming message:', e);
        }
    });

    udpClient.bind(ceListenPort, () => {
        const address = udpClient.address();
        console.log(`CE_UDP: Controller End '${CE_CLIENT_ID_REF}' listening on ${address.address}:${address.port}.`);
        console.log(`CE_UDP: Will connect to CS at ${CS_HOST_REF}:${CS_PORT_REF}`);
        registerWithServer();
    });
}

function registerWithServer() {
    // ... (implementation as before)
    if (!udpClient || !CE_CLIENT_ID_REF || !CS_HOST_REF || !CS_PORT_REF) {
        console.error("CE_UDP: Cannot register, UDP client or config not initialized.");
        return;
    }
    try {
        const regRequestInstance = protobufHandler.createRegisterClientRequest(CE_CLIENT_ID_REF, "0.2.0"); // Version updated to 0.2.0 to match robot
        const bufferToSend = protobufHandler.wrapForServer(
            regRequestInstance,
            "dog_system.v1.RegisterClientRequest",
            CE_CLIENT_ID_REF,
            "server" 
        );
        udpClient.send(bufferToSend, CS_PORT_REF, CS_HOST_REF, (err) => { /* ... */ });
    } catch (e) { /* ... */ }
}

function sendControlCommandToRobot(robotClientId, linearX, linearY, angularZ) {
    // ... (implementation as before)
    if (!udpClient || !CE_CLIENT_ID_REF || !CS_HOST_REF || !CS_PORT_REF) {
        console.error("CE_UDP: Cannot send control command, UDP client or config not initialized.");
        return;
    }
    try {
        const controlCommandInstance = protobufHandler.createControlCommand(linearX, linearY, angularZ, CE_CLIENT_ID_REF, robotClientId);
        const bufferToSend = protobufHandler.wrapForServer(
            controlCommandInstance,
            "dog_system.v1.ControlCommand", 
            CE_CLIENT_ID_REF,
            robotClientId
        );
        udpClient.send(bufferToSend, CS_PORT_REF, CS_HOST_REF, (err) => {
            if (err) {
                console.error(`CE_UDP: Failed to send ControlCommand to ${robotClientId}:`, err);
            } else {
                // console.log(`CE_UDP: Sent ControlCommand to ${robotClientId} via CS`);
            }
        });
    } catch (e) {
        console.error('CE_UDP: Error preparing or sending ControlCommand:', e);
    }
}

// ADDED: Function to send SystemActionCommand
function sendSystemActionCommandToRobot(robotClientId, actionTypeString) {
    if (!udpClient || !CE_CLIENT_ID_REF || !CS_HOST_REF || !CS_PORT_REF) {
        console.error("CE_UDP: Cannot send system action command, UDP client or config not initialized.");
        return;
    }
    try {
        const commandInstance = protobufHandler.createSystemActionCommand(actionTypeString, CE_CLIENT_ID_REF, robotClientId);
        const bufferToSend = protobufHandler.wrapForServer(
            commandInstance,
            "dog_system.v1.SystemActionCommand",
            CE_CLIENT_ID_REF,
            robotClientId
        );

        udpClient.send(bufferToSend, CS_PORT_REF, CS_HOST_REF, (err) => {
            if (err) {
                console.error(`CE_UDP: Failed to send SystemActionCommand (${actionTypeString}) to ${robotClientId}:`, err);
            } else {
                console.log(`CE_UDP: Sent SystemActionCommand (${actionTypeString}) to ${robotClientId} via CS`);
            }
        });
    } catch (e) {
        console.error(`CE_UDP: Error preparing or sending SystemActionCommand ('${actionTypeString}'):`, e);
    }
}

// ADDED: Function to send SetPostureCommand
function sendSetPostureCommandToRobot(robotClientId, postureTypeString) {
    if (!udpClient || !CE_CLIENT_ID_REF || !CS_HOST_REF || !CS_PORT_REF) {
        console.error("CE_UDP: Cannot send set posture command, UDP client or config not initialized.");
        return;
    }
    try {
        const commandInstance = protobufHandler.createSetPostureCommand(postureTypeString, CE_CLIENT_ID_REF, robotClientId);
        const bufferToSend = protobufHandler.wrapForServer(
            commandInstance,
            "dog_system.v1.SetPostureCommand",
            CE_CLIENT_ID_REF,
            robotClientId
        );

        udpClient.send(bufferToSend, CS_PORT_REF, CS_HOST_REF, (err) => {
            if (err) {
                console.error(`CE_UDP: Failed to send SetPostureCommand (${postureTypeString}) to ${robotClientId}:`, err);
            } else {
                console.log(`CE_UDP: Sent SetPostureCommand (${postureTypeString}) to ${robotClientId} via CS`);
            }
        });
    } catch (e) {
        console.error(`CE_UDP: Error preparing or sending SetPostureCommand ('${postureTypeString}'):`, e);
    }
}

function closeUdpClient() {
    // ... (implementation as before)
    if (udpClient) {
        udpClient.close();
        udpClient = null;
        console.log("CE_UDP: UDP client closed.");
    }
}

module.exports = {
    initUdpClient,
    registerWithServer,
    sendControlCommandToRobot,
    sendSystemActionCommandToRobot, // ADDED
    sendSetPostureCommandToRobot,   // ADDED
    closeUdpClient
};