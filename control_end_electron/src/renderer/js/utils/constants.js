// 应用常量定义
import CONFIG from '../config.js';

export const PAGES = {
    PARTICIPANT_MANAGEMENT: 'participant_management',
    MAP_MANAGEMENT: 'map_management',
    MAP_BUILDER: 'map_builder',
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

// 从配置文件导入API端点
export const API_ENDPOINTS = CONFIG.API.ENDPOINTS;

// 从配置文件导入机器人命令
export const ROBOT_COMMANDS = CONFIG.ROBOT.COMMANDS;

// 从配置文件导入会话状态
export const SESSION_STATUS = CONFIG.SESSION.STATUS;

// 从配置文件导入验证规则
export const VALIDATION_RULES = CONFIG.VALIDATION;
