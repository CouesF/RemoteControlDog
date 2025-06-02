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
            "VideoStreamPacket", "RobotSystemEvent", "CommandAcknowledgement", 
            "SystemActionCommand", // Existing
            "ControlCommand",      // Existing
            "SetPostureCommand"    // ADDED
        ];

        typesToLoad.forEach(typeName => {
            const fullName = `dog_system.v1.${typeName}`;
            let resolved = false;
            try {
                const messageItem = pbRoot.lookupType(fullName);
                if (messageItem) {
                    messageTypes[typeName] = messageItem;
                    resolved = true;
                }
            } catch (e_type) {
                try {
                    const enumItem = pbRoot.lookupEnum(fullName);
                    if (enumItem) {
                        messageTypes[typeName] = enumItem.values; // Store {name: value} map
                        resolved = true;
                    }
                } catch (e_enum) {
                    console.error(`CE_ProtoHandler: Could not resolve '${typeName}' (as ${fullName}). \n  Not a Message (Error: ${e_type.message}). \n  Not an Enum (Error: ${e_enum.message}).`);
                }
            }
        });

        // Verification checks
        if (!messageTypes.UdpPacketWrapper || !messageTypes.RegisterClientRequest) {
            throw new Error("CE_ProtoHandler: Essential protobuf message types (UdpPacketWrapper, RegisterClientRequest) failed to load.");
        }
        if (!messageTypes.ClientType || typeof messageTypes.ClientType.ROBOT_DOG === 'undefined') {
            console.error("CE_ProtoHandler: Problem with ClientType. Current value:", messageTypes.ClientType);
            throw new Error("CE_ProtoHandler: Essential enum ClientType failed to load correctly.");
        }
        if (!messageTypes.ControlCommand) {
            console.warn("CE_ProtoHandler: WARNING - ControlCommand message type not loaded.");
        }
        // Check for SystemActionCommand and its nested enum ActionType
        const SystemActionCommandType = messageTypes.SystemActionCommand;
        if (!SystemActionCommandType || !SystemActionCommandType.get("action") || !SystemActionCommandType.get("action").resolvedType || !SystemActionCommandType.get("action").resolvedType.values) {
            console.warn("CE_ProtoHandler: WARNING - SystemActionCommand or its ActionType enum not loaded correctly.");
        } else {
            // console.log("CE_ProtoHandler: SystemActionCommand.ActionType enum values:", SystemActionCommandType.get("action").resolvedType.values);
        }
        // Check for SetPostureCommand and its nested enum PostureType
        const SetPostureCommandType = messageTypes.SetPostureCommand;
        if (!SetPostureCommandType || !SetPostureCommandType.get("posture") || !SetPostureCommandType.get("posture").resolvedType || !SetPostureCommandType.get("posture").resolvedType.values) {
            console.warn("CE_ProtoHandler: WARNING - SetPostureCommand or its PostureType enum not loaded correctly.");
        } else {
            // console.log("CE_ProtoHandler: SetPostureCommand.PostureType enum values:", SetPostureCommandType.get("posture").resolvedType.values);
        }


        console.log("CE_ProtoHandler: All specified message types and enums processed.");

    } catch (err) {
        console.error("CE_ProtoHandler: FATAL - Failed to load protobuf definitions:", err);
        throw err;
    }
}

function getFormattedTimestampMs() {
    return Date.now();
}

function createHeader(sourceId, targetId, sessionId = null, trialId = null) {
    if (!messageTypes.Header) throw new Error("Header type not loaded");
    const payload = {
        messageId: uuidv4(),
        timestampUtcMs: getFormattedTimestampMs(),
        sourceId: sourceId,
        targetId: targetId,
    };
    if (sessionId) payload.sessionId = sessionId;
    if (trialId) payload.trialId = trialId;
    return messageTypes.Header.create(payload);
}

function createRegisterClientRequest(clientId, clientVersion) {
    // ... (implementation as before)
    if (!messageTypes.RegisterClientRequest || !messageTypes.Header || !messageTypes.ClientType) {
        throw new Error("Required types for RegisterClientRequest not loaded");
    }
    const header = createHeader(clientId, "server"); 
    const payload = {
        header: header,
        clientType: messageTypes.ClientType.CONTROLLER_END,
        clientId: clientId,
        clientVersion: clientVersion,
        capabilities: ["video_H264", "audio_opus"]
    };
    return messageTypes.RegisterClientRequest.create(payload);
}

function createControlCommand(linearX, linearY, angularZ, sourceId, targetId) {
    // ... (implementation as before)
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

// ADDED: Function to create SystemActionCommand
function createSystemActionCommand(actionTypeString, sourceId, targetId) {
    const SystemActionCommandType = messageTypes.SystemActionCommand;
    if (!SystemActionCommandType || !messageTypes.Header) {
        throw new Error("Required types for SystemActionCommand (SystemActionCommandType or Header) not loaded");
    }
    const actionEnum = SystemActionCommandType.get("action").resolvedType; // This is the Enum object
    if (!actionEnum || typeof actionEnum.values[actionTypeString] === 'undefined') {
        throw new Error(`Invalid actionTypeString: '${actionTypeString}' for SystemActionCommand.ActionType. Available: ${Object.keys(actionEnum.values).join(', ')}`);
    }
    const header = createHeader(sourceId, targetId);
    const payload = {
        header: header,
        action: actionEnum.values[actionTypeString] // Use numeric enum value
    };
    return SystemActionCommandType.create(payload);
}

// ADDED: Function to create SetPostureCommand
function createSetPostureCommand(postureTypeString, sourceId, targetId) {
    const SetPostureCommandType = messageTypes.SetPostureCommand;
    if (!SetPostureCommandType || !messageTypes.Header) {
        throw new Error("Required types for SetPostureCommand (SetPostureCommandType or Header) not loaded");
    }
    const postureEnum = SetPostureCommandType.get("posture").resolvedType; // This is the Enum object
    if (!postureEnum || typeof postureEnum.values[postureTypeString] === 'undefined') {
        throw new Error(`Invalid postureTypeString: '${postureTypeString}' for SetPostureCommand.PostureType. Available: ${Object.keys(postureEnum.values).join(', ')}`);
    }
    const header = createHeader(sourceId, targetId);
    const payload = {
        header: header,
        posture: postureEnum.values[postureTypeString] // Use numeric enum value
    };
    return SetPostureCommandType.create(payload);
}

function wrapForServer(innerMessageInstance, innerMessageTypeString, sourceClientId, relayTargetClientId) {
    // ... (implementation as before)
    if (!messageTypes.UdpPacketWrapper || !messageTypes.Header) {
        throw new Error("UdpPacketWrapper or Header type not loaded");
    }
    const simpleTypeName = innerMessageTypeString.split('.').pop(); 
    const InnerMessageType = messageTypes[simpleTypeName]; 
    
    if (!InnerMessageType) throw new Error(`Inner message type '${simpleTypeName}' (from '${innerMessageTypeString}') not loaded or not a message type.`);
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

function decodeUdpPacketWrapper(buffer) {
    // ... (implementation as before)
    if (!messageTypes.UdpPacketWrapper) throw new Error("UdpPacketWrapper type not loaded");
    return messageTypes.UdpPacketWrapper.decode(buffer);
}

function decodeActualMessage(wrapper) {
    // ... (implementation as before)
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
    if (typeof ActualMessageType.decode !== 'function') {
        console.warn(`CE_ProtoHandler: '${simpleTypeName}' (from '${wrapper.actualMessageType}') resolved to an enum. Cannot decode as message.`);
        return null;
    }

    try {
        const decodedMessage = ActualMessageType.decode(wrapper.actualMessageData);
        return ActualMessageType.toObject(decodedMessage, {
            longs: String, enums: String, bytes: String, defaults: true, 
            arrays: true, objects: true, oneofs: true    
        });
    } catch (e) {
        console.error(`CE_ProtoHandler: Failed to decode actual message of type '${wrapper.actualMessageType}':`, e);
        return null;
    }
}

module.exports = {
    loadProtoDefinitions,
    createRegisterClientRequest,
    createControlCommand,
    createSystemActionCommand, // ADDED
    createSetPostureCommand,   // ADDED
    wrapForServer,
    decodeUdpPacketWrapper,
    decodeActualMessage,
    createHeader,
    getFormattedTimestampMs,
};