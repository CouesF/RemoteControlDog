export const encodeClientType = {
  CLIENT_TYPE_UNSPECIFIED: 0,
  CONTROLLER_END: 1,
  ROBOT_DOG: 2,
  CLOUD_SERVER: 3,
};

export const decodeClientType = {
  0: "CLIENT_TYPE_UNSPECIFIED",
  1: "CONTROLLER_END",
  2: "ROBOT_DOG",
  3: "CLOUD_SERVER",
};

export const encodeNavigationState = {
  NAV_STATE_UNSPECIFIED: 0,
  IDLE: 1,
  NAVIGATING: 2,
  SUCCEEDED: 3,
  FAILED: 4,
  WAITING_FOR_HUMAN: 5,
  OBSTACLE_DETECTED_PAUSED: 6,
};

export const decodeNavigationState = {
  0: "NAV_STATE_UNSPECIFIED",
  1: "IDLE",
  2: "NAVIGATING",
  3: "SUCCEEDED",
  4: "FAILED",
  5: "WAITING_FOR_HUMAN",
  6: "OBSTACLE_DETECTED_PAUSED",
};

export const encodePromptActionType = {
  PROMPT_ACTION_TYPE_UNSPECIFIED: 0,
  HEAD_MOVEMENT: 1,
  POINTING_GESTURE: 2,
  PLAY_SOUND_CUE: 3,
  DISPLAY_VISUAL_CUE: 4,
};

export const decodePromptActionType = {
  0: "PROMPT_ACTION_TYPE_UNSPECIFIED",
  1: "HEAD_MOVEMENT",
  2: "POINTING_GESTURE",
  3: "PLAY_SOUND_CUE",
  4: "DISPLAY_VISUAL_CUE",
};

export const encodeHeadMovementTargetDirection = {
  HEAD_TARGET_UNSPECIFIED: 0,
  TOWARDS_ESTIMATED_CHILD_POSITION: 1,
  TOWARDS_ESTIMATED_RJA_OBJECT_POSITION: 2,
  RELATIVE_ANGLES_TO_ROBOT_BODY: 3,
  ABSOLUTE_ANGLES_IN_WORLD: 4,
};

export const decodeHeadMovementTargetDirection = {
  0: "HEAD_TARGET_UNSPECIFIED",
  1: "TOWARDS_ESTIMATED_CHILD_POSITION",
  2: "TOWARDS_ESTIMATED_RJA_OBJECT_POSITION",
  3: "RELATIVE_ANGLES_TO_ROBOT_BODY",
  4: "ABSOLUTE_ANGLES_IN_WORLD",
};

export const encodeHeadMovementIntensity = {
  HEAD_INTENSITY_UNSPECIFIED: 0,
  SUBTLE: 1,
  NORMAL: 2,
  EMPHATIC: 3,
};

export const decodeHeadMovementIntensity = {
  0: "HEAD_INTENSITY_UNSPECIFIED",
  1: "SUBTLE",
  2: "NORMAL",
  3: "EMPHATIC",
};

export const encodePointingLimb = {
  LIMB_UNSPECIFIED: 0,
  HEAD_POINTER: 1,
  LEFT_ARM: 2,
  RIGHT_ARM: 3,
};

export const decodePointingLimb = {
  0: "LIMB_UNSPECIFIED",
  1: "HEAD_POINTER",
  2: "LEFT_ARM",
  3: "RIGHT_ARM",
};

export const encodeChildResponseType = {
  CHILD_RESPONSE_TYPE_UNSPECIFIED: 0,
  CORRECT_RESPONSE: 1,
  INCORRECT_ATTENTION_TO_ROBOT: 2,
  INCORRECT_ATTENTION_TO_OTHER: 3,
  INCORRECT_NO_SHIFT_OF_ATTENTION: 4,
  NO_RESPONSE_DETECTED: 5,
  OPERATOR_MARKED_OTHER: 6,
};

export const decodeChildResponseType = {
  0: "CHILD_RESPONSE_TYPE_UNSPECIFIED",
  1: "CORRECT_RESPONSE",
  2: "INCORRECT_ATTENTION_TO_ROBOT",
  3: "INCORRECT_ATTENTION_TO_OTHER",
  4: "INCORRECT_NO_SHIFT_OF_ATTENTION",
  5: "NO_RESPONSE_DETECTED",
  6: "OPERATOR_MARKED_OTHER",
};

export const encodeFeedbackActionType = {
  FEEDBACK_ACTION_TYPE_UNSPECIFIED: 0,
  ROBOT_ANIMATION: 1,
  PLAY_FEEDBACK_SOUND: 2,
  DISPLAY_FEEDBACK_VISUAL: 3,
  ENGAGE_PERSONALIZED_CONTENT: 4,
};

export const decodeFeedbackActionType = {
  0: "FEEDBACK_ACTION_TYPE_UNSPECIFIED",
  1: "ROBOT_ANIMATION",
  2: "PLAY_FEEDBACK_SOUND",
  3: "DISPLAY_FEEDBACK_VISUAL",
  4: "ENGAGE_PERSONALIZED_CONTENT",
};

export const encodeRobotAnimationId = {
  ANIMATION_ID_UNSPECIFIED: 0,
  NOD_APPROVAL: 1,
  SHAKE_HEAD_GENTLE: 2,
  HAPPY_WIGGLE: 3,
  LOOK_INTERESTED: 4,
  ENCOURAGING_TILT: 5,
};

export const decodeRobotAnimationId = {
  0: "ANIMATION_ID_UNSPECIFIED",
  1: "NOD_APPROVAL",
  2: "SHAKE_HEAD_GENTLE",
  3: "HAPPY_WIGGLE",
  4: "LOOK_INTERESTED",
  5: "ENCOURAGING_TILT",
};

export const encodePersonalizedContentType = {
  PERSONALIZED_CONTENT_TYPE_UNSPECIFIED: 0,
  SOUND: 1,
  VISUAL: 2,
};

export const decodePersonalizedContentType = {
  0: "PERSONALIZED_CONTENT_TYPE_UNSPECIFIED",
  1: "SOUND",
  2: "VISUAL",
};

export const encodeSystemEventSeverity = {
  SEVERITY_UNSPECIFIED: 0,
  INFO: 1,
  WARNING: 2,
  ERROR: 3,
  CRITICAL: 4,
};

export const decodeSystemEventSeverity = {
  0: "SEVERITY_UNSPECIFIED",
  1: "INFO",
  2: "WARNING",
  3: "ERROR",
  4: "CRITICAL",
};

export function encodeHeader(message) {
  let bb = popByteBuffer();
  _encodeHeader(message, bb);
  return toUint8Array(bb);
}

function _encodeHeader(message, bb) {
  // optional string message_id = 1;
  let $message_id = message.message_id;
  if ($message_id !== undefined) {
    writeVarint32(bb, 10);
    writeString(bb, $message_id);
  }

  // optional int64 timestamp_utc_ms = 2;
  let $timestamp_utc_ms = message.timestamp_utc_ms;
  if ($timestamp_utc_ms !== undefined) {
    writeVarint32(bb, 16);
    writeVarint64(bb, $timestamp_utc_ms);
  }

  // optional string source_id = 3;
  let $source_id = message.source_id;
  if ($source_id !== undefined) {
    writeVarint32(bb, 26);
    writeString(bb, $source_id);
  }

  // optional string target_id = 4;
  let $target_id = message.target_id;
  if ($target_id !== undefined) {
    writeVarint32(bb, 34);
    writeString(bb, $target_id);
  }

  // optional string session_id = 5;
  let $session_id = message.session_id;
  if ($session_id !== undefined) {
    writeVarint32(bb, 42);
    writeString(bb, $session_id);
  }

  // optional string trial_id = 6;
  let $trial_id = message.trial_id;
  if ($trial_id !== undefined) {
    writeVarint32(bb, 50);
    writeString(bb, $trial_id);
  }
}

export function decodeHeader(binary) {
  return _decodeHeader(wrapByteBuffer(binary));
}

function _decodeHeader(bb) {
  let message = {};

  end_of_message: while (!isAtEnd(bb)) {
    let tag = readVarint32(bb);

    switch (tag >>> 3) {
      case 0:
        break end_of_message;

      // optional string message_id = 1;
      case 1: {
        message.message_id = readString(bb, readVarint32(bb));
        break;
      }

      // optional int64 timestamp_utc_ms = 2;
      case 2: {
        message.timestamp_utc_ms = readVarint64(bb, /* unsigned */ false);
        break;
      }

      // optional string source_id = 3;
      case 3: {
        message.source_id = readString(bb, readVarint32(bb));
        break;
      }

      // optional string target_id = 4;
      case 4: {
        message.target_id = readString(bb, readVarint32(bb));
        break;
      }

      // optional string session_id = 5;
      case 5: {
        message.session_id = readString(bb, readVarint32(bb));
        break;
      }

      // optional string trial_id = 6;
      case 6: {
        message.trial_id = readString(bb, readVarint32(bb));
        break;
      }

      default:
        skipUnknownField(bb, tag & 7);
    }
  }

  return message;
}

export function encodeVector3(message) {
  let bb = popByteBuffer();
  _encodeVector3(message, bb);
  return toUint8Array(bb);
}

function _encodeVector3(message, bb) {
  // optional float x = 1;
  let $x = message.x;
  if ($x !== undefined) {
    writeVarint32(bb, 13);
    writeFloat(bb, $x);
  }

  // optional float y = 2;
  let $y = message.y;
  if ($y !== undefined) {
    writeVarint32(bb, 21);
    writeFloat(bb, $y);
  }

  // optional float z = 3;
  let $z = message.z;
  if ($z !== undefined) {
    writeVarint32(bb, 29);
    writeFloat(bb, $z);
  }
}

export function decodeVector3(binary) {
  return _decodeVector3(wrapByteBuffer(binary));
}

function _decodeVector3(bb) {
  let message = {};

  end_of_message: while (!isAtEnd(bb)) {
    let tag = readVarint32(bb);

    switch (tag >>> 3) {
      case 0:
        break end_of_message;

      // optional float x = 1;
      case 1: {
        message.x = readFloat(bb);
        break;
      }

      // optional float y = 2;
      case 2: {
        message.y = readFloat(bb);
        break;
      }

      // optional float z = 3;
      case 3: {
        message.z = readFloat(bb);
        break;
      }

      default:
        skipUnknownField(bb, tag & 7);
    }
  }

  return message;
}

export function encodeQuaternion(message) {
  let bb = popByteBuffer();
  _encodeQuaternion(message, bb);
  return toUint8Array(bb);
}

function _encodeQuaternion(message, bb) {
  // optional float x = 1;
  let $x = message.x;
  if ($x !== undefined) {
    writeVarint32(bb, 13);
    writeFloat(bb, $x);
  }

  // optional float y = 2;
  let $y = message.y;
  if ($y !== undefined) {
    writeVarint32(bb, 21);
    writeFloat(bb, $y);
  }

  // optional float z = 3;
  let $z = message.z;
  if ($z !== undefined) {
    writeVarint32(bb, 29);
    writeFloat(bb, $z);
  }

  // optional float w = 4;
  let $w = message.w;
  if ($w !== undefined) {
    writeVarint32(bb, 37);
    writeFloat(bb, $w);
  }
}

export function decodeQuaternion(binary) {
  return _decodeQuaternion(wrapByteBuffer(binary));
}

function _decodeQuaternion(bb) {
  let message = {};

  end_of_message: while (!isAtEnd(bb)) {
    let tag = readVarint32(bb);

    switch (tag >>> 3) {
      case 0:
        break end_of_message;

      // optional float x = 1;
      case 1: {
        message.x = readFloat(bb);
        break;
      }

      // optional float y = 2;
      case 2: {
        message.y = readFloat(bb);
        break;
      }

      // optional float z = 3;
      case 3: {
        message.z = readFloat(bb);
        break;
      }

      // optional float w = 4;
      case 4: {
        message.w = readFloat(bb);
        break;
      }

      default:
        skipUnknownField(bb, tag & 7);
    }
  }

  return message;
}

export function encodePose(message) {
  let bb = popByteBuffer();
  _encodePose(message, bb);
  return toUint8Array(bb);
}

function _encodePose(message, bb) {
  // optional Vector3 position = 1;
  let $position = message.position;
  if ($position !== undefined) {
    writeVarint32(bb, 10);
    let nested = popByteBuffer();
    _encodeVector3($position, nested);
    writeVarint32(bb, nested.limit);
    writeByteBuffer(bb, nested);
    pushByteBuffer(nested);
  }

  // optional Quaternion orientation = 2;
  let $orientation = message.orientation;
  if ($orientation !== undefined) {
    writeVarint32(bb, 18);
    let nested = popByteBuffer();
    _encodeQuaternion($orientation, nested);
    writeVarint32(bb, nested.limit);
    writeByteBuffer(bb, nested);
    pushByteBuffer(nested);
  }
}

export function decodePose(binary) {
  return _decodePose(wrapByteBuffer(binary));
}

function _decodePose(bb) {
  let message = {};

  end_of_message: while (!isAtEnd(bb)) {
    let tag = readVarint32(bb);

    switch (tag >>> 3) {
      case 0:
        break end_of_message;

      // optional Vector3 position = 1;
      case 1: {
        let limit = pushTemporaryLength(bb);
        message.position = _decodeVector3(bb);
        bb.limit = limit;
        break;
      }

      // optional Quaternion orientation = 2;
      case 2: {
        let limit = pushTemporaryLength(bb);
        message.orientation = _decodeQuaternion(bb);
        bb.limit = limit;
        break;
      }

      default:
        skipUnknownField(bb, tag & 7);
    }
  }

  return message;
}

export function encodeUdpPacketWrapper(message) {
  let bb = popByteBuffer();
  _encodeUdpPacketWrapper(message, bb);
  return toUint8Array(bb);
}

function _encodeUdpPacketWrapper(message, bb) {
  // optional Header header = 1;
  let $header = message.header;
  if ($header !== undefined) {
    writeVarint32(bb, 10);
    let nested = popByteBuffer();
    _encodeHeader($header, nested);
    writeVarint32(bb, nested.limit);
    writeByteBuffer(bb, nested);
    pushByteBuffer(nested);
  }

  // optional string target_client_id_for_relay = 2;
  let $target_client_id_for_relay = message.target_client_id_for_relay;
  if ($target_client_id_for_relay !== undefined) {
    writeVarint32(bb, 18);
    writeString(bb, $target_client_id_for_relay);
  }

  // optional string actual_message_type = 3;
  let $actual_message_type = message.actual_message_type;
  if ($actual_message_type !== undefined) {
    writeVarint32(bb, 26);
    writeString(bb, $actual_message_type);
  }

  // optional bytes actual_message_data = 4;
  let $actual_message_data = message.actual_message_data;
  if ($actual_message_data !== undefined) {
    writeVarint32(bb, 34);
    writeVarint32(bb, $actual_message_data.length), writeBytes(bb, $actual_message_data);
  }
}

export function decodeUdpPacketWrapper(binary) {
  return _decodeUdpPacketWrapper(wrapByteBuffer(binary));
}

function _decodeUdpPacketWrapper(bb) {
  let message = {};

  end_of_message: while (!isAtEnd(bb)) {
    let tag = readVarint32(bb);

    switch (tag >>> 3) {
      case 0:
        break end_of_message;

      // optional Header header = 1;
      case 1: {
        let limit = pushTemporaryLength(bb);
        message.header = _decodeHeader(bb);
        bb.limit = limit;
        break;
      }

      // optional string target_client_id_for_relay = 2;
      case 2: {
        message.target_client_id_for_relay = readString(bb, readVarint32(bb));
        break;
      }

      // optional string actual_message_type = 3;
      case 3: {
        message.actual_message_type = readString(bb, readVarint32(bb));
        break;
      }

      // optional bytes actual_message_data = 4;
      case 4: {
        message.actual_message_data = readBytes(bb, readVarint32(bb));
        break;
      }

      default:
        skipUnknownField(bb, tag & 7);
    }
  }

  return message;
}

export function encodeRegisterClientRequest(message) {
  let bb = popByteBuffer();
  _encodeRegisterClientRequest(message, bb);
  return toUint8Array(bb);
}

function _encodeRegisterClientRequest(message, bb) {
  // optional Header header = 1;
  let $header = message.header;
  if ($header !== undefined) {
    writeVarint32(bb, 10);
    let nested = popByteBuffer();
    _encodeHeader($header, nested);
    writeVarint32(bb, nested.limit);
    writeByteBuffer(bb, nested);
    pushByteBuffer(nested);
  }

  // optional ClientType client_type = 2;
  let $client_type = message.client_type;
  if ($client_type !== undefined) {
    writeVarint32(bb, 16);
    writeVarint32(bb, encodeClientType[$client_type]);
  }

  // optional string client_id = 3;
  let $client_id = message.client_id;
  if ($client_id !== undefined) {
    writeVarint32(bb, 26);
    writeString(bb, $client_id);
  }

  // optional string client_version = 4;
  let $client_version = message.client_version;
  if ($client_version !== undefined) {
    writeVarint32(bb, 34);
    writeString(bb, $client_version);
  }

  // repeated string capabilities = 5;
  let array$capabilities = message.capabilities;
  if (array$capabilities !== undefined) {
    for (let value of array$capabilities) {
      writeVarint32(bb, 42);
      writeString(bb, value);
    }
  }
}

export function decodeRegisterClientRequest(binary) {
  return _decodeRegisterClientRequest(wrapByteBuffer(binary));
}

function _decodeRegisterClientRequest(bb) {
  let message = {};

  end_of_message: while (!isAtEnd(bb)) {
    let tag = readVarint32(bb);

    switch (tag >>> 3) {
      case 0:
        break end_of_message;

      // optional Header header = 1;
      case 1: {
        let limit = pushTemporaryLength(bb);
        message.header = _decodeHeader(bb);
        bb.limit = limit;
        break;
      }

      // optional ClientType client_type = 2;
      case 2: {
        message.client_type = decodeClientType[readVarint32(bb)];
        break;
      }

      // optional string client_id = 3;
      case 3: {
        message.client_id = readString(bb, readVarint32(bb));
        break;
      }

      // optional string client_version = 4;
      case 4: {
        message.client_version = readString(bb, readVarint32(bb));
        break;
      }

      // repeated string capabilities = 5;
      case 5: {
        let values = message.capabilities || (message.capabilities = []);
        values.push(readString(bb, readVarint32(bb)));
        break;
      }

      default:
        skipUnknownField(bb, tag & 7);
    }
  }

  return message;
}

export function encodeRegisterClientResponse(message) {
  let bb = popByteBuffer();
  _encodeRegisterClientResponse(message, bb);
  return toUint8Array(bb);
}

function _encodeRegisterClientResponse(message, bb) {
  // optional Header header = 1;
  let $header = message.header;
  if ($header !== undefined) {
    writeVarint32(bb, 10);
    let nested = popByteBuffer();
    _encodeHeader($header, nested);
    writeVarint32(bb, nested.limit);
    writeByteBuffer(bb, nested);
    pushByteBuffer(nested);
  }

  // optional bool success = 2;
  let $success = message.success;
  if ($success !== undefined) {
    writeVarint32(bb, 16);
    writeByte(bb, $success ? 1 : 0);
  }

  // optional string message = 3;
  let $message = message.message;
  if ($message !== undefined) {
    writeVarint32(bb, 26);
    writeString(bb, $message);
  }

  // optional string session_token = 4;
  let $session_token = message.session_token;
  if ($session_token !== undefined) {
    writeVarint32(bb, 34);
    writeString(bb, $session_token);
  }
}

export function decodeRegisterClientResponse(binary) {
  return _decodeRegisterClientResponse(wrapByteBuffer(binary));
}

function _decodeRegisterClientResponse(bb) {
  let message = {};

  end_of_message: while (!isAtEnd(bb)) {
    let tag = readVarint32(bb);

    switch (tag >>> 3) {
      case 0:
        break end_of_message;

      // optional Header header = 1;
      case 1: {
        let limit = pushTemporaryLength(bb);
        message.header = _decodeHeader(bb);
        bb.limit = limit;
        break;
      }

      // optional bool success = 2;
      case 2: {
        message.success = !!readByte(bb);
        break;
      }

      // optional string message = 3;
      case 3: {
        message.message = readString(bb, readVarint32(bb));
        break;
      }

      // optional string session_token = 4;
      case 4: {
        message.session_token = readString(bb, readVarint32(bb));
        break;
      }

      default:
        skipUnknownField(bb, tag & 7);
    }
  }

  return message;
}

export function encodeNavigateToPointCommand(message) {
  let bb = popByteBuffer();
  _encodeNavigateToPointCommand(message, bb);
  return toUint8Array(bb);
}

function _encodeNavigateToPointCommand(message, bb) {
  // optional Header header = 1;
  let $header = message.header;
  if ($header !== undefined) {
    writeVarint32(bb, 10);
    let nested = popByteBuffer();
    _encodeHeader($header, nested);
    writeVarint32(bb, nested.limit);
    writeByteBuffer(bb, nested);
    pushByteBuffer(nested);
  }

  // optional string rja_point_id = 2;
  let $rja_point_id = message.rja_point_id;
  if ($rja_point_id !== undefined) {
    writeVarint32(bb, 18);
    writeString(bb, $rja_point_id);
  }

  // optional Pose target_pose_override = 3;
  let $target_pose_override = message.target_pose_override;
  if ($target_pose_override !== undefined) {
    writeVarint32(bb, 26);
    let nested = popByteBuffer();
    _encodePose($target_pose_override, nested);
    writeVarint32(bb, nested.limit);
    writeByteBuffer(bb, nested);
    pushByteBuffer(nested);
  }

  // optional bool wait_for_human_if_lost = 4;
  let $wait_for_human_if_lost = message.wait_for_human_if_lost;
  if ($wait_for_human_if_lost !== undefined) {
    writeVarint32(bb, 32);
    writeByte(bb, $wait_for_human_if_lost ? 1 : 0);
  }

  // optional int32 wait_duration_ms = 5;
  let $wait_duration_ms = message.wait_duration_ms;
  if ($wait_duration_ms !== undefined) {
    writeVarint32(bb, 40);
    writeVarint64(bb, intToLong($wait_duration_ms));
  }
}

export function decodeNavigateToPointCommand(binary) {
  return _decodeNavigateToPointCommand(wrapByteBuffer(binary));
}

function _decodeNavigateToPointCommand(bb) {
  let message = {};

  end_of_message: while (!isAtEnd(bb)) {
    let tag = readVarint32(bb);

    switch (tag >>> 3) {
      case 0:
        break end_of_message;

      // optional Header header = 1;
      case 1: {
        let limit = pushTemporaryLength(bb);
        message.header = _decodeHeader(bb);
        bb.limit = limit;
        break;
      }

      // optional string rja_point_id = 2;
      case 2: {
        message.rja_point_id = readString(bb, readVarint32(bb));
        break;
      }

      // optional Pose target_pose_override = 3;
      case 3: {
        let limit = pushTemporaryLength(bb);
        message.target_pose_override = _decodePose(bb);
        bb.limit = limit;
        break;
      }

      // optional bool wait_for_human_if_lost = 4;
      case 4: {
        message.wait_for_human_if_lost = !!readByte(bb);
        break;
      }

      // optional int32 wait_duration_ms = 5;
      case 5: {
        message.wait_duration_ms = readVarint32(bb);
        break;
      }

      default:
        skipUnknownField(bb, tag & 7);
    }
  }

  return message;
}

export function encodeHumanDetectionDetails(message) {
  let bb = popByteBuffer();
  _encodeHumanDetectionDetails(message, bb);
  return toUint8Array(bb);
}

function _encodeHumanDetectionDetails(message, bb) {
  // optional bool is_present = 1;
  let $is_present = message.is_present;
  if ($is_present !== undefined) {
    writeVarint32(bb, 8);
    writeByte(bb, $is_present ? 1 : 0);
  }

  // optional float distance_m = 2;
  let $distance_m = message.distance_m;
  if ($distance_m !== undefined) {
    writeVarint32(bb, 21);
    writeFloat(bb, $distance_m);
  }

  // optional Vector3 relative_position = 3;
  let $relative_position = message.relative_position;
  if ($relative_position !== undefined) {
    writeVarint32(bb, 26);
    let nested = popByteBuffer();
    _encodeVector3($relative_position, nested);
    writeVarint32(bb, nested.limit);
    writeByteBuffer(bb, nested);
    pushByteBuffer(nested);
  }

  // optional bool is_within_interaction_zone = 4;
  let $is_within_interaction_zone = message.is_within_interaction_zone;
  if ($is_within_interaction_zone !== undefined) {
    writeVarint32(bb, 32);
    writeByte(bb, $is_within_interaction_zone ? 1 : 0);
  }
}

export function decodeHumanDetectionDetails(binary) {
  return _decodeHumanDetectionDetails(wrapByteBuffer(binary));
}

function _decodeHumanDetectionDetails(bb) {
  let message = {};

  end_of_message: while (!isAtEnd(bb)) {
    let tag = readVarint32(bb);

    switch (tag >>> 3) {
      case 0:
        break end_of_message;

      // optional bool is_present = 1;
      case 1: {
        message.is_present = !!readByte(bb);
        break;
      }

      // optional float distance_m = 2;
      case 2: {
        message.distance_m = readFloat(bb);
        break;
      }

      // optional Vector3 relative_position = 3;
      case 3: {
        let limit = pushTemporaryLength(bb);
        message.relative_position = _decodeVector3(bb);
        bb.limit = limit;
        break;
      }

      // optional bool is_within_interaction_zone = 4;
      case 4: {
        message.is_within_interaction_zone = !!readByte(bb);
        break;
      }

      default:
        skipUnknownField(bb, tag & 7);
    }
  }

  return message;
}

export function encodeRjaObjectDetectionDetails(message) {
  let bb = popByteBuffer();
  _encodeRjaObjectDetectionDetails(message, bb);
  return toUint8Array(bb);
}

function _encodeRjaObjectDetectionDetails(message, bb) {
  // optional string object_id = 1;
  let $object_id = message.object_id;
  if ($object_id !== undefined) {
    writeVarint32(bb, 10);
    writeString(bb, $object_id);
  }

  // optional bool is_visible = 2;
  let $is_visible = message.is_visible;
  if ($is_visible !== undefined) {
    writeVarint32(bb, 16);
    writeByte(bb, $is_visible ? 1 : 0);
  }

  // optional Vector3 relative_position_to_robot = 3;
  let $relative_position_to_robot = message.relative_position_to_robot;
  if ($relative_position_to_robot !== undefined) {
    writeVarint32(bb, 26);
    let nested = popByteBuffer();
    _encodeVector3($relative_position_to_robot, nested);
    writeVarint32(bb, nested.limit);
    writeByteBuffer(bb, nested);
    pushByteBuffer(nested);
  }
}

export function decodeRjaObjectDetectionDetails(binary) {
  return _decodeRjaObjectDetectionDetails(wrapByteBuffer(binary));
}

function _decodeRjaObjectDetectionDetails(bb) {
  let message = {};

  end_of_message: while (!isAtEnd(bb)) {
    let tag = readVarint32(bb);

    switch (tag >>> 3) {
      case 0:
        break end_of_message;

      // optional string object_id = 1;
      case 1: {
        message.object_id = readString(bb, readVarint32(bb));
        break;
      }

      // optional bool is_visible = 2;
      case 2: {
        message.is_visible = !!readByte(bb);
        break;
      }

      // optional Vector3 relative_position_to_robot = 3;
      case 3: {
        let limit = pushTemporaryLength(bb);
        message.relative_position_to_robot = _decodeVector3(bb);
        bb.limit = limit;
        break;
      }

      default:
        skipUnknownField(bb, tag & 7);
    }
  }

  return message;
}

export function encodeActiveActionStatus(message) {
  let bb = popByteBuffer();
  _encodeActiveActionStatus(message, bb);
  return toUint8Array(bb);
}

function _encodeActiveActionStatus(message, bb) {
  // optional string action_name = 1;
  let $action_name = message.action_name;
  if ($action_name !== undefined) {
    writeVarint32(bb, 10);
    writeString(bb, $action_name);
  }

  // optional float progress_percent = 2;
  let $progress_percent = message.progress_percent;
  if ($progress_percent !== undefined) {
    writeVarint32(bb, 21);
    writeFloat(bb, $progress_percent);
  }

  // optional string status_description = 3;
  let $status_description = message.status_description;
  if ($status_description !== undefined) {
    writeVarint32(bb, 26);
    writeString(bb, $status_description);
  }
}

export function decodeActiveActionStatus(binary) {
  return _decodeActiveActionStatus(wrapByteBuffer(binary));
}

function _decodeActiveActionStatus(bb) {
  let message = {};

  end_of_message: while (!isAtEnd(bb)) {
    let tag = readVarint32(bb);

    switch (tag >>> 3) {
      case 0:
        break end_of_message;

      // optional string action_name = 1;
      case 1: {
        message.action_name = readString(bb, readVarint32(bb));
        break;
      }

      // optional float progress_percent = 2;
      case 2: {
        message.progress_percent = readFloat(bb);
        break;
      }

      // optional string status_description = 3;
      case 3: {
        message.status_description = readString(bb, readVarint32(bb));
        break;
      }

      default:
        skipUnknownField(bb, tag & 7);
    }
  }

  return message;
}

export function encodeRobotStatusUpdate(message) {
  let bb = popByteBuffer();
  _encodeRobotStatusUpdate(message, bb);
  return toUint8Array(bb);
}

function _encodeRobotStatusUpdate(message, bb) {
  // optional Header header = 1;
  let $header = message.header;
  if ($header !== undefined) {
    writeVarint32(bb, 10);
    let nested = popByteBuffer();
    _encodeHeader($header, nested);
    writeVarint32(bb, nested.limit);
    writeByteBuffer(bb, nested);
    pushByteBuffer(nested);
  }

  // optional float battery_percent = 2;
  let $battery_percent = message.battery_percent;
  if ($battery_percent !== undefined) {
    writeVarint32(bb, 21);
    writeFloat(bb, $battery_percent);
  }

  // optional Pose current_world_pose = 3;
  let $current_world_pose = message.current_world_pose;
  if ($current_world_pose !== undefined) {
    writeVarint32(bb, 26);
    let nested = popByteBuffer();
    _encodePose($current_world_pose, nested);
    writeVarint32(bb, nested.limit);
    writeByteBuffer(bb, nested);
    pushByteBuffer(nested);
  }

  // optional NavigationState navigation_state = 4;
  let $navigation_state = message.navigation_state;
  if ($navigation_state !== undefined) {
    writeVarint32(bb, 32);
    writeVarint32(bb, encodeNavigationState[$navigation_state]);
  }

  // optional string current_rja_point_id = 5;
  let $current_rja_point_id = message.current_rja_point_id;
  if ($current_rja_point_id !== undefined) {
    writeVarint32(bb, 42);
    writeString(bb, $current_rja_point_id);
  }

  // optional HumanDetectionDetails human_detection = 6;
  let $human_detection = message.human_detection;
  if ($human_detection !== undefined) {
    writeVarint32(bb, 50);
    let nested = popByteBuffer();
    _encodeHumanDetectionDetails($human_detection, nested);
    writeVarint32(bb, nested.limit);
    writeByteBuffer(bb, nested);
    pushByteBuffer(nested);
  }

  // repeated RjaObjectDetectionDetails rja_object_detections = 7;
  let array$rja_object_detections = message.rja_object_detections;
  if (array$rja_object_detections !== undefined) {
    for (let value of array$rja_object_detections) {
      writeVarint32(bb, 58);
      let nested = popByteBuffer();
      _encodeRjaObjectDetectionDetails(value, nested);
      writeVarint32(bb, nested.limit);
      writeByteBuffer(bb, nested);
      pushByteBuffer(nested);
    }
  }

  // optional ActiveActionStatus current_action = 8;
  let $current_action = message.current_action;
  if ($current_action !== undefined) {
    writeVarint32(bb, 66);
    let nested = popByteBuffer();
    _encodeActiveActionStatus($current_action, nested);
    writeVarint32(bb, nested.limit);
    writeByteBuffer(bb, nested);
    pushByteBuffer(nested);
  }

  // optional SystemEventSeverity overall_system_health = 9;
  let $overall_system_health = message.overall_system_health;
  if ($overall_system_health !== undefined) {
    writeVarint32(bb, 72);
    writeVarint32(bb, encodeSystemEventSeverity[$overall_system_health]);
  }

  // repeated string error_messages_active = 10;
  let array$error_messages_active = message.error_messages_active;
  if (array$error_messages_active !== undefined) {
    for (let value of array$error_messages_active) {
      writeVarint32(bb, 82);
      writeString(bb, value);
    }
  }
}

export function decodeRobotStatusUpdate(binary) {
  return _decodeRobotStatusUpdate(wrapByteBuffer(binary));
}

function _decodeRobotStatusUpdate(bb) {
  let message = {};

  end_of_message: while (!isAtEnd(bb)) {
    let tag = readVarint32(bb);

    switch (tag >>> 3) {
      case 0:
        break end_of_message;

      // optional Header header = 1;
      case 1: {
        let limit = pushTemporaryLength(bb);
        message.header = _decodeHeader(bb);
        bb.limit = limit;
        break;
      }

      // optional float battery_percent = 2;
      case 2: {
        message.battery_percent = readFloat(bb);
        break;
      }

      // optional Pose current_world_pose = 3;
      case 3: {
        let limit = pushTemporaryLength(bb);
        message.current_world_pose = _decodePose(bb);
        bb.limit = limit;
        break;
      }

      // optional NavigationState navigation_state = 4;
      case 4: {
        message.navigation_state = decodeNavigationState[readVarint32(bb)];
        break;
      }

      // optional string current_rja_point_id = 5;
      case 5: {
        message.current_rja_point_id = readString(bb, readVarint32(bb));
        break;
      }

      // optional HumanDetectionDetails human_detection = 6;
      case 6: {
        let limit = pushTemporaryLength(bb);
        message.human_detection = _decodeHumanDetectionDetails(bb);
        bb.limit = limit;
        break;
      }

      // repeated RjaObjectDetectionDetails rja_object_detections = 7;
      case 7: {
        let limit = pushTemporaryLength(bb);
        let values = message.rja_object_detections || (message.rja_object_detections = []);
        values.push(_decodeRjaObjectDetectionDetails(bb));
        bb.limit = limit;
        break;
      }

      // optional ActiveActionStatus current_action = 8;
      case 8: {
        let limit = pushTemporaryLength(bb);
        message.current_action = _decodeActiveActionStatus(bb);
        bb.limit = limit;
        break;
      }

      // optional SystemEventSeverity overall_system_health = 9;
      case 9: {
        message.overall_system_health = decodeSystemEventSeverity[readVarint32(bb)];
        break;
      }

      // repeated string error_messages_active = 10;
      case 10: {
        let values = message.error_messages_active || (message.error_messages_active = []);
        values.push(readString(bb, readVarint32(bb)));
        break;
      }

      default:
        skipUnknownField(bb, tag & 7);
    }
  }

  return message;
}

export function encodeHeadMovementParams(message) {
  let bb = popByteBuffer();
  _encodeHeadMovementParams(message, bb);
  return toUint8Array(bb);
}

function _encodeHeadMovementParams(message, bb) {
  // optional HeadMovementTargetDirection target_direction = 1;
  let $target_direction = message.target_direction;
  if ($target_direction !== undefined) {
    writeVarint32(bb, 8);
    writeVarint32(bb, encodeHeadMovementTargetDirection[$target_direction]);
  }

  // optional HeadMovementIntensity intensity = 2;
  let $intensity = message.intensity;
  if ($intensity !== undefined) {
    writeVarint32(bb, 16);
    writeVarint32(bb, encodeHeadMovementIntensity[$intensity]);
  }

  // optional Pose specific_target_pose = 3;
  let $specific_target_pose = message.specific_target_pose;
  if ($specific_target_pose !== undefined) {
    writeVarint32(bb, 26);
    let nested = popByteBuffer();
    _encodePose($specific_target_pose, nested);
    writeVarint32(bb, nested.limit);
    writeByteBuffer(bb, nested);
    pushByteBuffer(nested);
  }
}

export function decodeHeadMovementParams(binary) {
  return _decodeHeadMovementParams(wrapByteBuffer(binary));
}

function _decodeHeadMovementParams(bb) {
  let message = {};

  end_of_message: while (!isAtEnd(bb)) {
    let tag = readVarint32(bb);

    switch (tag >>> 3) {
      case 0:
        break end_of_message;

      // optional HeadMovementTargetDirection target_direction = 1;
      case 1: {
        message.target_direction = decodeHeadMovementTargetDirection[readVarint32(bb)];
        break;
      }

      // optional HeadMovementIntensity intensity = 2;
      case 2: {
        message.intensity = decodeHeadMovementIntensity[readVarint32(bb)];
        break;
      }

      // optional Pose specific_target_pose = 3;
      case 3: {
        let limit = pushTemporaryLength(bb);
        message.specific_target_pose = _decodePose(bb);
        bb.limit = limit;
        break;
      }

      default:
        skipUnknownField(bb, tag & 7);
    }
  }

  return message;
}

export function encodePointingGestureParams(message) {
  let bb = popByteBuffer();
  _encodePointingGestureParams(message, bb);
  return toUint8Array(bb);
}

function _encodePointingGestureParams(message, bb) {
  // optional PointingLimb limb_to_use = 1;
  let $limb_to_use = message.limb_to_use;
  if ($limb_to_use !== undefined) {
    writeVarint32(bb, 8);
    writeVarint32(bb, encodePointingLimb[$limb_to_use]);
  }

  // optional Vector3 target_object_relative_position = 2;
  let $target_object_relative_position = message.target_object_relative_position;
  if ($target_object_relative_position !== undefined) {
    writeVarint32(bb, 18);
    let nested = popByteBuffer();
    _encodeVector3($target_object_relative_position, nested);
    writeVarint32(bb, nested.limit);
    writeByteBuffer(bb, nested);
    pushByteBuffer(nested);
  }
}

export function decodePointingGestureParams(binary) {
  return _decodePointingGestureParams(wrapByteBuffer(binary));
}

function _decodePointingGestureParams(bb) {
  let message = {};

  end_of_message: while (!isAtEnd(bb)) {
    let tag = readVarint32(bb);

    switch (tag >>> 3) {
      case 0:
        break end_of_message;

      // optional PointingLimb limb_to_use = 1;
      case 1: {
        message.limb_to_use = decodePointingLimb[readVarint32(bb)];
        break;
      }

      // optional Vector3 target_object_relative_position = 2;
      case 2: {
        let limit = pushTemporaryLength(bb);
        message.target_object_relative_position = _decodeVector3(bb);
        bb.limit = limit;
        break;
      }

      default:
        skipUnknownField(bb, tag & 7);
    }
  }

  return message;
}

export function encodePlaySoundCueParams(message) {
  let bb = popByteBuffer();
  _encodePlaySoundCueParams(message, bb);
  return toUint8Array(bb);
}

function _encodePlaySoundCueParams(message, bb) {
  // optional string sound_id_or_filename = 1;
  let $sound_id_or_filename = message.sound_id_or_filename;
  if ($sound_id_or_filename !== undefined) {
    writeVarint32(bb, 10);
    writeString(bb, $sound_id_or_filename);
  }

  // optional float volume_level = 2;
  let $volume_level = message.volume_level;
  if ($volume_level !== undefined) {
    writeVarint32(bb, 21);
    writeFloat(bb, $volume_level);
  }

  // optional bool loop = 3;
  let $loop = message.loop;
  if ($loop !== undefined) {
    writeVarint32(bb, 24);
    writeByte(bb, $loop ? 1 : 0);
  }
}

export function decodePlaySoundCueParams(binary) {
  return _decodePlaySoundCueParams(wrapByteBuffer(binary));
}

function _decodePlaySoundCueParams(bb) {
  let message = {};

  end_of_message: while (!isAtEnd(bb)) {
    let tag = readVarint32(bb);

    switch (tag >>> 3) {
      case 0:
        break end_of_message;

      // optional string sound_id_or_filename = 1;
      case 1: {
        message.sound_id_or_filename = readString(bb, readVarint32(bb));
        break;
      }

      // optional float volume_level = 2;
      case 2: {
        message.volume_level = readFloat(bb);
        break;
      }

      // optional bool loop = 3;
      case 3: {
        message.loop = !!readByte(bb);
        break;
      }

      default:
        skipUnknownField(bb, tag & 7);
    }
  }

  return message;
}

export function encodeDisplayVisualCueParams(message) {
  let bb = popByteBuffer();
  _encodeDisplayVisualCueParams(message, bb);
  return toUint8Array(bb);
}

function _encodeDisplayVisualCueParams(message, bb) {
  // optional string visual_cue_id_or_filename = 1;
  let $visual_cue_id_or_filename = message.visual_cue_id_or_filename;
  if ($visual_cue_id_or_filename !== undefined) {
    writeVarint32(bb, 10);
    writeString(bb, $visual_cue_id_or_filename);
  }
}

export function decodeDisplayVisualCueParams(binary) {
  return _decodeDisplayVisualCueParams(wrapByteBuffer(binary));
}

function _decodeDisplayVisualCueParams(bb) {
  let message = {};

  end_of_message: while (!isAtEnd(bb)) {
    let tag = readVarint32(bb);

    switch (tag >>> 3) {
      case 0:
        break end_of_message;

      // optional string visual_cue_id_or_filename = 1;
      case 1: {
        message.visual_cue_id_or_filename = readString(bb, readVarint32(bb));
        break;
      }

      default:
        skipUnknownField(bb, tag & 7);
    }
  }

  return message;
}

export function encodePromptAction(message) {
  let bb = popByteBuffer();
  _encodePromptAction(message, bb);
  return toUint8Array(bb);
}

function _encodePromptAction(message, bb) {
  // optional string action_id = 1;
  let $action_id = message.action_id;
  if ($action_id !== undefined) {
    writeVarint32(bb, 10);
    writeString(bb, $action_id);
  }

  // optional PromptActionType type = 2;
  let $type = message.type;
  if ($type !== undefined) {
    writeVarint32(bb, 16);
    writeVarint32(bb, encodePromptActionType[$type]);
  }

  // optional HeadMovementParams head_params = 3;
  let $head_params = message.head_params;
  if ($head_params !== undefined) {
    writeVarint32(bb, 26);
    let nested = popByteBuffer();
    _encodeHeadMovementParams($head_params, nested);
    writeVarint32(bb, nested.limit);
    writeByteBuffer(bb, nested);
    pushByteBuffer(nested);
  }

  // optional PointingGestureParams pointing_params = 4;
  let $pointing_params = message.pointing_params;
  if ($pointing_params !== undefined) {
    writeVarint32(bb, 34);
    let nested = popByteBuffer();
    _encodePointingGestureParams($pointing_params, nested);
    writeVarint32(bb, nested.limit);
    writeByteBuffer(bb, nested);
    pushByteBuffer(nested);
  }

  // optional PlaySoundCueParams sound_params = 5;
  let $sound_params = message.sound_params;
  if ($sound_params !== undefined) {
    writeVarint32(bb, 42);
    let nested = popByteBuffer();
    _encodePlaySoundCueParams($sound_params, nested);
    writeVarint32(bb, nested.limit);
    writeByteBuffer(bb, nested);
    pushByteBuffer(nested);
  }

  // optional DisplayVisualCueParams visual_params = 6;
  let $visual_params = message.visual_params;
  if ($visual_params !== undefined) {
    writeVarint32(bb, 50);
    let nested = popByteBuffer();
    _encodeDisplayVisualCueParams($visual_params, nested);
    writeVarint32(bb, nested.limit);
    writeByteBuffer(bb, nested);
    pushByteBuffer(nested);
  }

  // optional int32 start_delay_ms = 7;
  let $start_delay_ms = message.start_delay_ms;
  if ($start_delay_ms !== undefined) {
    writeVarint32(bb, 56);
    writeVarint64(bb, intToLong($start_delay_ms));
  }

  // optional int32 estimated_duration_ms = 8;
  let $estimated_duration_ms = message.estimated_duration_ms;
  if ($estimated_duration_ms !== undefined) {
    writeVarint32(bb, 64);
    writeVarint64(bb, intToLong($estimated_duration_ms));
  }
}

export function decodePromptAction(binary) {
  return _decodePromptAction(wrapByteBuffer(binary));
}

function _decodePromptAction(bb) {
  let message = {};

  end_of_message: while (!isAtEnd(bb)) {
    let tag = readVarint32(bb);

    switch (tag >>> 3) {
      case 0:
        break end_of_message;

      // optional string action_id = 1;
      case 1: {
        message.action_id = readString(bb, readVarint32(bb));
        break;
      }

      // optional PromptActionType type = 2;
      case 2: {
        message.type = decodePromptActionType[readVarint32(bb)];
        break;
      }

      // optional HeadMovementParams head_params = 3;
      case 3: {
        let limit = pushTemporaryLength(bb);
        message.head_params = _decodeHeadMovementParams(bb);
        bb.limit = limit;
        break;
      }

      // optional PointingGestureParams pointing_params = 4;
      case 4: {
        let limit = pushTemporaryLength(bb);
        message.pointing_params = _decodePointingGestureParams(bb);
        bb.limit = limit;
        break;
      }

      // optional PlaySoundCueParams sound_params = 5;
      case 5: {
        let limit = pushTemporaryLength(bb);
        message.sound_params = _decodePlaySoundCueParams(bb);
        bb.limit = limit;
        break;
      }

      // optional DisplayVisualCueParams visual_params = 6;
      case 6: {
        let limit = pushTemporaryLength(bb);
        message.visual_params = _decodeDisplayVisualCueParams(bb);
        bb.limit = limit;
        break;
      }

      // optional int32 start_delay_ms = 7;
      case 7: {
        message.start_delay_ms = readVarint32(bb);
        break;
      }

      // optional int32 estimated_duration_ms = 8;
      case 8: {
        message.estimated_duration_ms = readVarint32(bb);
        break;
      }

      default:
        skipUnknownField(bb, tag & 7);
    }
  }

  return message;
}

export function encodeRjaPromptCommand(message) {
  let bb = popByteBuffer();
  _encodeRjaPromptCommand(message, bb);
  return toUint8Array(bb);
}

function _encodeRjaPromptCommand(message, bb) {
  // optional Header header = 1;
  let $header = message.header;
  if ($header !== undefined) {
    writeVarint32(bb, 10);
    let nested = popByteBuffer();
    _encodeHeader($header, nested);
    writeVarint32(bb, nested.limit);
    writeByteBuffer(bb, nested);
    pushByteBuffer(nested);
  }

  // optional int32 child_current_level = 2;
  let $child_current_level = message.child_current_level;
  if ($child_current_level !== undefined) {
    writeVarint32(bb, 16);
    writeVarint64(bb, intToLong($child_current_level));
  }

  // repeated PromptAction actions = 3;
  let array$actions = message.actions;
  if (array$actions !== undefined) {
    for (let value of array$actions) {
      writeVarint32(bb, 26);
      let nested = popByteBuffer();
      _encodePromptAction(value, nested);
      writeVarint32(bb, nested.limit);
      writeByteBuffer(bb, nested);
      pushByteBuffer(nested);
    }
  }

  // optional string rja_object_target_id = 4;
  let $rja_object_target_id = message.rja_object_target_id;
  if ($rja_object_target_id !== undefined) {
    writeVarint32(bb, 34);
    writeString(bb, $rja_object_target_id);
  }
}

export function decodeRjaPromptCommand(binary) {
  return _decodeRjaPromptCommand(wrapByteBuffer(binary));
}

function _decodeRjaPromptCommand(bb) {
  let message = {};

  end_of_message: while (!isAtEnd(bb)) {
    let tag = readVarint32(bb);

    switch (tag >>> 3) {
      case 0:
        break end_of_message;

      // optional Header header = 1;
      case 1: {
        let limit = pushTemporaryLength(bb);
        message.header = _decodeHeader(bb);
        bb.limit = limit;
        break;
      }

      // optional int32 child_current_level = 2;
      case 2: {
        message.child_current_level = readVarint32(bb);
        break;
      }

      // repeated PromptAction actions = 3;
      case 3: {
        let limit = pushTemporaryLength(bb);
        let values = message.actions || (message.actions = []);
        values.push(_decodePromptAction(bb));
        bb.limit = limit;
        break;
      }

      // optional string rja_object_target_id = 4;
      case 4: {
        message.rja_object_target_id = readString(bb, readVarint32(bb));
        break;
      }

      default:
        skipUnknownField(bb, tag & 7);
    }
  }

  return message;
}

export function encodeRjaChildResponseRecord(message) {
  let bb = popByteBuffer();
  _encodeRjaChildResponseRecord(message, bb);
  return toUint8Array(bb);
}

function _encodeRjaChildResponseRecord(message, bb) {
  // optional Header header = 1;
  let $header = message.header;
  if ($header !== undefined) {
    writeVarint32(bb, 10);
    let nested = popByteBuffer();
    _encodeHeader($header, nested);
    writeVarint32(bb, nested.limit);
    writeByteBuffer(bb, nested);
    pushByteBuffer(nested);
  }

  // optional string responded_to_prompt_message_id = 2;
  let $responded_to_prompt_message_id = message.responded_to_prompt_message_id;
  if ($responded_to_prompt_message_id !== undefined) {
    writeVarint32(bb, 18);
    writeString(bb, $responded_to_prompt_message_id);
  }

  // optional ChildResponseType response_type = 3;
  let $response_type = message.response_type;
  if ($response_type !== undefined) {
    writeVarint32(bb, 24);
    writeVarint32(bb, encodeChildResponseType[$response_type]);
  }

  // optional int64 response_time_ms_from_prompt_end = 4;
  let $response_time_ms_from_prompt_end = message.response_time_ms_from_prompt_end;
  if ($response_time_ms_from_prompt_end !== undefined) {
    writeVarint32(bb, 32);
    writeVarint64(bb, $response_time_ms_from_prompt_end);
  }

  // optional string operator_notes = 5;
  let $operator_notes = message.operator_notes;
  if ($operator_notes !== undefined) {
    writeVarint32(bb, 42);
    writeString(bb, $operator_notes);
  }
}

export function decodeRjaChildResponseRecord(binary) {
  return _decodeRjaChildResponseRecord(wrapByteBuffer(binary));
}

function _decodeRjaChildResponseRecord(bb) {
  let message = {};

  end_of_message: while (!isAtEnd(bb)) {
    let tag = readVarint32(bb);

    switch (tag >>> 3) {
      case 0:
        break end_of_message;

      // optional Header header = 1;
      case 1: {
        let limit = pushTemporaryLength(bb);
        message.header = _decodeHeader(bb);
        bb.limit = limit;
        break;
      }

      // optional string responded_to_prompt_message_id = 2;
      case 2: {
        message.responded_to_prompt_message_id = readString(bb, readVarint32(bb));
        break;
      }

      // optional ChildResponseType response_type = 3;
      case 3: {
        message.response_type = decodeChildResponseType[readVarint32(bb)];
        break;
      }

      // optional int64 response_time_ms_from_prompt_end = 4;
      case 4: {
        message.response_time_ms_from_prompt_end = readVarint64(bb, /* unsigned */ false);
        break;
      }

      // optional string operator_notes = 5;
      case 5: {
        message.operator_notes = readString(bb, readVarint32(bb));
        break;
      }

      default:
        skipUnknownField(bb, tag & 7);
    }
  }

  return message;
}

export function encodeRobotAnimationParams(message) {
  let bb = popByteBuffer();
  _encodeRobotAnimationParams(message, bb);
  return toUint8Array(bb);
}

function _encodeRobotAnimationParams(message, bb) {
  // optional RobotAnimationId animation_id = 1;
  let $animation_id = message.animation_id;
  if ($animation_id !== undefined) {
    writeVarint32(bb, 8);
    writeVarint32(bb, encodeRobotAnimationId[$animation_id]);
  }
}

export function decodeRobotAnimationParams(binary) {
  return _decodeRobotAnimationParams(wrapByteBuffer(binary));
}

function _decodeRobotAnimationParams(bb) {
  let message = {};

  end_of_message: while (!isAtEnd(bb)) {
    let tag = readVarint32(bb);

    switch (tag >>> 3) {
      case 0:
        break end_of_message;

      // optional RobotAnimationId animation_id = 1;
      case 1: {
        message.animation_id = decodeRobotAnimationId[readVarint32(bb)];
        break;
      }

      default:
        skipUnknownField(bb, tag & 7);
    }
  }

  return message;
}

export function encodePlayFeedbackSoundParams(message) {
  let bb = popByteBuffer();
  _encodePlayFeedbackSoundParams(message, bb);
  return toUint8Array(bb);
}

function _encodePlayFeedbackSoundParams(message, bb) {
  // optional string sound_id_or_filename = 1;
  let $sound_id_or_filename = message.sound_id_or_filename;
  if ($sound_id_or_filename !== undefined) {
    writeVarint32(bb, 10);
    writeString(bb, $sound_id_or_filename);
  }

  // optional float volume_level = 2;
  let $volume_level = message.volume_level;
  if ($volume_level !== undefined) {
    writeVarint32(bb, 21);
    writeFloat(bb, $volume_level);
  }
}

export function decodePlayFeedbackSoundParams(binary) {
  return _decodePlayFeedbackSoundParams(wrapByteBuffer(binary));
}

function _decodePlayFeedbackSoundParams(bb) {
  let message = {};

  end_of_message: while (!isAtEnd(bb)) {
    let tag = readVarint32(bb);

    switch (tag >>> 3) {
      case 0:
        break end_of_message;

      // optional string sound_id_or_filename = 1;
      case 1: {
        message.sound_id_or_filename = readString(bb, readVarint32(bb));
        break;
      }

      // optional float volume_level = 2;
      case 2: {
        message.volume_level = readFloat(bb);
        break;
      }

      default:
        skipUnknownField(bb, tag & 7);
    }
  }

  return message;
}

export function encodeDisplayFeedbackVisualParams(message) {
  let bb = popByteBuffer();
  _encodeDisplayFeedbackVisualParams(message, bb);
  return toUint8Array(bb);
}

function _encodeDisplayFeedbackVisualParams(message, bb) {
  // optional string visual_id_or_filename = 1;
  let $visual_id_or_filename = message.visual_id_or_filename;
  if ($visual_id_or_filename !== undefined) {
    writeVarint32(bb, 10);
    writeString(bb, $visual_id_or_filename);
  }
}

export function decodeDisplayFeedbackVisualParams(binary) {
  return _decodeDisplayFeedbackVisualParams(wrapByteBuffer(binary));
}

function _decodeDisplayFeedbackVisualParams(bb) {
  let message = {};

  end_of_message: while (!isAtEnd(bb)) {
    let tag = readVarint32(bb);

    switch (tag >>> 3) {
      case 0:
        break end_of_message;

      // optional string visual_id_or_filename = 1;
      case 1: {
        message.visual_id_or_filename = readString(bb, readVarint32(bb));
        break;
      }

      default:
        skipUnknownField(bb, tag & 7);
    }
  }

  return message;
}

export function encodeEngagePersonalizedContentParams(message) {
  let bb = popByteBuffer();
  _encodeEngagePersonalizedContentParams(message, bb);
  return toUint8Array(bb);
}

function _encodeEngagePersonalizedContentParams(message, bb) {
  // optional PersonalizedContentType content_type = 1;
  let $content_type = message.content_type;
  if ($content_type !== undefined) {
    writeVarint32(bb, 8);
    writeVarint32(bb, encodePersonalizedContentType[$content_type]);
  }

  // optional string preference_tag = 2;
  let $preference_tag = message.preference_tag;
  if ($preference_tag !== undefined) {
    writeVarint32(bb, 18);
    writeString(bb, $preference_tag);
  }
}

export function decodeEngagePersonalizedContentParams(binary) {
  return _decodeEngagePersonalizedContentParams(wrapByteBuffer(binary));
}

function _decodeEngagePersonalizedContentParams(bb) {
  let message = {};

  end_of_message: while (!isAtEnd(bb)) {
    let tag = readVarint32(bb);

    switch (tag >>> 3) {
      case 0:
        break end_of_message;

      // optional PersonalizedContentType content_type = 1;
      case 1: {
        message.content_type = decodePersonalizedContentType[readVarint32(bb)];
        break;
      }

      // optional string preference_tag = 2;
      case 2: {
        message.preference_tag = readString(bb, readVarint32(bb));
        break;
      }

      default:
        skipUnknownField(bb, tag & 7);
    }
  }

  return message;
}

export function encodeFeedbackAction(message) {
  let bb = popByteBuffer();
  _encodeFeedbackAction(message, bb);
  return toUint8Array(bb);
}

function _encodeFeedbackAction(message, bb) {
  // optional string action_id = 1;
  let $action_id = message.action_id;
  if ($action_id !== undefined) {
    writeVarint32(bb, 10);
    writeString(bb, $action_id);
  }

  // optional FeedbackActionType type = 2;
  let $type = message.type;
  if ($type !== undefined) {
    writeVarint32(bb, 16);
    writeVarint32(bb, encodeFeedbackActionType[$type]);
  }

  // optional RobotAnimationParams animation_params = 3;
  let $animation_params = message.animation_params;
  if ($animation_params !== undefined) {
    writeVarint32(bb, 26);
    let nested = popByteBuffer();
    _encodeRobotAnimationParams($animation_params, nested);
    writeVarint32(bb, nested.limit);
    writeByteBuffer(bb, nested);
    pushByteBuffer(nested);
  }

  // optional PlayFeedbackSoundParams sound_params = 4;
  let $sound_params = message.sound_params;
  if ($sound_params !== undefined) {
    writeVarint32(bb, 34);
    let nested = popByteBuffer();
    _encodePlayFeedbackSoundParams($sound_params, nested);
    writeVarint32(bb, nested.limit);
    writeByteBuffer(bb, nested);
    pushByteBuffer(nested);
  }

  // optional DisplayFeedbackVisualParams visual_params = 5;
  let $visual_params = message.visual_params;
  if ($visual_params !== undefined) {
    writeVarint32(bb, 42);
    let nested = popByteBuffer();
    _encodeDisplayFeedbackVisualParams($visual_params, nested);
    writeVarint32(bb, nested.limit);
    writeByteBuffer(bb, nested);
    pushByteBuffer(nested);
  }

  // optional EngagePersonalizedContentParams personalized_params = 6;
  let $personalized_params = message.personalized_params;
  if ($personalized_params !== undefined) {
    writeVarint32(bb, 50);
    let nested = popByteBuffer();
    _encodeEngagePersonalizedContentParams($personalized_params, nested);
    writeVarint32(bb, nested.limit);
    writeByteBuffer(bb, nested);
    pushByteBuffer(nested);
  }

  // optional int32 start_delay_ms = 7;
  let $start_delay_ms = message.start_delay_ms;
  if ($start_delay_ms !== undefined) {
    writeVarint32(bb, 56);
    writeVarint64(bb, intToLong($start_delay_ms));
  }

  // optional int32 estimated_duration_ms = 8;
  let $estimated_duration_ms = message.estimated_duration_ms;
  if ($estimated_duration_ms !== undefined) {
    writeVarint32(bb, 64);
    writeVarint64(bb, intToLong($estimated_duration_ms));
  }
}

export function decodeFeedbackAction(binary) {
  return _decodeFeedbackAction(wrapByteBuffer(binary));
}

function _decodeFeedbackAction(bb) {
  let message = {};

  end_of_message: while (!isAtEnd(bb)) {
    let tag = readVarint32(bb);

    switch (tag >>> 3) {
      case 0:
        break end_of_message;

      // optional string action_id = 1;
      case 1: {
        message.action_id = readString(bb, readVarint32(bb));
        break;
      }

      // optional FeedbackActionType type = 2;
      case 2: {
        message.type = decodeFeedbackActionType[readVarint32(bb)];
        break;
      }

      // optional RobotAnimationParams animation_params = 3;
      case 3: {
        let limit = pushTemporaryLength(bb);
        message.animation_params = _decodeRobotAnimationParams(bb);
        bb.limit = limit;
        break;
      }

      // optional PlayFeedbackSoundParams sound_params = 4;
      case 4: {
        let limit = pushTemporaryLength(bb);
        message.sound_params = _decodePlayFeedbackSoundParams(bb);
        bb.limit = limit;
        break;
      }

      // optional DisplayFeedbackVisualParams visual_params = 5;
      case 5: {
        let limit = pushTemporaryLength(bb);
        message.visual_params = _decodeDisplayFeedbackVisualParams(bb);
        bb.limit = limit;
        break;
      }

      // optional EngagePersonalizedContentParams personalized_params = 6;
      case 6: {
        let limit = pushTemporaryLength(bb);
        message.personalized_params = _decodeEngagePersonalizedContentParams(bb);
        bb.limit = limit;
        break;
      }

      // optional int32 start_delay_ms = 7;
      case 7: {
        message.start_delay_ms = readVarint32(bb);
        break;
      }

      // optional int32 estimated_duration_ms = 8;
      case 8: {
        message.estimated_duration_ms = readVarint32(bb);
        break;
      }

      default:
        skipUnknownField(bb, tag & 7);
    }
  }

  return message;
}

export function encodeRjaFeedbackCommand(message) {
  let bb = popByteBuffer();
  _encodeRjaFeedbackCommand(message, bb);
  return toUint8Array(bb);
}

function _encodeRjaFeedbackCommand(message, bb) {
  // optional Header header = 1;
  let $header = message.header;
  if ($header !== undefined) {
    writeVarint32(bb, 10);
    let nested = popByteBuffer();
    _encodeHeader($header, nested);
    writeVarint32(bb, nested.limit);
    writeByteBuffer(bb, nested);
    pushByteBuffer(nested);
  }

  // optional string for_prompt_message_id = 2;
  let $for_prompt_message_id = message.for_prompt_message_id;
  if ($for_prompt_message_id !== undefined) {
    writeVarint32(bb, 18);
    writeString(bb, $for_prompt_message_id);
  }

  // optional ChildResponseType child_response_that_triggered_feedback = 3;
  let $child_response_that_triggered_feedback = message.child_response_that_triggered_feedback;
  if ($child_response_that_triggered_feedback !== undefined) {
    writeVarint32(bb, 24);
    writeVarint32(bb, encodeChildResponseType[$child_response_that_triggered_feedback]);
  }

  // repeated FeedbackAction actions = 4;
  let array$actions = message.actions;
  if (array$actions !== undefined) {
    for (let value of array$actions) {
      writeVarint32(bb, 34);
      let nested = popByteBuffer();
      _encodeFeedbackAction(value, nested);
      writeVarint32(bb, nested.limit);
      writeByteBuffer(bb, nested);
      pushByteBuffer(nested);
    }
  }
}

export function decodeRjaFeedbackCommand(binary) {
  return _decodeRjaFeedbackCommand(wrapByteBuffer(binary));
}

function _decodeRjaFeedbackCommand(bb) {
  let message = {};

  end_of_message: while (!isAtEnd(bb)) {
    let tag = readVarint32(bb);

    switch (tag >>> 3) {
      case 0:
        break end_of_message;

      // optional Header header = 1;
      case 1: {
        let limit = pushTemporaryLength(bb);
        message.header = _decodeHeader(bb);
        bb.limit = limit;
        break;
      }

      // optional string for_prompt_message_id = 2;
      case 2: {
        message.for_prompt_message_id = readString(bb, readVarint32(bb));
        break;
      }

      // optional ChildResponseType child_response_that_triggered_feedback = 3;
      case 3: {
        message.child_response_that_triggered_feedback = decodeChildResponseType[readVarint32(bb)];
        break;
      }

      // repeated FeedbackAction actions = 4;
      case 4: {
        let limit = pushTemporaryLength(bb);
        let values = message.actions || (message.actions = []);
        values.push(_decodeFeedbackAction(bb));
        bb.limit = limit;
        break;
      }

      default:
        skipUnknownField(bb, tag & 7);
    }
  }

  return message;
}

export function encodeChildProfile(message) {
  let bb = popByteBuffer();
  _encodeChildProfile(message, bb);
  return toUint8Array(bb);
}

function _encodeChildProfile(message, bb) {
  // optional string child_id = 1;
  let $child_id = message.child_id;
  if ($child_id !== undefined) {
    writeVarint32(bb, 10);
    writeString(bb, $child_id);
  }

  // optional int32 current_rja_level = 2;
  let $current_rja_level = message.current_rja_level;
  if ($current_rja_level !== undefined) {
    writeVarint32(bb, 16);
    writeVarint64(bb, intToLong($current_rja_level));
  }

  // repeated string preference_tags = 3;
  let array$preference_tags = message.preference_tags;
  if (array$preference_tags !== undefined) {
    for (let value of array$preference_tags) {
      writeVarint32(bb, 26);
      writeString(bb, value);
    }
  }
}

export function decodeChildProfile(binary) {
  return _decodeChildProfile(wrapByteBuffer(binary));
}

function _decodeChildProfile(bb) {
  let message = {};

  end_of_message: while (!isAtEnd(bb)) {
    let tag = readVarint32(bb);

    switch (tag >>> 3) {
      case 0:
        break end_of_message;

      // optional string child_id = 1;
      case 1: {
        message.child_id = readString(bb, readVarint32(bb));
        break;
      }

      // optional int32 current_rja_level = 2;
      case 2: {
        message.current_rja_level = readVarint32(bb);
        break;
      }

      // repeated string preference_tags = 3;
      case 3: {
        let values = message.preference_tags || (message.preference_tags = []);
        values.push(readString(bb, readVarint32(bb)));
        break;
      }

      default:
        skipUnknownField(bb, tag & 7);
    }
  }

  return message;
}

export function encodeSetCurrentChildProfileCommand(message) {
  let bb = popByteBuffer();
  _encodeSetCurrentChildProfileCommand(message, bb);
  return toUint8Array(bb);
}

function _encodeSetCurrentChildProfileCommand(message, bb) {
  // optional Header header = 1;
  let $header = message.header;
  if ($header !== undefined) {
    writeVarint32(bb, 10);
    let nested = popByteBuffer();
    _encodeHeader($header, nested);
    writeVarint32(bb, nested.limit);
    writeByteBuffer(bb, nested);
    pushByteBuffer(nested);
  }

  // optional ChildProfile profile = 2;
  let $profile = message.profile;
  if ($profile !== undefined) {
    writeVarint32(bb, 18);
    let nested = popByteBuffer();
    _encodeChildProfile($profile, nested);
    writeVarint32(bb, nested.limit);
    writeByteBuffer(bb, nested);
    pushByteBuffer(nested);
  }
}

export function decodeSetCurrentChildProfileCommand(binary) {
  return _decodeSetCurrentChildProfileCommand(wrapByteBuffer(binary));
}

function _decodeSetCurrentChildProfileCommand(bb) {
  let message = {};

  end_of_message: while (!isAtEnd(bb)) {
    let tag = readVarint32(bb);

    switch (tag >>> 3) {
      case 0:
        break end_of_message;

      // optional Header header = 1;
      case 1: {
        let limit = pushTemporaryLength(bb);
        message.header = _decodeHeader(bb);
        bb.limit = limit;
        break;
      }

      // optional ChildProfile profile = 2;
      case 2: {
        let limit = pushTemporaryLength(bb);
        message.profile = _decodeChildProfile(bb);
        bb.limit = limit;
        break;
      }

      default:
        skipUnknownField(bb, tag & 7);
    }
  }

  return message;
}

export function encodeRjaPointDefinition(message) {
  let bb = popByteBuffer();
  _encodeRjaPointDefinition(message, bb);
  return toUint8Array(bb);
}

function _encodeRjaPointDefinition(message, bb) {
  // optional string point_id = 1;
  let $point_id = message.point_id;
  if ($point_id !== undefined) {
    writeVarint32(bb, 10);
    writeString(bb, $point_id);
  }

  // optional Pose world_pose = 2;
  let $world_pose = message.world_pose;
  if ($world_pose !== undefined) {
    writeVarint32(bb, 18);
    let nested = popByteBuffer();
    _encodePose($world_pose, nested);
    writeVarint32(bb, nested.limit);
    writeByteBuffer(bb, nested);
    pushByteBuffer(nested);
  }

  // optional string description = 3;
  let $description = message.description;
  if ($description !== undefined) {
    writeVarint32(bb, 26);
    writeString(bb, $description);
  }
}

export function decodeRjaPointDefinition(binary) {
  return _decodeRjaPointDefinition(wrapByteBuffer(binary));
}

function _decodeRjaPointDefinition(bb) {
  let message = {};

  end_of_message: while (!isAtEnd(bb)) {
    let tag = readVarint32(bb);

    switch (tag >>> 3) {
      case 0:
        break end_of_message;

      // optional string point_id = 1;
      case 1: {
        message.point_id = readString(bb, readVarint32(bb));
        break;
      }

      // optional Pose world_pose = 2;
      case 2: {
        let limit = pushTemporaryLength(bb);
        message.world_pose = _decodePose(bb);
        bb.limit = limit;
        break;
      }

      // optional string description = 3;
      case 3: {
        message.description = readString(bb, readVarint32(bb));
        break;
      }

      default:
        skipUnknownField(bb, tag & 7);
    }
  }

  return message;
}

export function encodeDefineRjaPointsCommand(message) {
  let bb = popByteBuffer();
  _encodeDefineRjaPointsCommand(message, bb);
  return toUint8Array(bb);
}

function _encodeDefineRjaPointsCommand(message, bb) {
  // optional Header header = 1;
  let $header = message.header;
  if ($header !== undefined) {
    writeVarint32(bb, 10);
    let nested = popByteBuffer();
    _encodeHeader($header, nested);
    writeVarint32(bb, nested.limit);
    writeByteBuffer(bb, nested);
    pushByteBuffer(nested);
  }

  // repeated RjaPointDefinition points = 2;
  let array$points = message.points;
  if (array$points !== undefined) {
    for (let value of array$points) {
      writeVarint32(bb, 18);
      let nested = popByteBuffer();
      _encodeRjaPointDefinition(value, nested);
      writeVarint32(bb, nested.limit);
      writeByteBuffer(bb, nested);
      pushByteBuffer(nested);
    }
  }

  // optional bool replace_all = 3;
  let $replace_all = message.replace_all;
  if ($replace_all !== undefined) {
    writeVarint32(bb, 24);
    writeByte(bb, $replace_all ? 1 : 0);
  }
}

export function decodeDefineRjaPointsCommand(binary) {
  return _decodeDefineRjaPointsCommand(wrapByteBuffer(binary));
}

function _decodeDefineRjaPointsCommand(bb) {
  let message = {};

  end_of_message: while (!isAtEnd(bb)) {
    let tag = readVarint32(bb);

    switch (tag >>> 3) {
      case 0:
        break end_of_message;

      // optional Header header = 1;
      case 1: {
        let limit = pushTemporaryLength(bb);
        message.header = _decodeHeader(bb);
        bb.limit = limit;
        break;
      }

      // repeated RjaPointDefinition points = 2;
      case 2: {
        let limit = pushTemporaryLength(bb);
        let values = message.points || (message.points = []);
        values.push(_decodeRjaPointDefinition(bb));
        bb.limit = limit;
        break;
      }

      // optional bool replace_all = 3;
      case 3: {
        message.replace_all = !!readByte(bb);
        break;
      }

      default:
        skipUnknownField(bb, tag & 7);
    }
  }

  return message;
}

export function encodeVideoStreamPacket(message) {
  let bb = popByteBuffer();
  _encodeVideoStreamPacket(message, bb);
  return toUint8Array(bb);
}

function _encodeVideoStreamPacket(message, bb) {
  // optional Header header = 1;
  let $header = message.header;
  if ($header !== undefined) {
    writeVarint32(bb, 10);
    let nested = popByteBuffer();
    _encodeHeader($header, nested);
    writeVarint32(bb, nested.limit);
    writeByteBuffer(bb, nested);
    pushByteBuffer(nested);
  }

  // optional uint32 frame_id = 2;
  let $frame_id = message.frame_id;
  if ($frame_id !== undefined) {
    writeVarint32(bb, 16);
    writeVarint32(bb, $frame_id);
  }

  // optional bytes frame_data = 3;
  let $frame_data = message.frame_data;
  if ($frame_data !== undefined) {
    writeVarint32(bb, 26);
    writeVarint32(bb, $frame_data.length), writeBytes(bb, $frame_data);
  }

  // optional string encoding_type = 4;
  let $encoding_type = message.encoding_type;
  if ($encoding_type !== undefined) {
    writeVarint32(bb, 34);
    writeString(bb, $encoding_type);
  }

  // optional uint32 width = 5;
  let $width = message.width;
  if ($width !== undefined) {
    writeVarint32(bb, 40);
    writeVarint32(bb, $width);
  }

  // optional uint32 height = 6;
  let $height = message.height;
  if ($height !== undefined) {
    writeVarint32(bb, 48);
    writeVarint32(bb, $height);
  }

  // optional bool is_key_frame = 7;
  let $is_key_frame = message.is_key_frame;
  if ($is_key_frame !== undefined) {
    writeVarint32(bb, 56);
    writeByte(bb, $is_key_frame ? 1 : 0);
  }
}

export function decodeVideoStreamPacket(binary) {
  return _decodeVideoStreamPacket(wrapByteBuffer(binary));
}

function _decodeVideoStreamPacket(bb) {
  let message = {};

  end_of_message: while (!isAtEnd(bb)) {
    let tag = readVarint32(bb);

    switch (tag >>> 3) {
      case 0:
        break end_of_message;

      // optional Header header = 1;
      case 1: {
        let limit = pushTemporaryLength(bb);
        message.header = _decodeHeader(bb);
        bb.limit = limit;
        break;
      }

      // optional uint32 frame_id = 2;
      case 2: {
        message.frame_id = readVarint32(bb) >>> 0;
        break;
      }

      // optional bytes frame_data = 3;
      case 3: {
        message.frame_data = readBytes(bb, readVarint32(bb));
        break;
      }

      // optional string encoding_type = 4;
      case 4: {
        message.encoding_type = readString(bb, readVarint32(bb));
        break;
      }

      // optional uint32 width = 5;
      case 5: {
        message.width = readVarint32(bb) >>> 0;
        break;
      }

      // optional uint32 height = 6;
      case 6: {
        message.height = readVarint32(bb) >>> 0;
        break;
      }

      // optional bool is_key_frame = 7;
      case 7: {
        message.is_key_frame = !!readByte(bb);
        break;
      }

      default:
        skipUnknownField(bb, tag & 7);
    }
  }

  return message;
}

export function encodeRobotSystemEvent(message) {
  let bb = popByteBuffer();
  _encodeRobotSystemEvent(message, bb);
  return toUint8Array(bb);
}

function _encodeRobotSystemEvent(message, bb) {
  // optional Header header = 1;
  let $header = message.header;
  if ($header !== undefined) {
    writeVarint32(bb, 10);
    let nested = popByteBuffer();
    _encodeHeader($header, nested);
    writeVarint32(bb, nested.limit);
    writeByteBuffer(bb, nested);
    pushByteBuffer(nested);
  }

  // optional SystemEventSeverity severity = 2;
  let $severity = message.severity;
  if ($severity !== undefined) {
    writeVarint32(bb, 16);
    writeVarint32(bb, encodeSystemEventSeverity[$severity]);
  }

  // optional string event_code = 3;
  let $event_code = message.event_code;
  if ($event_code !== undefined) {
    writeVarint32(bb, 26);
    writeString(bb, $event_code);
  }

  // optional string description = 4;
  let $description = message.description;
  if ($description !== undefined) {
    writeVarint32(bb, 34);
    writeString(bb, $description);
  }

  // optional map<string, string> additional_data = 5;
  let map$additional_data = message.additional_data;
  if (map$additional_data !== undefined) {
    for (let key in map$additional_data) {
      let nested = popByteBuffer();
      let value = map$additional_data[key];
      writeVarint32(nested, 10);
      writeString(nested, key);
      writeVarint32(nested, 18);
      writeString(nested, value);
      writeVarint32(bb, 42);
      writeVarint32(bb, nested.offset);
      writeByteBuffer(bb, nested);
      pushByteBuffer(nested);
    }
  }
}

export function decodeRobotSystemEvent(binary) {
  return _decodeRobotSystemEvent(wrapByteBuffer(binary));
}

function _decodeRobotSystemEvent(bb) {
  let message = {};

  end_of_message: while (!isAtEnd(bb)) {
    let tag = readVarint32(bb);

    switch (tag >>> 3) {
      case 0:
        break end_of_message;

      // optional Header header = 1;
      case 1: {
        let limit = pushTemporaryLength(bb);
        message.header = _decodeHeader(bb);
        bb.limit = limit;
        break;
      }

      // optional SystemEventSeverity severity = 2;
      case 2: {
        message.severity = decodeSystemEventSeverity[readVarint32(bb)];
        break;
      }

      // optional string event_code = 3;
      case 3: {
        message.event_code = readString(bb, readVarint32(bb));
        break;
      }

      // optional string description = 4;
      case 4: {
        message.description = readString(bb, readVarint32(bb));
        break;
      }

      // optional map<string, string> additional_data = 5;
      case 5: {
        let values = message.additional_data || (message.additional_data = {});
        let outerLimit = pushTemporaryLength(bb);
        let key;
        let value;
        end_of_entry: while (!isAtEnd(bb)) {
          let tag = readVarint32(bb);
          switch (tag >>> 3) {
            case 0:
              break end_of_entry;
            case 1: {
              key = readString(bb, readVarint32(bb));
              break;
            }
            case 2: {
              value = readString(bb, readVarint32(bb));
              break;
            }
            default:
              skipUnknownField(bb, tag & 7);
          }
        }
        if (key === undefined || value === undefined)
          throw new Error("Invalid data for map: additional_data");
        values[key] = value;
        bb.limit = outerLimit;
        break;
      }

      default:
        skipUnknownField(bb, tag & 7);
    }
  }

  return message;
}

export function encodeCommandAcknowledgement(message) {
  let bb = popByteBuffer();
  _encodeCommandAcknowledgement(message, bb);
  return toUint8Array(bb);
}

function _encodeCommandAcknowledgement(message, bb) {
  // optional Header header = 1;
  let $header = message.header;
  if ($header !== undefined) {
    writeVarint32(bb, 10);
    let nested = popByteBuffer();
    _encodeHeader($header, nested);
    writeVarint32(bb, nested.limit);
    writeByteBuffer(bb, nested);
    pushByteBuffer(nested);
  }

  // optional string acknowledged_message_id = 2;
  let $acknowledged_message_id = message.acknowledged_message_id;
  if ($acknowledged_message_id !== undefined) {
    writeVarint32(bb, 18);
    writeString(bb, $acknowledged_message_id);
  }

  // optional bool success = 3;
  let $success = message.success;
  if ($success !== undefined) {
    writeVarint32(bb, 24);
    writeByte(bb, $success ? 1 : 0);
  }

  // optional string details = 4;
  let $details = message.details;
  if ($details !== undefined) {
    writeVarint32(bb, 34);
    writeString(bb, $details);
  }
}

export function decodeCommandAcknowledgement(binary) {
  return _decodeCommandAcknowledgement(wrapByteBuffer(binary));
}

function _decodeCommandAcknowledgement(bb) {
  let message = {};

  end_of_message: while (!isAtEnd(bb)) {
    let tag = readVarint32(bb);

    switch (tag >>> 3) {
      case 0:
        break end_of_message;

      // optional Header header = 1;
      case 1: {
        let limit = pushTemporaryLength(bb);
        message.header = _decodeHeader(bb);
        bb.limit = limit;
        break;
      }

      // optional string acknowledged_message_id = 2;
      case 2: {
        message.acknowledged_message_id = readString(bb, readVarint32(bb));
        break;
      }

      // optional bool success = 3;
      case 3: {
        message.success = !!readByte(bb);
        break;
      }

      // optional string details = 4;
      case 4: {
        message.details = readString(bb, readVarint32(bb));
        break;
      }

      default:
        skipUnknownField(bb, tag & 7);
    }
  }

  return message;
}

export function encodeSystemActionCommand(message) {
  let bb = popByteBuffer();
  _encodeSystemActionCommand(message, bb);
  return toUint8Array(bb);
}

function _encodeSystemActionCommand(message, bb) {
  // optional Header header = 1;
  let $header = message.header;
  if ($header !== undefined) {
    writeVarint32(bb, 10);
    let nested = popByteBuffer();
    _encodeHeader($header, nested);
    writeVarint32(bb, nested.limit);
    writeByteBuffer(bb, nested);
    pushByteBuffer(nested);
  }

  // optional ActionType action = 2;
  let $action = message.action;
  if ($action !== undefined) {
    writeVarint32(bb, 18);
    let nested = popByteBuffer();
    _encodeActionType($action, nested);
    writeVarint32(bb, nested.limit);
    writeByteBuffer(bb, nested);
    pushByteBuffer(nested);
  }
}

export function decodeSystemActionCommand(binary) {
  return _decodeSystemActionCommand(wrapByteBuffer(binary));
}

function _decodeSystemActionCommand(bb) {
  let message = {};

  end_of_message: while (!isAtEnd(bb)) {
    let tag = readVarint32(bb);

    switch (tag >>> 3) {
      case 0:
        break end_of_message;

      // optional Header header = 1;
      case 1: {
        let limit = pushTemporaryLength(bb);
        message.header = _decodeHeader(bb);
        bb.limit = limit;
        break;
      }

      // optional ActionType action = 2;
      case 2: {
        let limit = pushTemporaryLength(bb);
        message.action = _decodeActionType(bb);
        bb.limit = limit;
        break;
      }

      default:
        skipUnknownField(bb, tag & 7);
    }
  }

  return message;
}

function pushTemporaryLength(bb) {
  let length = readVarint32(bb);
  let limit = bb.limit;
  bb.limit = bb.offset + length;
  return limit;
}

function skipUnknownField(bb, type) {
  switch (type) {
    case 0: while (readByte(bb) & 0x80) { } break;
    case 2: skip(bb, readVarint32(bb)); break;
    case 5: skip(bb, 4); break;
    case 1: skip(bb, 8); break;
    default: throw new Error("Unimplemented type: " + type);
  }
}

function stringToLong(value) {
  return {
    low: value.charCodeAt(0) | (value.charCodeAt(1) << 16),
    high: value.charCodeAt(2) | (value.charCodeAt(3) << 16),
    unsigned: false,
  };
}

function longToString(value) {
  let low = value.low;
  let high = value.high;
  return String.fromCharCode(
    low & 0xFFFF,
    low >>> 16,
    high & 0xFFFF,
    high >>> 16);
}

// The code below was modified from https://github.com/protobufjs/bytebuffer.js
// which is under the Apache License 2.0.

let f32 = new Float32Array(1);
let f32_u8 = new Uint8Array(f32.buffer);

let f64 = new Float64Array(1);
let f64_u8 = new Uint8Array(f64.buffer);

function intToLong(value) {
  value |= 0;
  return {
    low: value,
    high: value >> 31,
    unsigned: value >= 0,
  };
}

let bbStack = [];

function popByteBuffer() {
  const bb = bbStack.pop();
  if (!bb) return { bytes: new Uint8Array(64), offset: 0, limit: 0 };
  bb.offset = bb.limit = 0;
  return bb;
}

function pushByteBuffer(bb) {
  bbStack.push(bb);
}

function wrapByteBuffer(bytes) {
  return { bytes, offset: 0, limit: bytes.length };
}

function toUint8Array(bb) {
  let bytes = bb.bytes;
  let limit = bb.limit;
  return bytes.length === limit ? bytes : bytes.subarray(0, limit);
}

function skip(bb, offset) {
  if (bb.offset + offset > bb.limit) {
    throw new Error('Skip past limit');
  }
  bb.offset += offset;
}

function isAtEnd(bb) {
  return bb.offset >= bb.limit;
}

function grow(bb, count) {
  let bytes = bb.bytes;
  let offset = bb.offset;
  let limit = bb.limit;
  let finalOffset = offset + count;
  if (finalOffset > bytes.length) {
    let newBytes = new Uint8Array(finalOffset * 2);
    newBytes.set(bytes);
    bb.bytes = newBytes;
  }
  bb.offset = finalOffset;
  if (finalOffset > limit) {
    bb.limit = finalOffset;
  }
  return offset;
}

function advance(bb, count) {
  let offset = bb.offset;
  if (offset + count > bb.limit) {
    throw new Error('Read past limit');
  }
  bb.offset += count;
  return offset;
}

function readBytes(bb, count) {
  let offset = advance(bb, count);
  return bb.bytes.subarray(offset, offset + count);
}

function writeBytes(bb, buffer) {
  let offset = grow(bb, buffer.length);
  bb.bytes.set(buffer, offset);
}

function readString(bb, count) {
  // Sadly a hand-coded UTF8 decoder is much faster than subarray+TextDecoder in V8
  let offset = advance(bb, count);
  let fromCharCode = String.fromCharCode;
  let bytes = bb.bytes;
  let invalid = '\uFFFD';
  let text = '';

  for (let i = 0; i < count; i++) {
    let c1 = bytes[i + offset], c2, c3, c4, c;

    // 1 byte
    if ((c1 & 0x80) === 0) {
      text += fromCharCode(c1);
    }

    // 2 bytes
    else if ((c1 & 0xE0) === 0xC0) {
      if (i + 1 >= count) text += invalid;
      else {
        c2 = bytes[i + offset + 1];
        if ((c2 & 0xC0) !== 0x80) text += invalid;
        else {
          c = ((c1 & 0x1F) << 6) | (c2 & 0x3F);
          if (c < 0x80) text += invalid;
          else {
            text += fromCharCode(c);
            i++;
          }
        }
      }
    }

    // 3 bytes
    else if ((c1 & 0xF0) == 0xE0) {
      if (i + 2 >= count) text += invalid;
      else {
        c2 = bytes[i + offset + 1];
        c3 = bytes[i + offset + 2];
        if (((c2 | (c3 << 8)) & 0xC0C0) !== 0x8080) text += invalid;
        else {
          c = ((c1 & 0x0F) << 12) | ((c2 & 0x3F) << 6) | (c3 & 0x3F);
          if (c < 0x0800 || (c >= 0xD800 && c <= 0xDFFF)) text += invalid;
          else {
            text += fromCharCode(c);
            i += 2;
          }
        }
      }
    }

    // 4 bytes
    else if ((c1 & 0xF8) == 0xF0) {
      if (i + 3 >= count) text += invalid;
      else {
        c2 = bytes[i + offset + 1];
        c3 = bytes[i + offset + 2];
        c4 = bytes[i + offset + 3];
        if (((c2 | (c3 << 8) | (c4 << 16)) & 0xC0C0C0) !== 0x808080) text += invalid;
        else {
          c = ((c1 & 0x07) << 0x12) | ((c2 & 0x3F) << 0x0C) | ((c3 & 0x3F) << 0x06) | (c4 & 0x3F);
          if (c < 0x10000 || c > 0x10FFFF) text += invalid;
          else {
            c -= 0x10000;
            text += fromCharCode((c >> 10) + 0xD800, (c & 0x3FF) + 0xDC00);
            i += 3;
          }
        }
      }
    }

    else text += invalid;
  }

  return text;
}

function writeString(bb, text) {
  // Sadly a hand-coded UTF8 encoder is much faster than TextEncoder+set in V8
  let n = text.length;
  let byteCount = 0;

  // Write the byte count first
  for (let i = 0; i < n; i++) {
    let c = text.charCodeAt(i);
    if (c >= 0xD800 && c <= 0xDBFF && i + 1 < n) {
      c = (c << 10) + text.charCodeAt(++i) - 0x35FDC00;
    }
    byteCount += c < 0x80 ? 1 : c < 0x800 ? 2 : c < 0x10000 ? 3 : 4;
  }
  writeVarint32(bb, byteCount);

  let offset = grow(bb, byteCount);
  let bytes = bb.bytes;

  // Then write the bytes
  for (let i = 0; i < n; i++) {
    let c = text.charCodeAt(i);
    if (c >= 0xD800 && c <= 0xDBFF && i + 1 < n) {
      c = (c << 10) + text.charCodeAt(++i) - 0x35FDC00;
    }
    if (c < 0x80) {
      bytes[offset++] = c;
    } else {
      if (c < 0x800) {
        bytes[offset++] = ((c >> 6) & 0x1F) | 0xC0;
      } else {
        if (c < 0x10000) {
          bytes[offset++] = ((c >> 12) & 0x0F) | 0xE0;
        } else {
          bytes[offset++] = ((c >> 18) & 0x07) | 0xF0;
          bytes[offset++] = ((c >> 12) & 0x3F) | 0x80;
        }
        bytes[offset++] = ((c >> 6) & 0x3F) | 0x80;
      }
      bytes[offset++] = (c & 0x3F) | 0x80;
    }
  }
}

function writeByteBuffer(bb, buffer) {
  let offset = grow(bb, buffer.limit);
  let from = bb.bytes;
  let to = buffer.bytes;

  // This for loop is much faster than subarray+set on V8
  for (let i = 0, n = buffer.limit; i < n; i++) {
    from[i + offset] = to[i];
  }
}

function readByte(bb) {
  return bb.bytes[advance(bb, 1)];
}

function writeByte(bb, value) {
  let offset = grow(bb, 1);
  bb.bytes[offset] = value;
}

function readFloat(bb) {
  let offset = advance(bb, 4);
  let bytes = bb.bytes;

  // Manual copying is much faster than subarray+set in V8
  f32_u8[0] = bytes[offset++];
  f32_u8[1] = bytes[offset++];
  f32_u8[2] = bytes[offset++];
  f32_u8[3] = bytes[offset++];
  return f32[0];
}

function writeFloat(bb, value) {
  let offset = grow(bb, 4);
  let bytes = bb.bytes;
  f32[0] = value;

  // Manual copying is much faster than subarray+set in V8
  bytes[offset++] = f32_u8[0];
  bytes[offset++] = f32_u8[1];
  bytes[offset++] = f32_u8[2];
  bytes[offset++] = f32_u8[3];
}

function readDouble(bb) {
  let offset = advance(bb, 8);
  let bytes = bb.bytes;

  // Manual copying is much faster than subarray+set in V8
  f64_u8[0] = bytes[offset++];
  f64_u8[1] = bytes[offset++];
  f64_u8[2] = bytes[offset++];
  f64_u8[3] = bytes[offset++];
  f64_u8[4] = bytes[offset++];
  f64_u8[5] = bytes[offset++];
  f64_u8[6] = bytes[offset++];
  f64_u8[7] = bytes[offset++];
  return f64[0];
}

function writeDouble(bb, value) {
  let offset = grow(bb, 8);
  let bytes = bb.bytes;
  f64[0] = value;

  // Manual copying is much faster than subarray+set in V8
  bytes[offset++] = f64_u8[0];
  bytes[offset++] = f64_u8[1];
  bytes[offset++] = f64_u8[2];
  bytes[offset++] = f64_u8[3];
  bytes[offset++] = f64_u8[4];
  bytes[offset++] = f64_u8[5];
  bytes[offset++] = f64_u8[6];
  bytes[offset++] = f64_u8[7];
}

function readInt32(bb) {
  let offset = advance(bb, 4);
  let bytes = bb.bytes;
  return (
    bytes[offset] |
    (bytes[offset + 1] << 8) |
    (bytes[offset + 2] << 16) |
    (bytes[offset + 3] << 24)
  );
}

function writeInt32(bb, value) {
  let offset = grow(bb, 4);
  let bytes = bb.bytes;
  bytes[offset] = value;
  bytes[offset + 1] = value >> 8;
  bytes[offset + 2] = value >> 16;
  bytes[offset + 3] = value >> 24;
}

function readInt64(bb, unsigned) {
  return {
    low: readInt32(bb),
    high: readInt32(bb),
    unsigned,
  };
}

function writeInt64(bb, value) {
  writeInt32(bb, value.low);
  writeInt32(bb, value.high);
}

function readVarint32(bb) {
  let c = 0;
  let value = 0;
  let b;
  do {
    b = readByte(bb);
    if (c < 32) value |= (b & 0x7F) << c;
    c += 7;
  } while (b & 0x80);
  return value;
}

function writeVarint32(bb, value) {
  value >>>= 0;
  while (value >= 0x80) {
    writeByte(bb, (value & 0x7f) | 0x80);
    value >>>= 7;
  }
  writeByte(bb, value);
}

function readVarint64(bb, unsigned) {
  let part0 = 0;
  let part1 = 0;
  let part2 = 0;
  let b;

  b = readByte(bb); part0 = (b & 0x7F); if (b & 0x80) {
    b = readByte(bb); part0 |= (b & 0x7F) << 7; if (b & 0x80) {
      b = readByte(bb); part0 |= (b & 0x7F) << 14; if (b & 0x80) {
        b = readByte(bb); part0 |= (b & 0x7F) << 21; if (b & 0x80) {

          b = readByte(bb); part1 = (b & 0x7F); if (b & 0x80) {
            b = readByte(bb); part1 |= (b & 0x7F) << 7; if (b & 0x80) {
              b = readByte(bb); part1 |= (b & 0x7F) << 14; if (b & 0x80) {
                b = readByte(bb); part1 |= (b & 0x7F) << 21; if (b & 0x80) {

                  b = readByte(bb); part2 = (b & 0x7F); if (b & 0x80) {
                    b = readByte(bb); part2 |= (b & 0x7F) << 7;
                  }
                }
              }
            }
          }
        }
      }
    }
  }

  return {
    low: part0 | (part1 << 28),
    high: (part1 >>> 4) | (part2 << 24),
    unsigned,
  };
}

function writeVarint64(bb, value) {
  let part0 = value.low >>> 0;
  let part1 = ((value.low >>> 28) | (value.high << 4)) >>> 0;
  let part2 = value.high >>> 24;

  // ref: src/google/protobuf/io/coded_stream.cc
  let size =
    part2 === 0 ?
      part1 === 0 ?
        part0 < 1 << 14 ?
          part0 < 1 << 7 ? 1 : 2 :
          part0 < 1 << 21 ? 3 : 4 :
        part1 < 1 << 14 ?
          part1 < 1 << 7 ? 5 : 6 :
          part1 < 1 << 21 ? 7 : 8 :
      part2 < 1 << 7 ? 9 : 10;

  let offset = grow(bb, size);
  let bytes = bb.bytes;

  switch (size) {
    case 10: bytes[offset + 9] = (part2 >>> 7) & 0x01;
    case 9: bytes[offset + 8] = size !== 9 ? part2 | 0x80 : part2 & 0x7F;
    case 8: bytes[offset + 7] = size !== 8 ? (part1 >>> 21) | 0x80 : (part1 >>> 21) & 0x7F;
    case 7: bytes[offset + 6] = size !== 7 ? (part1 >>> 14) | 0x80 : (part1 >>> 14) & 0x7F;
    case 6: bytes[offset + 5] = size !== 6 ? (part1 >>> 7) | 0x80 : (part1 >>> 7) & 0x7F;
    case 5: bytes[offset + 4] = size !== 5 ? part1 | 0x80 : part1 & 0x7F;
    case 4: bytes[offset + 3] = size !== 4 ? (part0 >>> 21) | 0x80 : (part0 >>> 21) & 0x7F;
    case 3: bytes[offset + 2] = size !== 3 ? (part0 >>> 14) | 0x80 : (part0 >>> 14) & 0x7F;
    case 2: bytes[offset + 1] = size !== 2 ? (part0 >>> 7) | 0x80 : (part0 >>> 7) & 0x7F;
    case 1: bytes[offset] = size !== 1 ? part0 | 0x80 : part0 & 0x7F;
  }
}

function readVarint32ZigZag(bb) {
  let value = readVarint32(bb);

  // ref: src/google/protobuf/wire_format_lite.h
  return (value >>> 1) ^ -(value & 1);
}

function writeVarint32ZigZag(bb, value) {
  // ref: src/google/protobuf/wire_format_lite.h
  writeVarint32(bb, (value << 1) ^ (value >> 31));
}

function readVarint64ZigZag(bb) {
  let value = readVarint64(bb, /* unsigned */ false);
  let low = value.low;
  let high = value.high;
  let flip = -(low & 1);

  // ref: src/google/protobuf/wire_format_lite.h
  return {
    low: ((low >>> 1) | (high << 31)) ^ flip,
    high: (high >>> 1) ^ flip,
    unsigned: false,
  };
}

function writeVarint64ZigZag(bb, value) {
  let low = value.low;
  let high = value.high;
  let flip = high >> 31;

  // ref: src/google/protobuf/wire_format_lite.h
  writeVarint64(bb, {
    low: (low << 1) ^ flip,
    high: ((high << 1) | (low >>> 31)) ^ flip,
    unsigned: false,
  });
}
