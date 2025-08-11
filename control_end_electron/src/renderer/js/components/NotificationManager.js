/**
 * 统一的通知管理器 - 跨平台兼容的notification实现
 * 解决Windows上notification无法消失的问题
 */

export default class NotificationManager {
    constructor() {
        this.notifications = new Map();
        this.container = null;
        this.config = {
            duration: 1500,        // 默认显示时间（毫秒）
            maxNotifications: 5,   // 最大同时显示数量
            position: 'top-left',  // 显示位置
            zIndex: 2050          // 层级
        };
        
        this.init();
    }

    /**
     * 初始化通知容器
     */
    init() {
        // 查找或创建通知容器
        this.container = document.querySelector('.notification-container-global');
        if (!this.container) {
            this.container = this.createContainer();
            document.body.appendChild(this.container);
        }
        
        // 确保CSS样式已加载
        this.ensureStyles();
    }

    /**
     * 创建通知容器
     */
    createContainer() {
        const container = document.createElement('div');
        container.className = 'notification-container-global';
        container.style.cssText = `
            position: fixed;
            top: 20px;
            left: 20px;
            z-index: ${this.config.zIndex};
            width: 280px;
            pointer-events: none;
        `;
        return container;
    }

    /**
     * 确保必要的CSS样式已加载
     */
    ensureStyles() {
        if (document.querySelector('#notification-styles')) return;

        const style = document.createElement('style');
        style.id = 'notification-styles';
        style.textContent = `
            .notification-container-global {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            }

            .notification-item {
                background: white;
                border: 1px solid #e8e8e8;
                border-radius: 6px;
                box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
                margin-bottom: 8px;
                overflow: hidden;
                pointer-events: auto;
                position: relative;
                transform: translateX(-100%);
                opacity: 0;
                transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
            }

            .notification-item.show {
                transform: translateX(0);
                opacity: 1;
            }

            .notification-item.hide {
                transform: translateX(-100%);
                opacity: 0;
                margin-bottom: 0;
                padding-top: 0;
                padding-bottom: 0;
                max-height: 0;
            }

            .notification-content {
                padding: 10px 12px;
                display: flex;
                align-items: flex-start;
                gap: 8px;
            }

            .notification-icon {
                width: 16px;
                height: 16px;
                flex-shrink: 0;
                margin-top: 1px;
            }

            .notification-body {
                flex: 1;
                min-width: 0;
            }

            .notification-title {
                font-size: 13px;
                font-weight: 600;
                margin: 0 0 2px 0;
                line-height: 1.2;
            }

            .notification-message {
                font-size: 12px;
                margin: 0;
                line-height: 1.3;
                word-wrap: break-word;
            }

            .notification-close {
                background: none;
                border: none;
                color: #8c8c8c;
                cursor: pointer;
                font-size: 14px;
                width: 20px;
                height: 20px;
                border-radius: 3px;
                display: flex;
                align-items: center;
                justify-content: center;
                transition: all 0.2s ease;
                flex-shrink: 0;
            }

            .notification-close:hover {
                background-color: #f5f5f5;
                color: #262626;
            }

            .notification-close:focus {
                outline: 1px solid #1890ff;
                outline-offset: 1px;
            }

            /* 类型样式 */
            .notification-success {
                border-left: 3px solid #52c41a;
            }
            .notification-success .notification-title {
                color: #389e0d;
            }
            .notification-success .notification-icon {
                color: #52c41a;
            }

            .notification-warning {
                border-left: 3px solid #faad14;
            }
            .notification-warning .notification-title {
                color: #d46b08;
            }
            .notification-warning .notification-icon {
                color: #faad14;
            }

            .notification-danger {
                border-left: 3px solid #ff4d4f;
            }
            .notification-danger .notification-title {
                color: #cf1322;
            }
            .notification-danger .notification-icon {
                color: #ff4d4f;
            }

            .notification-info {
                border-left: 3px solid #1890ff;
            }
            .notification-info .notification-title {
                color: #0958d9;
            }
            .notification-info .notification-icon {
                color: #1890ff;
            }

            /* 进度条 */
            .notification-progress {
                position: absolute;
                bottom: 0;
                left: 0;
                height: 2px;
                background-color: rgba(0, 0, 0, 0.1);
                transition: width linear;
            }

            .notification-success .notification-progress {
                background-color: #52c41a;
            }
            .notification-warning .notification-progress {
                background-color: #faad14;
            }
            .notification-danger .notification-progress {
                background-color: #ff4d4f;
            }
            .notification-info .notification-progress {
                background-color: #1890ff;
            }

            /* 响应式设计 */
            @media (max-width: 480px) {
                .notification-container-global {
                    left: 8px;
                    right: 8px;
                    width: auto;
                }
                
                .notification-item {
                    transform: translateY(-100%);
                }
                
                .notification-item.show {
                    transform: translateY(0);
                }
                
                .notification-item.hide {
                    transform: translateY(-100%);
                }

                .notification-content {
                    padding: 8px 10px;
                }
            }

            /* Windows兼容性增强 */
            .notification-item {
                will-change: transform, opacity;
                backface-visibility: hidden;
                -webkit-backface-visibility: hidden;
            }
        `;
        document.head.appendChild(style);
    }

    /**
     * 显示通知
     * @param {string} type - 通知类型: 'success', 'warning', 'danger', 'info'
     * @param {string} title - 标题
     * @param {string} message - 消息内容
     * @param {Object} options - 选项
     * @returns {string} 通知ID
     */
    show(type = 'info', title = '', message = '', options = {}) {
        const config = { ...this.config, ...options };
        const id = this.generateId();
        
        // 清理过多的通知
        this.cleanup();
        
        // 创建通知元素
        const notification = this.createElement(id, type, title, message, config);
        
        // 添加到容器
        this.container.appendChild(notification);
        
        // 强制重排以确保动画生效（Windows兼容性）
        notification.offsetHeight;
        
        // 显示动画
        requestAnimationFrame(() => {
            notification.classList.add('show');
        });
        
        // 保存通知引用
        const notificationData = {
            element: notification,
            type,
            title,
            message,
            config,
            startTime: Date.now()
        };
        this.notifications.set(id, notificationData);
        
        // 设置自动隐藏
        if (config.duration > 0) {
            this.scheduleHide(id, config.duration);
        }
        
        // 设置进度条动画
        if (config.duration > 0 && config.showProgress !== false) {
            this.animateProgress(id, config.duration);
        }
        
        return id;
    }

    /**
     * 创建通知元素
     */
    createElement(id, type, title, message, config) {
        const notification = document.createElement('div');
        notification.id = id;
        notification.className = `notification-item notification-${type}`;
        
        const iconMap = {
            success: '✓',
            warning: '⚠',
            danger: '✕',
            info: 'ℹ'
        };
        
        notification.innerHTML = `
            <div class="notification-content">
                <div class="notification-icon">${iconMap[type] || iconMap.info}</div>
                <div class="notification-body">
                    ${title ? `<div class="notification-title">${this.escapeHtml(title)}</div>` : ''}
                    <div class="notification-message">${this.escapeHtml(message)}</div>
                </div>
                <button class="notification-close" type="button" aria-label="关闭">×</button>
            </div>
            ${config.duration > 0 && config.showProgress !== false ? '<div class="notification-progress"></div>' : ''}
        `;
        
        // 绑定关闭事件
        const closeBtn = notification.querySelector('.notification-close');
        closeBtn.addEventListener('click', () => this.hide(id));
        
        // 鼠标悬停暂停自动隐藏
        notification.addEventListener('mouseenter', () => this.pauseHide(id));
        notification.addEventListener('mouseleave', () => this.resumeHide(id));
        
        return notification;
    }

    /**
     * 隐藏通知
     * @param {string} id - 通知ID
     */
    hide(id) {
        const notification = this.notifications.get(id);
        if (!notification) return;
        
        const { element } = notification;
        
        // 清除定时器
        this.clearTimers(id);
        
        // 隐藏动画
        element.classList.remove('show');
        element.classList.add('hide');
        
        // 动画结束后移除元素
        const handleTransitionEnd = () => {
            element.removeEventListener('transitionend', handleTransitionEnd);
            if (element.parentNode) {
                element.parentNode.removeChild(element);
            }
            this.notifications.delete(id);
        };
        
        element.addEventListener('transitionend', handleTransitionEnd);
        
        // 备用清理（防止事件未触发）
        setTimeout(() => {
            if (element.parentNode) {
                element.parentNode.removeChild(element);
            }
            this.notifications.delete(id);
        }, 500);
    }

    /**
     * 安排自动隐藏
     */
    scheduleHide(id, duration) {
        const notification = this.notifications.get(id);
        if (!notification) return;
        
        notification.hideTimer = setTimeout(() => {
            this.hide(id);
        }, duration);
    }

    /**
     * 暂停自动隐藏
     */
    pauseHide(id) {
        const notification = this.notifications.get(id);
        if (!notification || !notification.hideTimer) return;
        
        clearTimeout(notification.hideTimer);
        notification.pausedAt = Date.now();
    }

    /**
     * 恢复自动隐藏
     */
    resumeHide(id) {
        const notification = this.notifications.get(id);
        if (!notification || !notification.pausedAt) return;
        
        const elapsed = notification.pausedAt - notification.startTime;
        const remaining = Math.max(0, notification.config.duration - elapsed);
        
        if (remaining > 0) {
            this.scheduleHide(id, remaining);
        } else {
            this.hide(id);
        }
        
        delete notification.pausedAt;
    }

    /**
     * 动画化进度条
     */
    animateProgress(id, duration) {
        const notification = this.notifications.get(id);
        if (!notification) return;
        
        const progressBar = notification.element.querySelector('.notification-progress');
        if (!progressBar) return;
        
        progressBar.style.width = '100%';
        progressBar.style.transitionDuration = `${duration}ms`;
        
        requestAnimationFrame(() => {
            progressBar.style.width = '0%';
        });
    }

    /**
     * 清除定时器
     */
    clearTimers(id) {
        const notification = this.notifications.get(id);
        if (!notification) return;
        
        if (notification.hideTimer) {
            clearTimeout(notification.hideTimer);
            delete notification.hideTimer;
        }
        if (notification.progressTimer) {
            clearTimeout(notification.progressTimer);
            delete notification.progressTimer;
        }
    }

    /**
     * 清理过多的通知
     */
    cleanup() {
        if (this.notifications.size >= this.config.maxNotifications) {
            // 移除最旧的通知
            const oldest = Array.from(this.notifications.entries())
                .sort((a, b) => a[1].startTime - b[1].startTime)[0];
            if (oldest) {
                this.hide(oldest[0]);
            }
        }
    }

    /**
     * 生成唯一ID
     */
    generateId() {
        return `notification-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    }

    /**
     * 转义HTML
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * 清除所有通知
     */
    clear() {
        for (const id of this.notifications.keys()) {
            this.hide(id);
        }
    }

    /**
     * 便捷方法
     */
    success(title, message, options) {
        return this.show('success', title, message, options);
    }

    warning(title, message, options) {
        return this.show('warning', title, message, options);
    }

    error(title, message, options) {
        return this.show('danger', title, message, options);
    }

    info(title, message, options) {
        return this.show('info', title, message, options);
    }

    /**
     * 销毁管理器
     */
    destroy() {
        this.clear();
        if (this.container && this.container.parentNode) {
            this.container.parentNode.removeChild(this.container);
        }
        this.notifications.clear();
        
        // 移除样式
        const styles = document.querySelector('#notification-styles');
        if (styles) {
            styles.parentNode.removeChild(styles);
        }
    }
}

// 创建全局实例
window.NotificationManager = window.NotificationManager || new NotificationManager();

export { NotificationManager };