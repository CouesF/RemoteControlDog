// 日志工具 - 统一的日志管理
export const LOG_LEVELS = {
    DEBUG: 0,
    INFO: 1,
    WARN: 2,
    ERROR: 3
};

class Logger {
    constructor() {
        this.level = LOG_LEVELS.INFO;
        this.enableConsole = true;
        this.logs = [];
        this.maxLogs = 1000;
    }

    setLevel(level) {
        this.level = level;
    }

    debug(message, ...args) {
        this.log(LOG_LEVELS.DEBUG, 'DEBUG', message, ...args);
    }

    info(message, ...args) {
        this.log(LOG_LEVELS.INFO, 'INFO', message, ...args);
    }

    warn(message, ...args) {
        this.log(LOG_LEVELS.WARN, 'WARN', message, ...args);
    }

    error(message, ...args) {
        this.log(LOG_LEVELS.ERROR, 'ERROR', message, ...args);
    }

    log(level, levelName, message, ...args) {
        if (level < this.level) return;

        const timestamp = new Date().toISOString();
        const logEntry = {
            timestamp,
            level: levelName,
            message,
            args: args.length > 0 ? args : undefined
        };

        // 存储日志
        this.logs.push(logEntry);
        if (this.logs.length > this.maxLogs) {
            this.logs.shift();
        }

        // 输出到控制台
        if (this.enableConsole) {
            const consoleMethod = this.getConsoleMethod(level);
            const formattedMessage = `[${timestamp}] [${levelName}] ${message}`;
            
            if (args.length > 0) {
                consoleMethod(formattedMessage, ...args);
            } else {
                consoleMethod(formattedMessage);
            }
        }
    }

    getConsoleMethod(level) {
        switch (level) {
            case LOG_LEVELS.DEBUG:
                return console.debug;
            case LOG_LEVELS.INFO:
                return console.info;
            case LOG_LEVELS.WARN:
                return console.warn;
            case LOG_LEVELS.ERROR:
                return console.error;
            default:
                return console.log;
        }
    }

    getLogs(level = null) {
        if (level === null) {
            return [...this.logs];
        }
        return this.logs.filter(log => log.level === level);
    }

    clearLogs() {
        this.logs = [];
    }

    exportLogs() {
        return JSON.stringify(this.logs, null, 2);
    }
}

export default new Logger();