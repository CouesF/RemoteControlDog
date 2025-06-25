// 应用配置文件
export const CONFIG = {
    // API配置
    API: {
        BASE_URL: 'http://118.31.58.101:48995',
        TIMEOUT: 10000, // 10秒超时
        ENDPOINTS: {
            PARTICIPANTS: '/api/participants',
            MAPS: '/api/maps',
            SESSIONS: '/api/sessions',
            TARGETS: '/api/targets',
            IMAGES: '/api/images',
            ROBOT: '/api/robot'
        }
    },
    
    // WebSocket配置（如果需要）
    WEBSOCKET: {
        URL: 'ws://118.31.58.101:48995/ws'
    },
    
    // 应用设置
    APP: {
        NAME: 'Remote Control Dog',
        VERSION: '1.0.0',
        DEBUG: true
    },
    
    // 机器人控制配置
    ROBOT: {
        COMMANDS: {
            POSTURES: {
                STAND: 'STAND',
                SIT: 'SIT',
                LIE: 'LIE'
            },
            SYSTEM_ACTIONS: {
                EMERGENCY_STOP: 'EMERGENCY_STOP',
                RESET: 'RESET'
            }
        },
        STATUS_UPDATE_INTERVAL: 1000 // 1秒
    },
    
    // 会话配置
    SESSION: {
        STATUS: {
            STARTED: 'started',
            PAUSED: 'paused',
            ENDED: 'ended'
        },
        AUTO_SAVE_INTERVAL: 30000 // 30秒
    },
    
    // 验证规则
    VALIDATION: {
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
    }
};

// 环境配置
export const ENV = {
    DEVELOPMENT: 'development',
    PRODUCTION: 'production',
    CURRENT: 'development' // 可以根据需要修改
};

// 根据环境调整配置
if (ENV.CURRENT === ENV.PRODUCTION) {
    CONFIG.APP.DEBUG = false;
    CONFIG.API.TIMEOUT = 15000; // 生产环境增加超时时间
}

export default CONFIG;
