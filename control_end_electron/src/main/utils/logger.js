/**
 * @file logger.js
 * @description A simple logger for the main process.
 */

const logger = {
    info: (...args) => {
        console.log('[INFO]', ...args);
    },
    warn: (...args) => {
        console.warn('[WARN]', ...args);
    },
    error: (...args) => {
        console.error('[ERROR]', ...args);
    }
};

module.exports = { logger };
