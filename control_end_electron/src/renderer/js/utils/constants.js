// 应用常量定义
export const PAGES = {
    PARTICIPANT_MANAGEMENT: 'participant_management',
    MAP_MANAGEMENT: 'map_management',
    EXPERIMENT_CONTROL: 'experiment_control',
    SESSION_RESULTS: 'session_results'
};

export const EVENTS = {
    // 导航事件
    NAVIGATE_TO: 'navigate_to',
    NAVIGATION_COMPLETE: 'navigation_complete',
    
    // 会话事件
    SESSION_STARTED: 'session_started',
    SESSION_ENDED: 'session_ended',
    SESSION_PAUSED: 'session_paused',
    
    // 机器人事件
    ROBOT_STATUS_UPDATE: 'robot_status_update',
    VIDEO_STREAM_UPDATE: 'video_stream_update',
    
    // 数据事件
    DATA_UPDATED: 'data_updated',
    DATA_ERROR: 'data_error',
    
    // UI事件
    MODAL_OPEN: 'modal_open',
    MODAL_CLOSE: 'modal_close',
    LOADING_START: 'loading_start',
    LOADING_END: 'loading_end'
};

export const API_ENDPOINTS = {
    PARTICIPANTS: '/api/participants',
    MAPS: '/api/maps',
    SESSIONS: '/api/sessions',
    TARGETS: '/api/targets',
    IMAGES: '/api/images'
};

export const ROBOT_COMMANDS = {
    POSTURES: {
        STAND: 'STAND',
        SIT: 'SIT',
        LIE: 'LIE'
    },
    SYSTEM_ACTIONS: {
        EMERGENCY_STOP: 'EMERGENCY_STOP',
        RESET: 'RESET'
    }
};

export const SESSION_STATUS = {
    STARTED: 'started',
    PAUSED: 'paused',
    ENDED: 'ended'
};

export const VALIDATION_RULES = {
    PARTICIPANT_NAME: {
        required: true,
        minLength: 2,
        maxLength: 50
    },
    PARENT_PHONE: {
        required: true,
        pattern: /^1[3-9]\d{9}$/
    },
    MAP_NAME: {
        required: true,
        minLength: 2,
        maxLength: 100
    }
};