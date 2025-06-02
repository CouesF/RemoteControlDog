// control_end_electron/src/main/protobuf_handler.js
const protobuf = require('protobufjs');
const path = require('path');
const { v4: uuidv4 } = require('uuid');

let pbRoot = null;
let messageTypes = {}; // Stores resolved Type objects for messages, or Enum value objects for enums

const protoFilePath = path.join(__dirname, '..', '..', '..', 'messages.proto');

async function loadProtoDefinitions() {
    if (pbRoot) return;

    try {
        pbRoot = await protobuf.load(protoFilePath);
        console.log("CE_ProtoHandler: Protobuf definitions loaded successfully from:", protoFilePath);

        // For debugging, you can inspect the loaded structure:
        // console.log("Loaded Protobuf Root JSON:", JSON.stringify(pbRoot.toJSON(), null, 2));
        // if (pbRoot.nested && pbRoot.nested.dog_system && pbRoot.nested.dog_system.nested && pbRoot.nested.dog_system.nested.v1) {
        //     console.log("Found package dog_system.v1. Nested object keys:", Object.keys(pbRoot.nested.dog_system.nested.v1.nested));
        // } else {
        //     console.warn("CE_ProtoHandler: Package dog_system.v1 not found as expected in pbRoot.nested structure.");
        // }

        const typesToLoad = [
            "Header", "Vector3", "Quaternion", "Pose",
            "ClientType", "NavigationState", "PromptActionType", "HeadMovementTargetDirection",
            "HeadMovementIntensity", "PointingLimb", "ChildResponseType", "FeedbackActionType",
            "RobotAnimationId", "PersonalizedContentType", "SystemEventSeverity",
            "UdpPacketWrapper", "RegisterClientRequest", "RegisterClientResponse",
            "NavigateToPointCommand", "HumanDetectionDetails", "RjaObjectDetectionDetails",
            "ActiveActionStatus", "RobotStatusUpdate",
            "HeadMovementParams", "PointingGestureParams", "PlaySoundCueParams", "DisplayVisualCueParams",
            "PromptAction", "RjaPromptCommand",
            "RjaChildResponseRecord",
            "RobotAnimationParams", "PlayFeedbackSoundParams", "DisplayFeedbackVisualParams",
            "EngagePersonalizedContentParams", "FeedbackAction", "RjaFeedbackCommand",
            "ChildProfile", "SetCurrentChildProfileCommand", "RjaPointDefinition", "DefineRjaPointsCommand",
            "VideoStreamPacket", "RobotSystemEvent", "CommandAcknowledgement", "SystemActionCommand",
            "ControlCommand" // Ensure this is in your .proto file
        ];

        typesToLoad.forEach(typeName => {
            const fullName = `dog_system.v1.${typeName}`;
            let resolved = false;

            // Try to load as a Message Type
            try {
                const messageItem = pbRoot.lookupType(fullName);
                if (messageItem) { // lookupType throws on not found or wrong type, so this check is often redundant if no error
                    messageTypes[typeName] = messageItem;
                    resolved = true;
                    // console.log(`CE_ProtoHandler: Loaded Message: ${fullName}`);
                }
            } catch (e_type) {
                // This error means it's not a Message type (or truly not found by lookupType).
                // Now, try to load as an Enum Type.
                try {
                    const enumItem = pbRoot.lookupEnum(fullName);
                    if (enumItem) { // lookupEnum also throws on not found
                        messageTypes[typeName] = enumItem.values; // Store the enum's {name: value} map
                        resolved = true;
                        // console.log(`CE_ProtoHandler: Loaded Enum: ${fullName}`);
                    }
                } catch (e_enum) {
                    // Failed to resolve as both Message Type and Enum Type
                    console.error(`CE_ProtoHandler: Could not resolve '${typeName}' (as ${fullName}). \n  Not a Message (Error: ${e_type.message}). \n  Not an Enum (Error: ${e_enum.message}).`);
                }
            }

            if (!resolved) {
                // This log might be redundant if the detailed error above already printed,
                // but can serve as a summary that a type wasn't loaded.
                // console.warn(`CE_ProtoHandler: '${typeName}' was not successfully loaded.`);
            }
        });

        // Verification checks
        if (!messageTypes.UdpPacketWrapper || !messageTypes.RegisterClientRequest) {
            throw new Error("CE_ProtoHandler: Essential protobuf message types (UdpPacketWrapper, RegisterClientRequest) failed to load.");
        }
        if (!messageTypes.ClientType || typeof messageTypes.ClientType.ROBOT_DOG === 'undefined') {
            // Check if ClientType exists and has expected enum values
            console.error("CE_ProtoHandler: Problem with ClientType. Current value:", messageTypes.ClientType);
            throw new Error("CE_ProtoHandler: Essential enum ClientType failed to load correctly.");
        }
        if (!messageTypes.ControlCommand) {
            console.warn("CE_ProtoHandler: WARNING - ControlCommand message type not loaded. Check .proto definition and logs for errors specific to ControlCommand.");
            // Depending on its necessity, you might throw an error here too.
        }

        console.log("CE_ProtoHandler: All specified message types and enums processed. Check logs for any individual load failures.");

    } catch (err) {
        // This catches errors from protobuf.load itself or from the verification checks
        console.error("CE_ProtoHandler: FATAL - Failed to load protobuf definitions:", err);
        throw err;
    }
}

function getFormattedTimestampMs() {
    return Date.now();
}

// createHeader remains robust as protobufjs handles snake_case to camelCase
function createHeader(sourceId, targetId, sessionId = null, trialId = null) {
    if (!messageTypes.Header) throw new Error("Header type not loaded");
    const payload = {
        messageId: uuidv4(), // proto: message_id
        timestampUtcMs: getFormattedTimestampMs(), // proto: timestamp_utc_ms
        sourceId: sourceId, // proto: source_id
        targetId: targetId, // proto: target_id
    };
    if (sessionId) payload.sessionId = sessionId; // proto: session_id
    if (trialId) payload.trialId = trialId; // proto: trial_id
    
    const headerMessage = messageTypes.Header.create(payload);
    // Verify (optional, for debugging)
    // const errMsg = messageTypes.Header.verify(payload);
    // if (errMsg) throw Error(errMsg);
    return headerMessage;
}

// --- Message Creation Functions ---

function createRegisterClientRequest(clientId, clientVersion) {
    if (!messageTypes.RegisterClientRequest || !messageTypes.Header || !messageTypes.ClientType) {
        throw new Error("Required types for RegisterClientRequest not loaded");
    }
    const header = createHeader(clientId, "server"); 
    const payload = {
        header: header,
        clientType: messageTypes.ClientType.CONTROLLER_END, // Uses the numeric value from the loaded enum values
        clientId: clientId,
        clientVersion: clientVersion,
        capabilities: ["video_H264", "audio_opus"] // Example capabilities
    };
    return messageTypes.RegisterClientRequest.create(payload);
}

function createControlCommand(linearX, linearY, angularZ, sourceId, targetId) {
    if (!messageTypes.ControlCommand || !messageTypes.Header) {
        throw new Error("Required types for ControlCommand not loaded");
    }
    const header = createHeader(sourceId, targetId);
    const payload = {
        header: header,
        linearVelocityX: linearX,
        linearVelocityY: linearY,
        angularVelocityZ: angularZ,
    };
    return messageTypes.ControlCommand.create(payload);
}


// --- Wrapper Creation ---
function wrapForServer(innerMessageInstance, innerMessageTypeString, sourceClientId, relayTargetClientId) {
    if (!messageTypes.UdpPacketWrapper || !messageTypes.Header) {
        throw new Error("UdpPacketWrapper or Header type not loaded");
    }
    // Get the simple name for lookup in messageTypes, e.g. "RegisterClientRequest"
    const simpleTypeName = innerMessageTypeString.split('.').pop(); 
    const InnerMessageType = messageTypes[simpleTypeName]; 
    
    if (!InnerMessageType) throw new Error(`Inner message type '${simpleTypeName}' (from '${innerMessageTypeString}') not loaded or not a message type.`);
    // Check if InnerMessageType is actually a Type constructor and not an enum values object
    if (typeof InnerMessageType.encode !== 'function') {
        throw new Error(`'${simpleTypeName}' resolved to an enum, not a message type. Cannot encode.`);
    }


    const innerMessageBuffer = InnerMessageType.encode(innerMessageInstance).finish();

    const wrapperHeader = createHeader(sourceClientId, "server"); 
    const wrapperPayload = {
        header: wrapperHeader,
        targetClientIdForRelay: relayTargetClientId,
        actualMessageType: innerMessageTypeString, 
        actualMessageData: innerMessageBuffer
    };
    const wrapperInstance = messageTypes.UdpPacketWrapper.create(wrapperPayload);
    return messageTypes.UdpPacketWrapper.encode(wrapperInstance).finish();
}

// --- Message Parsing ---
function decodeUdpPacketWrapper(buffer) {
    if (!messageTypes.UdpPacketWrapper) throw new Error("UdpPacketWrapper type not loaded");
    return messageTypes.UdpPacketWrapper.decode(buffer);
}

function decodeActualMessage(wrapper) {
    if (!wrapper || !wrapper.actualMessageType || !wrapper.actualMessageData) {
        console.error("CE_ProtoHandler: Invalid wrapper for decoding actual message.");
        return null;
    }
    const simpleTypeName = wrapper.actualMessageType.split('.').pop();
    const ActualMessageType = messageTypes[simpleTypeName];

    if (!ActualMessageType) {
        console.warn(`CE_ProtoHandler: No decoder for message type '${wrapper.actualMessageType}'. Known types: ${Object.keys(messageTypes)}`);
        return null;
    }
    // Check if ActualMessageType is actually a Type constructor and not an enum values object
    if (typeof ActualMessageType.decode !== 'function') {
        console.warn(`CE_ProtoHandler: '${simpleTypeName}' (from '${wrapper.actualMessageType}') resolved to an enum. Cannot decode as message.`);
        return null;
    }

    try {
        const decodedMessage = ActualMessageType.decode(wrapper.actualMessageData);
        return ActualMessageType.toObject(decodedMessage, {
            longs: String,  
            enums: String,  
            bytes: String,  
            defaults: true, 
            arrays: true,   
            objects: true,  
            oneofs: true    
        });
    } catch (e) {
        console.error(`CE_ProtoHandler: Failed to decode actual message of type '${wrapper.actualMessageType}':`, e);
        return null;
    }
}



// Ensure wrapForServer and decodeActualMessage also correctly handle this:
// In wrapForServer:
// const InnerMessageType = messageTypes[simpleTypeName];
// if (!InnerMessageType || typeof InnerMessageType.encode !== 'function') { ... error ... }

// In decodeActualMessage:
// const ActualMessageType = messageTypes[simpleTypeName];
// if (!ActualMessageType || typeof ActualMessageType.decode !== 'function') { ... error ... }

module.exports = {
    loadProtoDefinitions,
    createRegisterClientRequest,
    createControlCommand,
    wrapForServer,
    decodeUdpPacketWrapper,
    decodeActualMessage,
    createHeader,
    getFormattedTimestampMs,
    // getMessageKeystore: () => messageTypes, // If you want to expose all loaded types/enums
};
