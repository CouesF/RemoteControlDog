from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ClientType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    CLIENT_TYPE_UNSPECIFIED: _ClassVar[ClientType]
    CONTROLLER_END: _ClassVar[ClientType]
    ROBOT_DOG: _ClassVar[ClientType]
    CLOUD_SERVER: _ClassVar[ClientType]

class NavigationState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    NAV_STATE_UNSPECIFIED: _ClassVar[NavigationState]
    IDLE: _ClassVar[NavigationState]
    NAVIGATING: _ClassVar[NavigationState]
    SUCCEEDED: _ClassVar[NavigationState]
    FAILED: _ClassVar[NavigationState]
    WAITING_FOR_HUMAN: _ClassVar[NavigationState]
    OBSTACLE_DETECTED_PAUSED: _ClassVar[NavigationState]

class PromptActionType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    PROMPT_ACTION_TYPE_UNSPECIFIED: _ClassVar[PromptActionType]
    HEAD_MOVEMENT: _ClassVar[PromptActionType]
    POINTING_GESTURE: _ClassVar[PromptActionType]
    PLAY_SOUND_CUE: _ClassVar[PromptActionType]
    DISPLAY_VISUAL_CUE: _ClassVar[PromptActionType]

class HeadMovementTargetDirection(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    HEAD_TARGET_UNSPECIFIED: _ClassVar[HeadMovementTargetDirection]
    TOWARDS_ESTIMATED_CHILD_POSITION: _ClassVar[HeadMovementTargetDirection]
    TOWARDS_ESTIMATED_RJA_OBJECT_POSITION: _ClassVar[HeadMovementTargetDirection]
    RELATIVE_ANGLES_TO_ROBOT_BODY: _ClassVar[HeadMovementTargetDirection]
    ABSOLUTE_ANGLES_IN_WORLD: _ClassVar[HeadMovementTargetDirection]

class HeadMovementIntensity(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    HEAD_INTENSITY_UNSPECIFIED: _ClassVar[HeadMovementIntensity]
    SUBTLE: _ClassVar[HeadMovementIntensity]
    NORMAL: _ClassVar[HeadMovementIntensity]
    EMPHATIC: _ClassVar[HeadMovementIntensity]

class PointingLimb(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    LIMB_UNSPECIFIED: _ClassVar[PointingLimb]
    HEAD_POINTER: _ClassVar[PointingLimb]
    LEFT_ARM: _ClassVar[PointingLimb]
    RIGHT_ARM: _ClassVar[PointingLimb]

class ChildResponseType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    CHILD_RESPONSE_TYPE_UNSPECIFIED: _ClassVar[ChildResponseType]
    CORRECT_RESPONSE: _ClassVar[ChildResponseType]
    INCORRECT_ATTENTION_TO_ROBOT: _ClassVar[ChildResponseType]
    INCORRECT_ATTENTION_TO_OTHER: _ClassVar[ChildResponseType]
    INCORRECT_NO_SHIFT_OF_ATTENTION: _ClassVar[ChildResponseType]
    NO_RESPONSE_DETECTED: _ClassVar[ChildResponseType]
    OPERATOR_MARKED_OTHER: _ClassVar[ChildResponseType]

class FeedbackActionType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    FEEDBACK_ACTION_TYPE_UNSPECIFIED: _ClassVar[FeedbackActionType]
    ROBOT_ANIMATION: _ClassVar[FeedbackActionType]
    PLAY_FEEDBACK_SOUND: _ClassVar[FeedbackActionType]
    DISPLAY_FEEDBACK_VISUAL: _ClassVar[FeedbackActionType]
    ENGAGE_PERSONALIZED_CONTENT: _ClassVar[FeedbackActionType]

class RobotAnimationId(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    ANIMATION_ID_UNSPECIFIED: _ClassVar[RobotAnimationId]
    NOD_APPROVAL: _ClassVar[RobotAnimationId]
    SHAKE_HEAD_GENTLE: _ClassVar[RobotAnimationId]
    HAPPY_WIGGLE: _ClassVar[RobotAnimationId]
    LOOK_INTERESTED: _ClassVar[RobotAnimationId]
    ENCOURAGING_TILT: _ClassVar[RobotAnimationId]

class PersonalizedContentType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    PERSONALIZED_CONTENT_TYPE_UNSPECIFIED: _ClassVar[PersonalizedContentType]
    SOUND: _ClassVar[PersonalizedContentType]
    VISUAL: _ClassVar[PersonalizedContentType]

class SystemEventSeverity(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    SEVERITY_UNSPECIFIED: _ClassVar[SystemEventSeverity]
    INFO: _ClassVar[SystemEventSeverity]
    WARNING: _ClassVar[SystemEventSeverity]
    ERROR: _ClassVar[SystemEventSeverity]
    CRITICAL: _ClassVar[SystemEventSeverity]
CLIENT_TYPE_UNSPECIFIED: ClientType
CONTROLLER_END: ClientType
ROBOT_DOG: ClientType
CLOUD_SERVER: ClientType
NAV_STATE_UNSPECIFIED: NavigationState
IDLE: NavigationState
NAVIGATING: NavigationState
SUCCEEDED: NavigationState
FAILED: NavigationState
WAITING_FOR_HUMAN: NavigationState
OBSTACLE_DETECTED_PAUSED: NavigationState
PROMPT_ACTION_TYPE_UNSPECIFIED: PromptActionType
HEAD_MOVEMENT: PromptActionType
POINTING_GESTURE: PromptActionType
PLAY_SOUND_CUE: PromptActionType
DISPLAY_VISUAL_CUE: PromptActionType
HEAD_TARGET_UNSPECIFIED: HeadMovementTargetDirection
TOWARDS_ESTIMATED_CHILD_POSITION: HeadMovementTargetDirection
TOWARDS_ESTIMATED_RJA_OBJECT_POSITION: HeadMovementTargetDirection
RELATIVE_ANGLES_TO_ROBOT_BODY: HeadMovementTargetDirection
ABSOLUTE_ANGLES_IN_WORLD: HeadMovementTargetDirection
HEAD_INTENSITY_UNSPECIFIED: HeadMovementIntensity
SUBTLE: HeadMovementIntensity
NORMAL: HeadMovementIntensity
EMPHATIC: HeadMovementIntensity
LIMB_UNSPECIFIED: PointingLimb
HEAD_POINTER: PointingLimb
LEFT_ARM: PointingLimb
RIGHT_ARM: PointingLimb
CHILD_RESPONSE_TYPE_UNSPECIFIED: ChildResponseType
CORRECT_RESPONSE: ChildResponseType
INCORRECT_ATTENTION_TO_ROBOT: ChildResponseType
INCORRECT_ATTENTION_TO_OTHER: ChildResponseType
INCORRECT_NO_SHIFT_OF_ATTENTION: ChildResponseType
NO_RESPONSE_DETECTED: ChildResponseType
OPERATOR_MARKED_OTHER: ChildResponseType
FEEDBACK_ACTION_TYPE_UNSPECIFIED: FeedbackActionType
ROBOT_ANIMATION: FeedbackActionType
PLAY_FEEDBACK_SOUND: FeedbackActionType
DISPLAY_FEEDBACK_VISUAL: FeedbackActionType
ENGAGE_PERSONALIZED_CONTENT: FeedbackActionType
ANIMATION_ID_UNSPECIFIED: RobotAnimationId
NOD_APPROVAL: RobotAnimationId
SHAKE_HEAD_GENTLE: RobotAnimationId
HAPPY_WIGGLE: RobotAnimationId
LOOK_INTERESTED: RobotAnimationId
ENCOURAGING_TILT: RobotAnimationId
PERSONALIZED_CONTENT_TYPE_UNSPECIFIED: PersonalizedContentType
SOUND: PersonalizedContentType
VISUAL: PersonalizedContentType
SEVERITY_UNSPECIFIED: SystemEventSeverity
INFO: SystemEventSeverity
WARNING: SystemEventSeverity
ERROR: SystemEventSeverity
CRITICAL: SystemEventSeverity

class Header(_message.Message):
    __slots__ = ("message_id", "timestamp_utc_ms", "source_id", "target_id", "session_id", "trial_id")
    MESSAGE_ID_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_UTC_MS_FIELD_NUMBER: _ClassVar[int]
    SOURCE_ID_FIELD_NUMBER: _ClassVar[int]
    TARGET_ID_FIELD_NUMBER: _ClassVar[int]
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    TRIAL_ID_FIELD_NUMBER: _ClassVar[int]
    message_id: str
    timestamp_utc_ms: int
    source_id: str
    target_id: str
    session_id: str
    trial_id: str
    def __init__(self, message_id: _Optional[str] = ..., timestamp_utc_ms: _Optional[int] = ..., source_id: _Optional[str] = ..., target_id: _Optional[str] = ..., session_id: _Optional[str] = ..., trial_id: _Optional[str] = ...) -> None: ...

class Vector3(_message.Message):
    __slots__ = ("x", "y", "z")
    X_FIELD_NUMBER: _ClassVar[int]
    Y_FIELD_NUMBER: _ClassVar[int]
    Z_FIELD_NUMBER: _ClassVar[int]
    x: float
    y: float
    z: float
    def __init__(self, x: _Optional[float] = ..., y: _Optional[float] = ..., z: _Optional[float] = ...) -> None: ...

class Quaternion(_message.Message):
    __slots__ = ("x", "y", "z", "w")
    X_FIELD_NUMBER: _ClassVar[int]
    Y_FIELD_NUMBER: _ClassVar[int]
    Z_FIELD_NUMBER: _ClassVar[int]
    W_FIELD_NUMBER: _ClassVar[int]
    x: float
    y: float
    z: float
    w: float
    def __init__(self, x: _Optional[float] = ..., y: _Optional[float] = ..., z: _Optional[float] = ..., w: _Optional[float] = ...) -> None: ...

class Pose(_message.Message):
    __slots__ = ("position", "orientation")
    POSITION_FIELD_NUMBER: _ClassVar[int]
    ORIENTATION_FIELD_NUMBER: _ClassVar[int]
    position: Vector3
    orientation: Quaternion
    def __init__(self, position: _Optional[_Union[Vector3, _Mapping]] = ..., orientation: _Optional[_Union[Quaternion, _Mapping]] = ...) -> None: ...

class UdpPacketWrapper(_message.Message):
    __slots__ = ("header", "target_client_id_for_relay", "actual_message_type", "actual_message_data")
    HEADER_FIELD_NUMBER: _ClassVar[int]
    TARGET_CLIENT_ID_FOR_RELAY_FIELD_NUMBER: _ClassVar[int]
    ACTUAL_MESSAGE_TYPE_FIELD_NUMBER: _ClassVar[int]
    ACTUAL_MESSAGE_DATA_FIELD_NUMBER: _ClassVar[int]
    header: Header
    target_client_id_for_relay: str
    actual_message_type: str
    actual_message_data: bytes
    def __init__(self, header: _Optional[_Union[Header, _Mapping]] = ..., target_client_id_for_relay: _Optional[str] = ..., actual_message_type: _Optional[str] = ..., actual_message_data: _Optional[bytes] = ...) -> None: ...

class RegisterClientRequest(_message.Message):
    __slots__ = ("header", "client_type", "client_id", "client_version", "capabilities")
    HEADER_FIELD_NUMBER: _ClassVar[int]
    CLIENT_TYPE_FIELD_NUMBER: _ClassVar[int]
    CLIENT_ID_FIELD_NUMBER: _ClassVar[int]
    CLIENT_VERSION_FIELD_NUMBER: _ClassVar[int]
    CAPABILITIES_FIELD_NUMBER: _ClassVar[int]
    header: Header
    client_type: ClientType
    client_id: str
    client_version: str
    capabilities: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, header: _Optional[_Union[Header, _Mapping]] = ..., client_type: _Optional[_Union[ClientType, str]] = ..., client_id: _Optional[str] = ..., client_version: _Optional[str] = ..., capabilities: _Optional[_Iterable[str]] = ...) -> None: ...

class RegisterClientResponse(_message.Message):
    __slots__ = ("header", "success", "message", "session_token")
    HEADER_FIELD_NUMBER: _ClassVar[int]
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    SESSION_TOKEN_FIELD_NUMBER: _ClassVar[int]
    header: Header
    success: bool
    message: str
    session_token: str
    def __init__(self, header: _Optional[_Union[Header, _Mapping]] = ..., success: bool = ..., message: _Optional[str] = ..., session_token: _Optional[str] = ...) -> None: ...

class NavigateToPointCommand(_message.Message):
    __slots__ = ("header", "rja_point_id", "target_pose_override", "wait_for_human_if_lost", "wait_duration_ms")
    HEADER_FIELD_NUMBER: _ClassVar[int]
    RJA_POINT_ID_FIELD_NUMBER: _ClassVar[int]
    TARGET_POSE_OVERRIDE_FIELD_NUMBER: _ClassVar[int]
    WAIT_FOR_HUMAN_IF_LOST_FIELD_NUMBER: _ClassVar[int]
    WAIT_DURATION_MS_FIELD_NUMBER: _ClassVar[int]
    header: Header
    rja_point_id: str
    target_pose_override: Pose
    wait_for_human_if_lost: bool
    wait_duration_ms: int
    def __init__(self, header: _Optional[_Union[Header, _Mapping]] = ..., rja_point_id: _Optional[str] = ..., target_pose_override: _Optional[_Union[Pose, _Mapping]] = ..., wait_for_human_if_lost: bool = ..., wait_duration_ms: _Optional[int] = ...) -> None: ...

class HumanDetectionDetails(_message.Message):
    __slots__ = ("is_present", "distance_m", "relative_position", "is_within_interaction_zone")
    IS_PRESENT_FIELD_NUMBER: _ClassVar[int]
    DISTANCE_M_FIELD_NUMBER: _ClassVar[int]
    RELATIVE_POSITION_FIELD_NUMBER: _ClassVar[int]
    IS_WITHIN_INTERACTION_ZONE_FIELD_NUMBER: _ClassVar[int]
    is_present: bool
    distance_m: float
    relative_position: Vector3
    is_within_interaction_zone: bool
    def __init__(self, is_present: bool = ..., distance_m: _Optional[float] = ..., relative_position: _Optional[_Union[Vector3, _Mapping]] = ..., is_within_interaction_zone: bool = ...) -> None: ...

class RjaObjectDetectionDetails(_message.Message):
    __slots__ = ("object_id", "is_visible", "relative_position_to_robot")
    OBJECT_ID_FIELD_NUMBER: _ClassVar[int]
    IS_VISIBLE_FIELD_NUMBER: _ClassVar[int]
    RELATIVE_POSITION_TO_ROBOT_FIELD_NUMBER: _ClassVar[int]
    object_id: str
    is_visible: bool
    relative_position_to_robot: Vector3
    def __init__(self, object_id: _Optional[str] = ..., is_visible: bool = ..., relative_position_to_robot: _Optional[_Union[Vector3, _Mapping]] = ...) -> None: ...

class ActiveActionStatus(_message.Message):
    __slots__ = ("action_name", "progress_percent", "status_description")
    ACTION_NAME_FIELD_NUMBER: _ClassVar[int]
    PROGRESS_PERCENT_FIELD_NUMBER: _ClassVar[int]
    STATUS_DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    action_name: str
    progress_percent: float
    status_description: str
    def __init__(self, action_name: _Optional[str] = ..., progress_percent: _Optional[float] = ..., status_description: _Optional[str] = ...) -> None: ...

class RobotStatusUpdate(_message.Message):
    __slots__ = ("header", "battery_percent", "current_world_pose", "navigation_state", "current_rja_point_id", "human_detection", "rja_object_detections", "current_action", "overall_system_health", "error_messages_active")
    HEADER_FIELD_NUMBER: _ClassVar[int]
    BATTERY_PERCENT_FIELD_NUMBER: _ClassVar[int]
    CURRENT_WORLD_POSE_FIELD_NUMBER: _ClassVar[int]
    NAVIGATION_STATE_FIELD_NUMBER: _ClassVar[int]
    CURRENT_RJA_POINT_ID_FIELD_NUMBER: _ClassVar[int]
    HUMAN_DETECTION_FIELD_NUMBER: _ClassVar[int]
    RJA_OBJECT_DETECTIONS_FIELD_NUMBER: _ClassVar[int]
    CURRENT_ACTION_FIELD_NUMBER: _ClassVar[int]
    OVERALL_SYSTEM_HEALTH_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGES_ACTIVE_FIELD_NUMBER: _ClassVar[int]
    header: Header
    battery_percent: float
    current_world_pose: Pose
    navigation_state: NavigationState
    current_rja_point_id: str
    human_detection: HumanDetectionDetails
    rja_object_detections: _containers.RepeatedCompositeFieldContainer[RjaObjectDetectionDetails]
    current_action: ActiveActionStatus
    overall_system_health: SystemEventSeverity
    error_messages_active: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, header: _Optional[_Union[Header, _Mapping]] = ..., battery_percent: _Optional[float] = ..., current_world_pose: _Optional[_Union[Pose, _Mapping]] = ..., navigation_state: _Optional[_Union[NavigationState, str]] = ..., current_rja_point_id: _Optional[str] = ..., human_detection: _Optional[_Union[HumanDetectionDetails, _Mapping]] = ..., rja_object_detections: _Optional[_Iterable[_Union[RjaObjectDetectionDetails, _Mapping]]] = ..., current_action: _Optional[_Union[ActiveActionStatus, _Mapping]] = ..., overall_system_health: _Optional[_Union[SystemEventSeverity, str]] = ..., error_messages_active: _Optional[_Iterable[str]] = ...) -> None: ...

class HeadMovementParams(_message.Message):
    __slots__ = ("target_direction", "intensity", "specific_target_pose")
    TARGET_DIRECTION_FIELD_NUMBER: _ClassVar[int]
    INTENSITY_FIELD_NUMBER: _ClassVar[int]
    SPECIFIC_TARGET_POSE_FIELD_NUMBER: _ClassVar[int]
    target_direction: HeadMovementTargetDirection
    intensity: HeadMovementIntensity
    specific_target_pose: Pose
    def __init__(self, target_direction: _Optional[_Union[HeadMovementTargetDirection, str]] = ..., intensity: _Optional[_Union[HeadMovementIntensity, str]] = ..., specific_target_pose: _Optional[_Union[Pose, _Mapping]] = ...) -> None: ...

class PointingGestureParams(_message.Message):
    __slots__ = ("limb_to_use", "target_object_relative_position")
    LIMB_TO_USE_FIELD_NUMBER: _ClassVar[int]
    TARGET_OBJECT_RELATIVE_POSITION_FIELD_NUMBER: _ClassVar[int]
    limb_to_use: PointingLimb
    target_object_relative_position: Vector3
    def __init__(self, limb_to_use: _Optional[_Union[PointingLimb, str]] = ..., target_object_relative_position: _Optional[_Union[Vector3, _Mapping]] = ...) -> None: ...

class PlaySoundCueParams(_message.Message):
    __slots__ = ("sound_id_or_filename", "volume_level", "loop")
    SOUND_ID_OR_FILENAME_FIELD_NUMBER: _ClassVar[int]
    VOLUME_LEVEL_FIELD_NUMBER: _ClassVar[int]
    LOOP_FIELD_NUMBER: _ClassVar[int]
    sound_id_or_filename: str
    volume_level: float
    loop: bool
    def __init__(self, sound_id_or_filename: _Optional[str] = ..., volume_level: _Optional[float] = ..., loop: bool = ...) -> None: ...

class DisplayVisualCueParams(_message.Message):
    __slots__ = ("visual_cue_id_or_filename",)
    VISUAL_CUE_ID_OR_FILENAME_FIELD_NUMBER: _ClassVar[int]
    visual_cue_id_or_filename: str
    def __init__(self, visual_cue_id_or_filename: _Optional[str] = ...) -> None: ...

class PromptAction(_message.Message):
    __slots__ = ("action_id", "type", "head_params", "pointing_params", "sound_params", "visual_params", "start_delay_ms", "estimated_duration_ms")
    ACTION_ID_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    HEAD_PARAMS_FIELD_NUMBER: _ClassVar[int]
    POINTING_PARAMS_FIELD_NUMBER: _ClassVar[int]
    SOUND_PARAMS_FIELD_NUMBER: _ClassVar[int]
    VISUAL_PARAMS_FIELD_NUMBER: _ClassVar[int]
    START_DELAY_MS_FIELD_NUMBER: _ClassVar[int]
    ESTIMATED_DURATION_MS_FIELD_NUMBER: _ClassVar[int]
    action_id: str
    type: PromptActionType
    head_params: HeadMovementParams
    pointing_params: PointingGestureParams
    sound_params: PlaySoundCueParams
    visual_params: DisplayVisualCueParams
    start_delay_ms: int
    estimated_duration_ms: int
    def __init__(self, action_id: _Optional[str] = ..., type: _Optional[_Union[PromptActionType, str]] = ..., head_params: _Optional[_Union[HeadMovementParams, _Mapping]] = ..., pointing_params: _Optional[_Union[PointingGestureParams, _Mapping]] = ..., sound_params: _Optional[_Union[PlaySoundCueParams, _Mapping]] = ..., visual_params: _Optional[_Union[DisplayVisualCueParams, _Mapping]] = ..., start_delay_ms: _Optional[int] = ..., estimated_duration_ms: _Optional[int] = ...) -> None: ...

class RjaPromptCommand(_message.Message):
    __slots__ = ("header", "child_current_level", "actions", "rja_object_target_id")
    HEADER_FIELD_NUMBER: _ClassVar[int]
    CHILD_CURRENT_LEVEL_FIELD_NUMBER: _ClassVar[int]
    ACTIONS_FIELD_NUMBER: _ClassVar[int]
    RJA_OBJECT_TARGET_ID_FIELD_NUMBER: _ClassVar[int]
    header: Header
    child_current_level: int
    actions: _containers.RepeatedCompositeFieldContainer[PromptAction]
    rja_object_target_id: str
    def __init__(self, header: _Optional[_Union[Header, _Mapping]] = ..., child_current_level: _Optional[int] = ..., actions: _Optional[_Iterable[_Union[PromptAction, _Mapping]]] = ..., rja_object_target_id: _Optional[str] = ...) -> None: ...

class RjaChildResponseRecord(_message.Message):
    __slots__ = ("header", "responded_to_prompt_message_id", "response_type", "response_time_ms_from_prompt_end", "operator_notes")
    HEADER_FIELD_NUMBER: _ClassVar[int]
    RESPONDED_TO_PROMPT_MESSAGE_ID_FIELD_NUMBER: _ClassVar[int]
    RESPONSE_TYPE_FIELD_NUMBER: _ClassVar[int]
    RESPONSE_TIME_MS_FROM_PROMPT_END_FIELD_NUMBER: _ClassVar[int]
    OPERATOR_NOTES_FIELD_NUMBER: _ClassVar[int]
    header: Header
    responded_to_prompt_message_id: str
    response_type: ChildResponseType
    response_time_ms_from_prompt_end: int
    operator_notes: str
    def __init__(self, header: _Optional[_Union[Header, _Mapping]] = ..., responded_to_prompt_message_id: _Optional[str] = ..., response_type: _Optional[_Union[ChildResponseType, str]] = ..., response_time_ms_from_prompt_end: _Optional[int] = ..., operator_notes: _Optional[str] = ...) -> None: ...

class RobotAnimationParams(_message.Message):
    __slots__ = ("animation_id",)
    ANIMATION_ID_FIELD_NUMBER: _ClassVar[int]
    animation_id: RobotAnimationId
    def __init__(self, animation_id: _Optional[_Union[RobotAnimationId, str]] = ...) -> None: ...

class PlayFeedbackSoundParams(_message.Message):
    __slots__ = ("sound_id_or_filename", "volume_level")
    SOUND_ID_OR_FILENAME_FIELD_NUMBER: _ClassVar[int]
    VOLUME_LEVEL_FIELD_NUMBER: _ClassVar[int]
    sound_id_or_filename: str
    volume_level: float
    def __init__(self, sound_id_or_filename: _Optional[str] = ..., volume_level: _Optional[float] = ...) -> None: ...

class DisplayFeedbackVisualParams(_message.Message):
    __slots__ = ("visual_id_or_filename",)
    VISUAL_ID_OR_FILENAME_FIELD_NUMBER: _ClassVar[int]
    visual_id_or_filename: str
    def __init__(self, visual_id_or_filename: _Optional[str] = ...) -> None: ...

class EngagePersonalizedContentParams(_message.Message):
    __slots__ = ("content_type", "preference_tag")
    CONTENT_TYPE_FIELD_NUMBER: _ClassVar[int]
    PREFERENCE_TAG_FIELD_NUMBER: _ClassVar[int]
    content_type: PersonalizedContentType
    preference_tag: str
    def __init__(self, content_type: _Optional[_Union[PersonalizedContentType, str]] = ..., preference_tag: _Optional[str] = ...) -> None: ...

class FeedbackAction(_message.Message):
    __slots__ = ("action_id", "type", "animation_params", "sound_params", "visual_params", "personalized_params", "start_delay_ms", "estimated_duration_ms")
    ACTION_ID_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    ANIMATION_PARAMS_FIELD_NUMBER: _ClassVar[int]
    SOUND_PARAMS_FIELD_NUMBER: _ClassVar[int]
    VISUAL_PARAMS_FIELD_NUMBER: _ClassVar[int]
    PERSONALIZED_PARAMS_FIELD_NUMBER: _ClassVar[int]
    START_DELAY_MS_FIELD_NUMBER: _ClassVar[int]
    ESTIMATED_DURATION_MS_FIELD_NUMBER: _ClassVar[int]
    action_id: str
    type: FeedbackActionType
    animation_params: RobotAnimationParams
    sound_params: PlayFeedbackSoundParams
    visual_params: DisplayFeedbackVisualParams
    personalized_params: EngagePersonalizedContentParams
    start_delay_ms: int
    estimated_duration_ms: int
    def __init__(self, action_id: _Optional[str] = ..., type: _Optional[_Union[FeedbackActionType, str]] = ..., animation_params: _Optional[_Union[RobotAnimationParams, _Mapping]] = ..., sound_params: _Optional[_Union[PlayFeedbackSoundParams, _Mapping]] = ..., visual_params: _Optional[_Union[DisplayFeedbackVisualParams, _Mapping]] = ..., personalized_params: _Optional[_Union[EngagePersonalizedContentParams, _Mapping]] = ..., start_delay_ms: _Optional[int] = ..., estimated_duration_ms: _Optional[int] = ...) -> None: ...

class RjaFeedbackCommand(_message.Message):
    __slots__ = ("header", "for_prompt_message_id", "child_response_that_triggered_feedback", "actions")
    HEADER_FIELD_NUMBER: _ClassVar[int]
    FOR_PROMPT_MESSAGE_ID_FIELD_NUMBER: _ClassVar[int]
    CHILD_RESPONSE_THAT_TRIGGERED_FEEDBACK_FIELD_NUMBER: _ClassVar[int]
    ACTIONS_FIELD_NUMBER: _ClassVar[int]
    header: Header
    for_prompt_message_id: str
    child_response_that_triggered_feedback: ChildResponseType
    actions: _containers.RepeatedCompositeFieldContainer[FeedbackAction]
    def __init__(self, header: _Optional[_Union[Header, _Mapping]] = ..., for_prompt_message_id: _Optional[str] = ..., child_response_that_triggered_feedback: _Optional[_Union[ChildResponseType, str]] = ..., actions: _Optional[_Iterable[_Union[FeedbackAction, _Mapping]]] = ...) -> None: ...

class ChildProfile(_message.Message):
    __slots__ = ("child_id", "current_rja_level", "preference_tags")
    CHILD_ID_FIELD_NUMBER: _ClassVar[int]
    CURRENT_RJA_LEVEL_FIELD_NUMBER: _ClassVar[int]
    PREFERENCE_TAGS_FIELD_NUMBER: _ClassVar[int]
    child_id: str
    current_rja_level: int
    preference_tags: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, child_id: _Optional[str] = ..., current_rja_level: _Optional[int] = ..., preference_tags: _Optional[_Iterable[str]] = ...) -> None: ...

class SetCurrentChildProfileCommand(_message.Message):
    __slots__ = ("header", "profile")
    HEADER_FIELD_NUMBER: _ClassVar[int]
    PROFILE_FIELD_NUMBER: _ClassVar[int]
    header: Header
    profile: ChildProfile
    def __init__(self, header: _Optional[_Union[Header, _Mapping]] = ..., profile: _Optional[_Union[ChildProfile, _Mapping]] = ...) -> None: ...

class RjaPointDefinition(_message.Message):
    __slots__ = ("point_id", "world_pose", "description")
    POINT_ID_FIELD_NUMBER: _ClassVar[int]
    WORLD_POSE_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    point_id: str
    world_pose: Pose
    description: str
    def __init__(self, point_id: _Optional[str] = ..., world_pose: _Optional[_Union[Pose, _Mapping]] = ..., description: _Optional[str] = ...) -> None: ...

class DefineRjaPointsCommand(_message.Message):
    __slots__ = ("header", "points", "replace_all")
    HEADER_FIELD_NUMBER: _ClassVar[int]
    POINTS_FIELD_NUMBER: _ClassVar[int]
    REPLACE_ALL_FIELD_NUMBER: _ClassVar[int]
    header: Header
    points: _containers.RepeatedCompositeFieldContainer[RjaPointDefinition]
    replace_all: bool
    def __init__(self, header: _Optional[_Union[Header, _Mapping]] = ..., points: _Optional[_Iterable[_Union[RjaPointDefinition, _Mapping]]] = ..., replace_all: bool = ...) -> None: ...

class VideoStreamPacket(_message.Message):
    __slots__ = ("header", "frame_id", "frame_data", "encoding_type", "width", "height", "is_key_frame")
    HEADER_FIELD_NUMBER: _ClassVar[int]
    FRAME_ID_FIELD_NUMBER: _ClassVar[int]
    FRAME_DATA_FIELD_NUMBER: _ClassVar[int]
    ENCODING_TYPE_FIELD_NUMBER: _ClassVar[int]
    WIDTH_FIELD_NUMBER: _ClassVar[int]
    HEIGHT_FIELD_NUMBER: _ClassVar[int]
    IS_KEY_FRAME_FIELD_NUMBER: _ClassVar[int]
    header: Header
    frame_id: int
    frame_data: bytes
    encoding_type: str
    width: int
    height: int
    is_key_frame: bool
    def __init__(self, header: _Optional[_Union[Header, _Mapping]] = ..., frame_id: _Optional[int] = ..., frame_data: _Optional[bytes] = ..., encoding_type: _Optional[str] = ..., width: _Optional[int] = ..., height: _Optional[int] = ..., is_key_frame: bool = ...) -> None: ...

class RobotSystemEvent(_message.Message):
    __slots__ = ("header", "severity", "event_code", "description", "additional_data")
    class AdditionalDataEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    HEADER_FIELD_NUMBER: _ClassVar[int]
    SEVERITY_FIELD_NUMBER: _ClassVar[int]
    EVENT_CODE_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    ADDITIONAL_DATA_FIELD_NUMBER: _ClassVar[int]
    header: Header
    severity: SystemEventSeverity
    event_code: str
    description: str
    additional_data: _containers.ScalarMap[str, str]
    def __init__(self, header: _Optional[_Union[Header, _Mapping]] = ..., severity: _Optional[_Union[SystemEventSeverity, str]] = ..., event_code: _Optional[str] = ..., description: _Optional[str] = ..., additional_data: _Optional[_Mapping[str, str]] = ...) -> None: ...

class CommandAcknowledgement(_message.Message):
    __slots__ = ("header", "acknowledged_message_id", "success", "details")
    HEADER_FIELD_NUMBER: _ClassVar[int]
    ACKNOWLEDGED_MESSAGE_ID_FIELD_NUMBER: _ClassVar[int]
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    DETAILS_FIELD_NUMBER: _ClassVar[int]
    header: Header
    acknowledged_message_id: str
    success: bool
    details: str
    def __init__(self, header: _Optional[_Union[Header, _Mapping]] = ..., acknowledged_message_id: _Optional[str] = ..., success: bool = ..., details: _Optional[str] = ...) -> None: ...

class SystemActionCommand(_message.Message):
    __slots__ = ("header", "action")
    class ActionType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        ACTION_UNSPECIFIED: _ClassVar[SystemActionCommand.ActionType]
        REBOOT_ROBOT: _ClassVar[SystemActionCommand.ActionType]
        SHUTDOWN_ROBOT: _ClassVar[SystemActionCommand.ActionType]
        ENTER_STANDBY_MODE: _ClassVar[SystemActionCommand.ActionType]
        RUN_SELF_DIAGNOSTICS: _ClassVar[SystemActionCommand.ActionType]
        EMERGENCY_STOP: _ClassVar[SystemActionCommand.ActionType]
    ACTION_UNSPECIFIED: SystemActionCommand.ActionType
    REBOOT_ROBOT: SystemActionCommand.ActionType
    SHUTDOWN_ROBOT: SystemActionCommand.ActionType
    ENTER_STANDBY_MODE: SystemActionCommand.ActionType
    RUN_SELF_DIAGNOSTICS: SystemActionCommand.ActionType
    EMERGENCY_STOP: SystemActionCommand.ActionType
    HEADER_FIELD_NUMBER: _ClassVar[int]
    ACTION_FIELD_NUMBER: _ClassVar[int]
    header: Header
    action: SystemActionCommand.ActionType
    def __init__(self, header: _Optional[_Union[Header, _Mapping]] = ..., action: _Optional[_Union[SystemActionCommand.ActionType, str]] = ...) -> None: ...

class ControlCommand(_message.Message):
    __slots__ = ("header", "linear_velocity_x", "linear_velocity_y", "angular_velocity_z")
    HEADER_FIELD_NUMBER: _ClassVar[int]
    LINEAR_VELOCITY_X_FIELD_NUMBER: _ClassVar[int]
    LINEAR_VELOCITY_Y_FIELD_NUMBER: _ClassVar[int]
    ANGULAR_VELOCITY_Z_FIELD_NUMBER: _ClassVar[int]
    header: Header
    linear_velocity_x: float
    linear_velocity_y: float
    angular_velocity_z: float
    def __init__(self, header: _Optional[_Union[Header, _Mapping]] = ..., linear_velocity_x: _Optional[float] = ..., linear_velocity_y: _Optional[float] = ..., angular_velocity_z: _Optional[float] = ...) -> None: ...

class SetPostureCommand(_message.Message):
    __slots__ = ("header", "posture")
    class PostureType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        POSTURE_UNSPECIFIED: _ClassVar[SetPostureCommand.PostureType]
        STAND: _ClassVar[SetPostureCommand.PostureType]
        LIE_DOWN: _ClassVar[SetPostureCommand.PostureType]
    POSTURE_UNSPECIFIED: SetPostureCommand.PostureType
    STAND: SetPostureCommand.PostureType
    LIE_DOWN: SetPostureCommand.PostureType
    HEADER_FIELD_NUMBER: _ClassVar[int]
    POSTURE_FIELD_NUMBER: _ClassVar[int]
    header: Header
    posture: SetPostureCommand.PostureType
    def __init__(self, header: _Optional[_Union[Header, _Mapping]] = ..., posture: _Optional[_Union[SetPostureCommand.PostureType, str]] = ...) -> None: ...
