// 通用模态框组件
import BaseComponent from './BaseComponent.js';
import { EVENTS } from '../utils/constants.js';

export default class Modal extends BaseComponent {
    constructor(modalId, options = {}) {
        super(modalId);
        
        this.options = {
            closeOnBackdrop: true,
            closeOnEscape: true,
            autoFocus: true,
            ...options
        };
        
        this.isOpen = false;
        this.onConfirmCallback = null;
        this.onCancelCallback = null;
    }

    async doRender() {
        if (!this.container) {
            throw new Error('Modal container not found');
        }

        console.debug(`[Modal] Rendering modal: ${this.containerId}`);

        // 确保模态框有正确的结构
        if (!this.container.querySelector('.modal-content')) {
            console.debug(`[Modal] Modal content not found, creating default structure for: ${this.containerId}`);
            this.container.innerHTML = `
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">标题</h5>
                        <span class="close-button">&times;</span>
                    </div>
                    <div class="modal-body">
                        内容
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-dismiss="modal">取消</button>
                        <button type="button" class="btn btn-primary" data-confirm="modal">确认</button>
                    </div>
                </div>
            `;
        } else {
            console.debug(`[Modal] Modal content already exists for: ${this.containerId}`);
        }

        this.modalContent = this.querySelector('.modal-content');
        this.closeButton = this.querySelector('.close-button');
        this.confirmButton = this.querySelector('[data-confirm="modal"]');
        this.cancelButton = this.querySelector('[data-dismiss="modal"]');

        console.debug(`[Modal] Modal elements found:`, {
            modalContent: !!this.modalContent,
            closeButton: !!this.closeButton,
            confirmButton: !!this.confirmButton,
            cancelButton: !!this.cancelButton
        });
    }

    setupEventListeners() {
        // 关闭按钮
        if (this.closeButton) {
            this.addEventListener(this.closeButton, 'click', () => this.hide());
        }

        // 确认按钮
        if (this.confirmButton) {
            this.addEventListener(this.confirmButton, 'click', () => this.handleConfirm());
        }

        // 取消按钮
        if (this.cancelButton) {
            this.addEventListener(this.cancelButton, 'click', () => this.handleCancel());
        }

        // 背景点击关闭
        if (this.options.closeOnBackdrop) {
            this.addEventListener(this.container, 'click', (event) => {
                if (event.target === this.container) {
                    this.hide();
                }
            });
        }

        // ESC键关闭
        if (this.options.closeOnEscape) {
            this.addEventListener(document, 'keydown', (event) => {
                if (event.key === 'Escape' && this.isOpen) {
                    this.hide();
                }
            });
        }
    }

    show() {
        if (this.isOpen) return;

        this.validateState();
        this.container.style.display = 'block';
        this.isOpen = true;

        // 自动聚焦
        if (this.options.autoFocus) {
            const firstInput = this.querySelector('input, select, textarea, button');
            if (firstInput) {
                setTimeout(() => firstInput.focus(), 100);
            }
        }

        // 禁用背景滚动
        document.body.classList.add('modal-open');

        this.emitEvent(EVENTS.MODAL_OPEN, { modalId: this.containerId });
    }

    hide() {
        if (!this.isOpen) return;

        this.container.style.display = 'none';
        this.isOpen = false;

        // 恢复背景滚动
        document.body.classList.remove('modal-open');

        this.emitEvent(EVENTS.MODAL_CLOSE, { modalId: this.containerId });
    }

    toggle() {
        if (this.isOpen) {
            this.hide();
        } else {
            this.show();
        }
    }

    setTitle(title) {
        const titleElement = this.querySelector('.modal-title');
        if (titleElement) {
            titleElement.textContent = title;
        }
    }

    setBody(content) {
        const bodyElement = this.querySelector('.modal-body');
        if (bodyElement) {
            if (typeof content === 'string') {
                bodyElement.innerHTML = content;
            } else if (content instanceof HTMLElement) {
                bodyElement.innerHTML = '';
                bodyElement.appendChild(content);
            }
        }
    }

    setSize(size) {
        const validSizes = ['sm', 'lg', 'xl'];
        if (this.modalContent && validSizes.includes(size)) {
            // 移除现有尺寸类
            validSizes.forEach(s => this.modalContent.classList.remove(`modal-${s}`));
            // 添加新尺寸类
            this.modalContent.classList.add(`modal-${size}`);
        }
    }

    onConfirm(callback) {
        this.onConfirmCallback = callback;
        return this;
    }

    onCancel(callback) {
        this.onCancelCallback = callback;
        return this;
    }

    handleConfirm() {
        try {
            if (this.onConfirmCallback) {
                const result = this.onConfirmCallback();
                // 如果回调返回Promise，等待完成
                if (result instanceof Promise) {
                    result.then((shouldClose) => {
                        if (shouldClose !== false) {
                            this.hide();
                        }
                    }).catch(error => {
                        console.error('Modal confirm callback error:', error);
                    });
                } else if (result !== false) {
                    // 如果回调返回false，不关闭模态框
                    this.hide();
                }
            } else {
                this.hide();
            }
        } catch (error) {
            console.error('Modal confirm error:', error);
        }
    }

    handleCancel() {
        try {
            if (this.onCancelCallback) {
                this.onCancelCallback();
            }
            this.hide();
        } catch (error) {
            console.error('Modal cancel error:', error);
        }
    }

    // 静态方法：快速创建确认对话框
    static confirm(title, message, options = {}) {
        return new Promise((resolve) => {
            const modalId = `confirm-modal-${Date.now()}`;
            const modalHtml = `
                <div id="${modalId}" class="modal" style="display: none;">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">${title}</h5>
                        </div>
                        <div class="modal-body">
                            <p>${message}</p>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-dismiss="modal">
                                ${options.cancelText || '取消'}
                            </button>
                            <button type="button" class="btn btn-primary" data-confirm="modal">
                                ${options.confirmText || '确认'}
                            </button>
                        </div>
                    </div>
                </div>
            `;

            document.body.insertAdjacentHTML('beforeend', modalHtml);
            
            const modal = new Modal(modalId);
            modal.render().then(() => {
                modal.onConfirm(() => {
                    resolve(true);
                    // 清理DOM
                    setTimeout(() => {
                        const element = document.getElementById(modalId);
                        if (element) {
                            element.remove();
                        }
                    }, 300);
                });

                modal.onCancel(() => {
                    resolve(false);
                    // 清理DOM
                    setTimeout(() => {
                        const element = document.getElementById(modalId);
                        if (element) {
                            element.remove();
                        }
                    }, 300);
                });

                modal.show();
            });
        });
    }

    // 静态方法：快速创建警告对话框
    static alert(title, message, options = {}) {
        return new Promise((resolve) => {
            const modalId = `alert-modal-${Date.now()}`;
            const modalHtml = `
                <div id="${modalId}" class="modal" style="display: none;">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">${title}</h5>
                        </div>
                        <div class="modal-body">
                            <p>${message}</p>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-primary" data-confirm="modal">
                                ${options.okText || '确定'}
                            </button>
                        </div>
                    </div>
                </div>
            `;

            document.body.insertAdjacentHTML('beforeend', modalHtml);
            
            const modal = new Modal(modalId);
            modal.render().then(() => {
                modal.onConfirm(() => {
                    resolve();
                    // 清理DOM
                    setTimeout(() => {
                        const element = document.getElementById(modalId);
                        if (element) {
                            element.remove();
                        }
                    }, 300);
                });

                modal.show();
            });
        });
    }
}
