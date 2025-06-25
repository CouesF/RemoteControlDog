// 事件总线 - 实现组件间解耦通信
import Logger from './utils/logger.js';

class EventBus {
    constructor() {
        this.events = new Map();
    }

    on(eventName, callback) {
        if (!this.events.has(eventName)) {
            this.events.set(eventName, []);
        }
        this.events.get(eventName).push(callback);
        Logger.debug(`Event listener added for: ${eventName}`);
    }

    off(eventName, callback) {
        if (!this.events.has(eventName)) return;
        
        const callbacks = this.events.get(eventName);
        const index = callbacks.indexOf(callback);
        if (index > -1) {
            callbacks.splice(index, 1);
            Logger.debug(`Event listener removed for: ${eventName}`);
        }
    }

    emit(eventName, data) {
        if (!this.events.has(eventName)) return;
        
        const callbacks = this.events.get(eventName);
        callbacks.forEach(callback => {
            try {
                callback(data);
            } catch (error) {
                Logger.error(`Error in event callback for ${eventName}:`, error);
            }
        });
        Logger.debug(`Event emitted: ${eventName}`, data);
    }

    once(eventName, callback) {
        const onceCallback = (data) => {
            callback(data);
            this.off(eventName, onceCallback);
        };
        this.on(eventName, onceCallback);
    }

    clear() {
        this.events.clear();
        Logger.debug('All event listeners cleared');
    }
}

export default new EventBus();