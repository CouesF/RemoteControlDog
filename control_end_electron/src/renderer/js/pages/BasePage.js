// 基础页面类 - 所有页面组件的基类
import BaseComponent from '../components/BaseComponent.js';
import Logger from '../utils/logger.js';
import { EVENTS } from '../utils/constants.js';

export default class BasePage extends BaseComponent {
    constructor() {
        super();
        this.pageTitle = 'Unknown Page';
        this.viewTemplate = null;
        this.isLoading = false;
        this.loadingMessage = '加载中...';
    }

    async render(container) {
        this.container = container;
        
        try {
            await this.beforeRender();
            
            if (!this.viewTemplate) {
                throw new Error('View template not defined');
            }

            // 加载HTML模板
            await this.loadViewTemplate();
            
            await this.afterRender();
            Logger.info(`Page rendered: ${this.constructor.name}`);
            
        } catch (error) {
            Logger.error(`Failed to render page ${this.constructor.name}:`, error);
            this.showError('页面加载失败', error.message);
        }
    }

    async beforeRender() {
        this.showLoading(this.loadingMessage);
        await this.loadData();
    }

    async loadViewTemplate() {
        if (!this.viewTemplate) {
            throw new Error('View template not specified');
        }

        try {
            const response = await fetch(`./views/${this.viewTemplate}`);
            if (!response.ok) {
                throw new Error(`Failed to load template: ${response.statusText}`);
            }
            
            const html = await response.text();
            this.container.innerHTML = html;
            
        } catch (error) {
            Logger.error(`Failed to load view template ${this.viewTemplate}:`, error);
            throw error;
        }
    }

    async afterRender() {
        this.setupEventListeners();
        this.updatePageTitle();
        
        // 调用子类的数据渲染方法
        try {
            await this.renderData();
        } catch (error) {
            Logger.error('Failed to render data:', error);
            this.showError('数据渲染失败', error.message);
        }
        
        this.emitEvent(EVENTS.LOADING_END);
    }

    async loadData() {
        // 子类可以重写此方法来加载特定数据
    }

    updatePageTitle() {
        const titleElement = this.querySelector('h1');
        if (titleElement && this.pageTitle) {
            titleElement.textContent = this.pageTitle;
        }
        
        // 更新浏览器标题
        document.title = `${this.pageTitle} - WOZ 训练系统`;
    }

    showLoading(message = this.loadingMessage) {
        this.isLoading = true;
        this.emitEvent(EVENTS.LOADING_START, { message });
        
        if (this.container) {
            this.container.innerHTML = `
                <div class="page-loading">
                    <div class="d-flex justify-content-center align-items-center" style="min-height: 300px;">
                        <div class="text-center">
                            <div class="spinner-border text-primary" role="status">
                                <span class="sr-only">${message}</span>
                            </div>
                            <p class="mt-3 text-muted">${message}</p>
                        </div>
                    </div>
                </div>
            `;
        }
    }

    hideLoading() {
        this.isLoading = false;
        this.emitEvent(EVENTS.LOADING_END);
    }

    showError(title, message, details = null) {
        Logger.error(`Page error in ${this.constructor.name}: ${title} - ${message}`, details);
        
        if (this.container) {
            this.container.innerHTML = `
                <div class="page-error">
                    <div class="alert alert-danger" role="alert">
                        <h4 class="alert-heading">${title}</h4>
                        <p>${message}</p>
                        ${details ? `
                            <hr>
                            <details>
                                <summary>技术详情</summary>
                                <pre class="mt-2">${details}</pre>
                            </details>
                        ` : ''}
                        <div class="mt-3">
                            <button class="btn btn-outline-danger" onclick="location.reload()">
                                <i class="fas fa-redo"></i> 重新加载
                            </button>
                            <button class="btn btn-outline-secondary ml-2" onclick="history.back()">
                                <i class="fas fa-arrow-left"></i> 返回上页
                            </button>
                        </div>
                    </div>
                </div>
            `;
        }
    }

    showSuccess(message, autoHide = true) {
        this.showNotification(message, 'success', autoHide);
    }

    showWarning(message, autoHide = true) {
        this.showNotification(message, 'warning', autoHide);
    }

    showInfo(message, autoHide = true) {
        this.showNotification(message, 'info', autoHide);
    }

    showNotification(message, type = 'info', autoHide = true) {
        const notificationId = `notification-${Date.now()}`;
        const alertClass = `alert-${type}`;
        
        const notificationHtml = `
            <div id="${notificationId}" class="alert ${alertClass} alert-dismissible fade show" role="alert">
                ${message}
                <button type="button" class="close" data-dismiss="alert">
                    <span>&times;</span>
                </button>
            </div>
        `;

        // 在页面顶部插入通知
        const pageHeader = this.querySelector('.page-header') || this.container;
        if (pageHeader) {
            pageHeader.insertAdjacentHTML('afterbegin', notificationHtml);
        }

        // 自动隐藏
        if (autoHide) {
            setTimeout(() => {
                const notification = document.getElementById(notificationId);
                if (notification) {
                    notification.remove();
                }
            }, 5000);
        }
    }

    // 数据刷新方法
    async refreshData() {
        try {
            this.showLoading('刷新数据中...');
            await this.loadData();
            await this.renderData();
            this.hideLoading();
            this.showSuccess('数据刷新成功');
        } catch (error) {
            this.hideLoading();
            this.showError('数据刷新失败', error.message);
        }
    }

    // 子类需要实现的方法
    async renderData() {
        // 子类实现具体的数据渲染逻辑
    }

    // 表单验证辅助方法
    validateForm(formElement) {
        if (!formElement) return false;

        const inputs = formElement.querySelectorAll('input[required], select[required], textarea[required]');
        let isValid = true;
        const errors = [];

        inputs.forEach(input => {
            if (!input.value.trim()) {
                isValid = false;
                errors.push(`${this.getFieldLabel(input)} 不能为空`);
                this.markFieldError(input);
            } else {
                this.clearFieldError(input);
            }
        });

        if (!isValid) {
            this.showWarning(`表单验证失败：${errors.join('、')}`);
        }

        return isValid;
    }

    getFieldLabel(input) {
        const label = input.closest('.form-group')?.querySelector('label');
        return label ? label.textContent.replace(':', '') : input.name || input.id || '字段';
    }

    markFieldError(input) {
        input.classList.add('is-invalid');
    }

    clearFieldError(input) {
        input.classList.remove('is-invalid');
    }

    // 确认对话框
    async confirmAction(title, message) {
        // 这里可以使用Modal组件或浏览器原生confirm
        return new Promise((resolve) => {
            const result = confirm(`${title}\n\n${message}`);
            resolve(result);
        });
    }

    // 通用的删除确认
    async confirmDelete(itemName) {
        return this.confirmAction(
            '确认删除',
            `确定要删除"${itemName}"吗？此操作不可撤销。`
        );
    }

    // 获取URL参数
    getUrlParam(name) {
        const urlParams = new URLSearchParams(window.location.search);
        return urlParams.get(name);
    }

    // 导航到其他页面
    navigateTo(pageName, options = {}) {
        this.emitEvent(EVENTS.NAVIGATE_TO, { page: pageName, options });
    }

    // 页面清理
    async cleanup() {
        this.hideLoading();
        await super.cleanup();
    }
}