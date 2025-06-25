// 基础组件类 - 所有组件的基类
import EventBus from '../eventBus.js';
import Logger from '../utils/logger.js';

export default class BaseComponent {
    constructor(containerId = null) {
        this.containerId = containerId;
        this.container = null;
        this.eventListeners = [];
        this.isDestroyed = false;
        
        if (containerId) {
            this.container = document.getElementById(containerId);
            if (!this.container) {
                Logger.warn(`Container not found: ${containerId}`);
            }
        }
    }

    // 渲染组件
    async render(container = null) {
        if (this.isDestroyed) {
            throw new Error('Cannot render destroyed component');
        }

        this.container = container || this.container;
        if (!this.container) {
            throw new Error('No container available for rendering');
        }

        try {
            await this.beforeRender();
            await this.doRender();
            await this.afterRender();
            Logger.debug(`Component rendered: ${this.constructor.name}`);
        } catch (error) {
            Logger.error(`Failed to render component ${this.constructor.name}:`, error);
            throw error;
        }
    }

    // 渲染前的准备工作
    async beforeRender() {
        // 子类可以重写此方法
    }

    // 实际渲染逻辑 - 子类必须实现
    async doRender() {
        throw new Error('doRender method must be implemented by subclass');
    }

    // 渲染后的初始化工作
    async afterRender() {
        this.setupEventListeners();
    }

    // 设置事件监听器 - 子类可以重写
    setupEventListeners() {
        // 子类实现具体的事件监听器
    }

    // 添加事件监听器（自动管理生命周期）
    addEventListener(element, event, handler, options = {}) {
        if (!element || typeof handler !== 'function') {
            Logger.warn('Invalid addEventListener parameters');
            return;
        }

        element.addEventListener(event, handler, options);
        this.eventListeners.push({ element, event, handler, options });
    }

    // 监听EventBus事件
    onEvent(eventName, handler) {
        EventBus.on(eventName, handler);
        this.eventListeners.push({ eventBus: true, eventName, handler });
    }

    // 触发EventBus事件
    emitEvent(eventName, data) {
        EventBus.emit(eventName, data);
    }

    // 查找元素
    querySelector(selector) {
        if (!this.container) return null;
        return this.container.querySelector(selector);
    }

    querySelectorAll(selector) {
        if (!this.container) return [];
        return this.container.querySelectorAll(selector);
    }

    // 显示组件
    show() {
        if (this.container) {
            this.container.style.display = '';
        }
    }

    // 隐藏组件
    hide() {
        if (this.container) {
            this.container.style.display = 'none';
        }
    }

    // 启用组件
    enable() {
        if (this.container) {
            this.container.classList.remove('disabled');
            const inputs = this.container.querySelectorAll('input, button, select, textarea');
            inputs.forEach(input => input.disabled = false);
        }
    }

    // 禁用组件
    disable() {
        if (this.container) {
            this.container.classList.add('disabled');
            const inputs = this.container.querySelectorAll('input, button, select, textarea');
            inputs.forEach(input => input.disabled = true);
        }
    }

    // 显示加载状态
    showLoading(message = '加载中...') {
        if (this.container) {
            const loadingHtml = `
                <div class="component-loading">
                    <div class="spinner-border text-primary" role="status">
                        <span class="sr-only">${message}</span>
                    </div>
                    <p class="mt-2">${message}</p>
                </div>
            `;
            this.container.innerHTML = loadingHtml;
        }
    }

    // 显示错误状态
    showError(message, details = null) {
        if (this.container) {
            const errorHtml = `
                <div class="component-error alert alert-danger">
                    <h5>错误</h5>
                    <p>${message}</p>
                    ${details ? `<details><summary>详细信息</summary><pre>${details}</pre></details>` : ''}
                    <button class="btn btn-outline-danger btn-sm mt-2" onclick="location.reload()">
                        重新加载
                    </button>
                </div>
            `;
            this.container.innerHTML = errorHtml;
        }
    }

    // 清理资源
    async cleanup() {
        if (this.isDestroyed) return;

        try {
            await this.beforeCleanup();
            this.removeAllEventListeners();
            await this.afterCleanup();
            this.isDestroyed = true;
            Logger.debug(`Component cleaned up: ${this.constructor.name}`);
        } catch (error) {
            Logger.error(`Failed to cleanup component ${this.constructor.name}:`, error);
        }
    }

    // 清理前的准备工作
    async beforeCleanup() {
        // 子类可以重写此方法
    }

    // 清理后的收尾工作
    async afterCleanup() {
        // 子类可以重写此方法
    }

    // 移除所有事件监听器
    removeAllEventListeners() {
        this.eventListeners.forEach(({ element, event, handler, eventBus, eventName }) => {
            try {
                if (eventBus) {
                    EventBus.off(eventName, handler);
                } else if (element && element.removeEventListener) {
                    element.removeEventListener(event, handler);
                }
            } catch (error) {
                Logger.warn('Failed to remove event listener:', error);
            }
        });
        this.eventListeners = [];
    }

    // 验证组件状态
    validateState() {
        if (this.isDestroyed) {
            throw new Error('Component has been destroyed');
        }
    }
}