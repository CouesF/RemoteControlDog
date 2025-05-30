const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const dgram = require('dgram');
const { v4: uuidv4 } = require('uuid');
require('dotenv').config({ path: path.join(__dirname, '..', '.env') });

const protobuf = require('protobufjs'); // Use the protobufjs library
let pbRoot; // This will store the loaded protobuf root object

// Configuration from .env
const CE_CLIENT_ID = process.env.CE_CLIENT_ID || "controller_main";
const RD_CLIENT_ID = process.env.RD_CLIENT_ID || "robot_dog_alpha"; // Not directly used for sending from main.js
const CS_HOST = process.env.TARGET_CS_HOST || "127.0.0.1";
const CS_PORT = parseInt(process.env.TARGET_CS_PORT || "9000", 10);
const CE_LISTEN_PORT = parseInt(process.env.CE_LISTEN_PORT || "0", 10);

let mainWindow;
const udpClient = dgram.createSocket('udp4');

// --- Protobuf Message Types (will be populated after loading .proto) ---
let Header, UdpPacketWrapper, RegisterClientRequest, RobotStatusUpdate, VideoStreamPacket, ClientTypeEnum, RegisterClientResponse; // Added Enum suffix for clarity

async function loadProtobufDefinitions() {
  try {
    pbRoot = await protobuf.load(path.join(__dirname, 'messages.proto')); // Load .proto file
    console.log("CE: Protobuf definitions loaded successfully.");

    // Lookup specific message and enum types from the loaded root
    Header = pbRoot.lookupType("dog_system.v1.Header");
    UdpPacketWrapper = pbRoot.lookupType("dog_system.v1.UdpPacketWrapper");
    RegisterClientRequest = pbRoot.lookupType("dog_system.v1.RegisterClientRequest");
    RobotStatusUpdate = pbRoot.lookupType("dog_system.v1.RobotStatusUpdate");
    VideoStreamPacket = pbRoot.lookupType("dog_system.v1.VideoStreamPacket");
    ClientTypeEnum = pbRoot.lookupEnum("dog_system.v1.ClientType").values; // Get enum values object
    RegisterClientResponse = pbRoot.lookupType("dog_system.v1.RegisterClientResponse");


    if (!Header || !UdpPacketWrapper || !RegisterClientRequest || !RobotStatusUpdate || !VideoStreamPacket || !ClientTypeEnum || !RegisterClientResponse) {
        throw new Error("One or more protobuf types failed to load. Check your .proto file and type names.");
    }

  } catch (err) {
    console.error("CE: Fatal - Failed to load protobuf definitions:", err);
    app.quit(); // Important to quit if protos can't be loaded
  }
}

function getFormattedTimestampMs() {
    return Date.now();
}

// Renamed to avoid conflict with the 'Header' type variable
function createHeaderMessageInstance(sourceId, targetId) {
    const payload = { // This is a plain JavaScript object
        message_id: uuidv4(),
        timestamp_utc_ms: getFormattedTimestampMs(),
        source_id: sourceId,
        target_id: targetId
    };
    // Optional: Verify the payload if necessary, though create usually handles this
    // const errMsg = Header.verify(payload);
    // if (errMsg) throw Error(errMsg);
    return Header.create(payload); // Creates a message instance
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
    // mainWindow.webContents.openDevTools();
}

// Make the whenReady handler async to await protobuf loading
app.whenReady().then(async () => {
    await loadProtobufDefinitions(); // Load protobufs first
    if (!pbRoot) { // If loading failed, pbRoot would be undefined
        console.error("CE: Application cannot start because protobuf definitions failed to load.");
        return; // Exit if protos are not loaded
    }

    createWindow();

    udpClient.on('error', (err) => {
        console.error(`CE: UDP client error:\n${err.stack}`);
        udpClient.close();
    });

    udpClient.on('message', (msg, rinfo) => {
        try {
            const wrapper = UdpPacketWrapper.decode(msg); // Decode the outer wrapper

            if (wrapper.actual_message_type === "dog_system.v1.RobotStatusUpdate") {
                const statusUpdate = RobotStatusUpdate.decode(wrapper.actual_message_data);
                if (mainWindow) {
                    // Convert to plain JS object for IPC. This is safer.
                    mainWindow.webContents.send('robot-status', RobotStatusUpdate.toObject(statusUpdate, {
                        longs: String, // Convert Long.js instances to strings
                        enums: String, // Convert enums to their string names
                        bytes: String  // Convert bytes to base64 strings (default for toObject)
                    }));
                }
            } else if (wrapper.actual_message_type === "dog_system.v1.VideoStreamPacket") {
                const videoPacket = VideoStreamPacket.decode(wrapper.actual_message_data);
                if (mainWindow && videoPacket.frame_data && videoPacket.frame_data.length > 0) {
                    const base64Frame = Buffer.from(videoPacket.frame_data).toString('base64');
                    mainWindow.webContents.send('video-stream', `data:image/jpeg;base64,${base64Frame}`);
                }
            } else if (wrapper.actual_message_type === "dog_system.v1.RegisterClientResponse") {
                const regResponse = RegisterClientResponse.decode(wrapper.actual_message_data);
                const regResponseObj = RegisterClientResponse.toObject(regResponse); // Convert to plain object
                console.log(`CE: Received RegisterClientResponse: Success=${regResponseObj.success}, Msg=${regResponseObj.message}`);
            }

        } catch (e) {
            console.error('CE: Failed to decode incoming message:', e);
            console.error('CE: Offending message buffer (first 100 bytes):', msg.slice(0, 100).toString('hex'));
        }
    });

    udpClient.bind(CE_LISTEN_PORT, () => {
        const address = udpClient.address();
        console.log(`CE: Controller End '${CE_CLIENT_ID}' listening on ${address.address}:${address.port}. Connecting to CS at ${CS_HOST}:${CS_PORT}`);
        
        // Create RegisterClientRequest message
        const regRequestPayload = {
            header: createHeaderMessageInstance(CE_CLIENT_ID, "server"), // Use the function to create header instance
            client_type: ClientTypeEnum.CONTROLLER_END, // Use the loaded enum value
            client_id: CE_CLIENT_ID,
            client_version: "0.1.0"
        };
        const regRequestMessage = RegisterClientRequest.create(regRequestPayload);
        const regRequestBuffer = RegisterClientRequest.encode(regRequestMessage).finish(); // Serialize

        // Create UdpPacketWrapper message
        const wrapperRegPayload = {
            header: createHeaderMessageInstance(CE_CLIENT_ID, "server"),
            target_client_id_for_relay: "server",
            actual_message_type: "dog_system.v1.RegisterClientRequest",
            actual_message_data: regRequestBuffer
        };
        const wrapperRegMessage = UdpPacketWrapper.create(wrapperRegPayload);
        const bufferToSend = UdpPacketWrapper.encode(wrapperRegMessage).finish(); // Serialize
        
        udpClient.send(bufferToSend, CS_PORT, CS_HOST, (err) => {
            if (err) {
                console.error('CE: Failed to send registration message:', err);
            } else {
                console.log('CE: Sent RegisterClientRequest to CS');
            }
        });
    });

    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) {
            if (pbRoot) createWindow(); // Only create window if protos are loaded
        }
    });
});

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') {
        app.quit();
    }
    udpClient.close();
});