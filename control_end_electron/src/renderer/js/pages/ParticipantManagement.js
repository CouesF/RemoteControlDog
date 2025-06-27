// 参与者管理页面
import BasePage from './BasePage.js';
import Modal from '../components/modal.js';
import ParticipantsAPI from '../api/participants.js';
import SessionsAPI from '../api/sessions.js';
import mapsAPI from '../api/maps.js';
import { EVENTS } from '../utils/constants.js';
import { Validator } from '../utils/validator.js';
import Logger from '../utils/logger.js';
import { formatIdDisplayWithTitle } from '../utils/idFormatter.js';

export default class ParticipantManagement extends BasePage {
    constructor() {
        super();
        this.pageTitle = '被试管理';
        this.viewTemplate = 'participant_management.html';
        this.participants = [];
        this.maps = [];
        this.addParticipantModal = null;
        this.experimentModal = null;
    }

    async loadData() {
        try {
            // 并行加载数据
            const [participants, maps] = await Promise.all([
                ParticipantsAPI.getAll(),
                this.loadMaps()
            ]);

            this.participants = participants || [];
            this.maps = maps || [];

            Logger.info(`Loaded ${this.participants.length} participants and ${this.maps.length} maps`);
        } catch (error) {
            Logger.error('Failed to load participant management data:', error);
            throw error;
        }
    }

    async loadMaps() {
        try {
            // 调用真实的地图API
            return await mapsAPI.getAll();
        } catch (error) {
            Logger.error('Failed to load maps:', error);
            // 如果API调用失败，使用mock数据作为fallback
            Logger.warn('Falling back to mock data for maps');
            return mapsAPI.getMockMaps();
        }
    }

    async renderData() {
        this.renderParticipantTable();
        this.initializeModals();
    }

    setupEventListeners() {
        super.setupEventListeners();

        // 添加被试按钮
        const addParticipantBtn = this.querySelector('#add-participant-btn');
        if (addParticipantBtn) {
            this.addEventListener(addParticipantBtn, 'click', () => this.handleAddParticipant());
        }

        // 开始实验按钮
        const startExperimentBtn = this.querySelector('#start-experiment-btn');
        if (startExperimentBtn) {
            this.addEventListener(startExperimentBtn, 'click', () => this.handleStartExperiment());
        }

        // 刷新数据按钮
        const refreshBtn = this.querySelector('#refresh-btn');
        if (refreshBtn) {
            this.addEventListener(refreshBtn, 'click', () => this.refreshData());
        }

        // 表格中的操作按钮（事件委托）
        const tableBody = this.querySelector('#participant-table-body');
        if (tableBody) {
            this.addEventListener(tableBody, 'click', (e) => this.handleTableAction(e));
        }
    }

    renderParticipantTable() {
        const tableBody = this.querySelector('#participant-table-body');
        if (!tableBody) {
            Logger.warn('Participant table body not found');
            return;
        }

        if (this.participants.length === 0) {
            tableBody.innerHTML = `
                <tr>
                    <td colspan="6" class="text-center text-muted py-4">
                        <i class="fas fa-users fa-2x mb-2"></i><br>
                        暂无被试数据<br>
                        <small>点击"添加被试"按钮开始添加</small>
                    </td>
                </tr>
            `;
            return;
        }

        const rows = this.participants.map(participant => {
            const ageText = `${participant.year}岁${participant.month}个月`;
            return `
                <tr data-participant-id="${participant.participantId}">
                    <td>
                        ${formatIdDisplayWithTitle(participant.participantId)}
                    </td>
                    <td>
                        <strong>${participant.participantName}</strong>
                    </td>
                    <td>${ageText}</td>
                    <td>${participant.parentName}</td>
                    <td>
                        <a href="tel:${participant.parentPhone}">${participant.parentPhone}</a>
                    </td>
                    <td>
                        <div class="btn-group btn-group-sm" role="group">
                            <button class="btn btn-outline-primary" 
                                    data-action="view" 
                                    data-participant-id="${participant.participantId}"
                                    title="查看详情">
                                <i class="fas fa-eye"></i>
                            </button>
                            <button class="btn btn-outline-secondary" 
                                    data-action="edit" 
                                    data-participant-id="${participant.participantId}"
                                    title="编辑">
                                <i class="fas fa-edit"></i>
                            </button>
                            <button class="btn btn-outline-danger" 
                                    data-action="delete" 
                                    data-participant-id="${participant.participantId}"
                                    title="删除">
                                <i class="fas fa-trash"></i>
                            </button>
                        </div>
                    </td>
                </tr>
            `;
        }).join('');

        tableBody.innerHTML = rows;
    }

    // 在 ParticipantManagement.js 中改进 initializeModals 方法
    async initializeModals() {
        try {
            // 确保模态框元素存在
            const addModalElement = document.getElementById('add-participant-modal');
            const experimentModalElement = document.getElementById('experiment-modal');

            if (!addModalElement) {
                throw new Error('Add participant modal element not found');
            }
            if (!experimentModalElement) {
                throw new Error('Experiment modal element not found');
            }

            // 初始化添加被试模态框
            this.addParticipantModal = new Modal('add-participant-modal');
            await this.addParticipantModal.render();
            this.addParticipantModal.onConfirm(() => this.handleConfirmAddParticipant());

            // 初始化实验模态框
            this.experimentModal = new Modal('experiment-modal');
            await this.experimentModal.render();
            this.experimentModal.onConfirm(() => this.handleConfirmStartExperiment());

            // 设置表单实时验证
            this.setupFormValidation();

            Logger.info('Modals initialized successfully');
        } catch (error) {
            Logger.error('Failed to initialize modals:', error);
            this.showError('模态框初始化失败', error.message);
        }
    }


    handleTableAction(event) {
        const button = event.target.closest('button[data-action]');
        if (!button) return;

        const action = button.getAttribute('data-action');
        const participantId = button.getAttribute('data-participant-id');
        const participant = this.participants.find(p => p.participantId === participantId);

        if (!participant) {
            this.showError('错误', '找不到指定的被试');
            return;
        }

        switch (action) {
            case 'view':
                this.handleViewParticipant(participant);
                break;
            case 'edit':
                this.handleEditParticipant(participant);
                break;
            case 'delete':
                this.handleDeleteParticipant(participant);
                break;
        }
    }

    handleViewParticipant(participant) {
        // TODO: 实现查看被试详情功能
        this.showInfo(`TODO: 显示被试 ${participant.participantName} 的详细信息`);
        Logger.info('View participant:', participant);
    }

    handleEditParticipant(participant) {
        // TODO: 实现编辑被试功能
        this.showInfo(`TODO: 编辑被试 ${participant.participantName}`);
        Logger.info('Edit participant:', participant);
    }

    async handleDeleteParticipant(participant) {
        try {
            const confirmed = await this.confirmDelete(participant.participantName);
            if (!confirmed) return;

            this.showLoading('正在删除被试...');

            await ParticipantsAPI.delete(participant.participantId);

            // 从本地数据中移除
            this.participants = this.participants.filter(p => p.participantId !== participant.participantId);

            this.hideLoading();
            this.showSuccess(`被试 ${participant.participantName} 已删除`);
            this.renderParticipantTable();

        } catch (error) {
            this.hideLoading();
            Logger.error('Failed to delete participant:', error);
            this.showError('删除失败', error.message);
        }
    }

    handleAddParticipant() {
        Logger.info('handleAddParticipant called');
        
        // 检查模态框元素是否存在
        const modalElement = document.getElementById('add-participant-modal');
        if (!modalElement) {
            Logger.error('Add participant modal element not found in DOM');
            this.showError('错误', '模态框元素未找到，请刷新页面重试');
            return;
        }
        
        if (!this.addParticipantModal) {
            Logger.warn('Modal instance not initialized, attempting to initialize...');
            // 尝试重新初始化
            this.initializeModals().then(() => {
                if (this.addParticipantModal) {
                    Logger.info('Modal initialized successfully, showing modal');
                    this.clearAddParticipantForm();
                    this.addParticipantModal.show();
                } else {
                    Logger.error('Failed to initialize modal after retry');
                    this.showError('错误', '模态框初始化失败，请刷新页面重试');
                }
            }).catch(error => {
                Logger.error('Error during modal initialization:', error);
                this.showError('错误', '模态框初始化失败：' + error.message);
            });
            return;
        }
    
        Logger.info('Showing existing modal');
        this.clearAddParticipantForm();
        this.addParticipantModal.show();
    }
    

    clearAddParticipantForm() {
        const form = document.querySelector('#add-participant-form');
        if (form) {
            form.reset();
            // 清除验证状态
            form.querySelectorAll('.is-invalid').forEach(input => {
                input.classList.remove('is-invalid');
            });
        }
    }

    async handleConfirmAddParticipant() {
        try {
            const participantData = this.getParticipantFormData();

            // 清除之前的验证状态
            this.clearValidationErrors();

            // 验证数据
            const errors = Validator.validateParticipant(participantData);
            if (errors.length > 0) {
                // 显示字段级别的验证错误
                this.displayValidationErrors(errors);
                this.showWarning(`表单验证失败：${errors.map(e => e.message).join('、')}`);
                return false; // 阻止模态框关闭
            }

            // 使用模态框内的loading，而不是全页面loading
            this.showModalLoading('正在添加被试...');

            const newParticipant = await ParticipantsAPI.create(participantData);

            // 添加到本地数据
            this.participants.unshift(newParticipant);

            this.hideModalLoading();
            this.showSuccess(`被试 ${newParticipant.participantName} 添加成功`);
            this.renderParticipantTable();

            return true; // 允许模态框关闭

        } catch (error) {
            this.hideModalLoading();
            Logger.error('Failed to add participant:', error);
            this.showError('添加失败', error.message);
            return false; // 阻止模态框关闭
        }
    }

    getParticipantFormData() {
        const yearValue = document.querySelector('#participant-year-input')?.value?.trim();
        const monthValue = document.querySelector('#participant-month-input')?.value?.trim();
        
        return {
            participantName: document.querySelector('#participant-name-input')?.value?.trim() || '',
            year: yearValue === '' ? null : parseInt(yearValue),
            month: monthValue === '' ? null : parseInt(monthValue),
            parentName: document.querySelector('#parent-name-input')?.value?.trim() || '',
            parentPhone: document.querySelector('#parent-phone-input')?.value?.trim() || '',
            diagnosticInfo: document.querySelector('#diagnostic-info-input')?.value?.trim() || '',
            preferenceInfo: document.querySelector('#preference-info-input')?.value?.trim() || ''
        };
    }

    clearValidationErrors() {
        const form = document.querySelector('#add-participant-form');
        if (form) {
            // 移除所有错误状态
            form.querySelectorAll('.is-invalid').forEach(input => {
                input.classList.remove('is-invalid');
            });
            
            // 移除所有错误消息
            form.querySelectorAll('.invalid-feedback').forEach(feedback => {
                feedback.remove();
            });
        }
    }

    displayValidationErrors(errors) {
        const fieldMapping = {
            'participantName': '#participant-name-input',
            'year': '#participant-year-input',
            'month': '#participant-month-input',
            'parentName': '#parent-name-input',
            'parentPhone': '#parent-phone-input'
        };

        errors.forEach(error => {
            const fieldSelector = fieldMapping[error.field];
            if (fieldSelector) {
                const field = document.querySelector(fieldSelector);
                if (field) {
                    // 添加错误样式
                    field.classList.add('is-invalid');
                    
                    // 添加错误消息
                    const existingFeedback = field.parentNode.querySelector('.invalid-feedback');
                    if (!existingFeedback) {
                        const feedback = document.createElement('div');
                        feedback.className = 'invalid-feedback';
                        feedback.textContent = error.message;
                        field.parentNode.appendChild(feedback);
                    }
                }
            }
        });
    }

    setupFormValidation() {
        // 延迟执行，确保模态框已经完全渲染
        setTimeout(() => {
            const formFields = [
                { id: '#participant-name-input', field: 'participantName' },
                { id: '#parent-name-input', field: 'parentName' },
                { id: '#parent-phone-input', field: 'parentPhone' },
                { id: '#participant-year-input', field: 'year' },
                { id: '#participant-month-input', field: 'month' }
            ];

            formFields.forEach(({ id, field }) => {
                const input = document.querySelector(id);
                if (input) {
                    // 添加实时验证
                    input.addEventListener('blur', () => {
                        this.validateSingleField(field, input);
                    });

                    // 清除错误状态当用户开始输入
                    input.addEventListener('input', () => {
                        if (input.classList.contains('is-invalid')) {
                            input.classList.remove('is-invalid');
                            const feedback = input.parentNode.querySelector('.invalid-feedback');
                            if (feedback) {
                                feedback.remove();
                            }
                        }
                    });
                } else {
                    Logger.warn(`Form field not found: ${id}`);
                }
            });
        }, 100);
    }

    validateSingleField(fieldName, inputElement) {
        const participantData = this.getParticipantFormData();
        const errors = Validator.validateParticipant(participantData);
        
        // 查找当前字段的错误
        const fieldError = errors.find(error => error.field === fieldName);
        
        // 清除当前字段的错误状态
        inputElement.classList.remove('is-invalid');
        const existingFeedback = inputElement.parentNode.querySelector('.invalid-feedback');
        if (existingFeedback) {
            existingFeedback.remove();
        }
        
        // 如果有错误，显示错误
        if (fieldError) {
            inputElement.classList.add('is-invalid');
            const feedback = document.createElement('div');
            feedback.className = 'invalid-feedback';
            feedback.textContent = fieldError.message;
            inputElement.parentNode.appendChild(feedback);
        }
    }

    handleStartExperiment() {
        if (!this.experimentModal) {
            this.showError('错误', '模态框未初始化');
            return;
        }

        if (this.participants.length === 0) {
            this.showWarning('请先添加被试');
            return;
        }

        if (this.maps.length === 0) {
            this.showWarning('请先创建地图');
            return;
        }

        this.populateExperimentModal();
        this.experimentModal.show();
    }

    populateExperimentModal() {
        // 填充被试选择器
        const participantSelect = document.querySelector('#participant-select');
        if (participantSelect) {
            const options = this.participants.map(p =>
                `<option value="${p.participantId}">${p.participantName} (${p.year}岁${p.month}个月)</option>`
            ).join('');
            participantSelect.innerHTML = options;
        }

        // 填充地图选择器
        const mapSelect = document.querySelector('#map-select');
        if (mapSelect) {
            const options = this.maps.map(m =>
                `<option value="${m.mapId}">${m.mapName}</option>`
            ).join('');
            mapSelect.innerHTML = options;
        }
    }

    async handleConfirmStartExperiment() {
        try {
            const participantId = document.querySelector('#participant-select')?.value;
            const mapId = document.querySelector('#map-select')?.value;

            if (!participantId || !mapId) {
                this.showWarning('请选择被试和地图');
                return false;
            }

            this.showLoading('正在开始实验...');

            const session = await SessionsAPI.create(participantId, mapId);

            if (session) {
                // 保存会话信息
                sessionStorage.setItem('currentSessionId', session.sessionId);
                sessionStorage.setItem('sessionStartTime', session.startTime);

                // 保存参与者和地图信息供显示使用
                const participant = this.participants.find(p => p.participantId === participantId);
                const map = this.maps.find(m => m.mapId === mapId);

                if (participant) {
                    sessionStorage.setItem('currentParticipantName', participant.participantName);
                }
                if (map) {
                    sessionStorage.setItem('currentMapName', map.mapName);
                }

                this.hideLoading();
                this.showSuccess(`实验已开始，会话ID: ${session.sessionId}`);

                // 触发会话开始事件
                this.emitEvent(EVENTS.SESSION_STARTED, session);

                // 导航到实验控制页面
                setTimeout(() => {
                    this.navigateTo('experiment_control');
                }, 1000);

                return true;
            } else {
                throw new Error('创建会话失败');
            }

        } catch (error) {
            this.hideLoading();
            Logger.error('Failed to start experiment:', error);
            this.showError('开始实验失败', error.message);
            return false;
        }
    }

    // 模态框内的loading方法
    showModalLoading(message = '处理中...') {
        const modal = this.addParticipantModal;
        if (!modal || !modal.container) return;

        const modalBody = modal.querySelector('.modal-body');
        const modalFooter = modal.querySelector('.modal-footer');
        
        if (modalBody && modalFooter) {
            // 禁用表单
            const form = modalBody.querySelector('form');
            if (form) {
                const inputs = form.querySelectorAll('input, select, textarea');
                inputs.forEach(input => input.disabled = true);
            }
            
            // 禁用按钮并显示loading
            const confirmBtn = modalFooter.querySelector('[data-confirm="modal"]');
            const cancelBtn = modalFooter.querySelector('[data-dismiss="modal"]');
            
            if (confirmBtn) {
                confirmBtn.disabled = true;
                confirmBtn.innerHTML = `
                    <span class="spinner-border spinner-border-sm" role="status"></span>
                    ${message}
                `;
            }
            
            if (cancelBtn) {
                cancelBtn.disabled = true;
            }
        }
    }

    hideModalLoading() {
        const modal = this.addParticipantModal;
        if (!modal || !modal.container) return;

        const modalBody = modal.querySelector('.modal-body');
        const modalFooter = modal.querySelector('.modal-footer');
        
        if (modalBody && modalFooter) {
            // 启用表单
            const form = modalBody.querySelector('form');
            if (form) {
                const inputs = form.querySelectorAll('input, select, textarea');
                inputs.forEach(input => input.disabled = false);
            }
            
            // 恢复按钮状态
            const confirmBtn = modalFooter.querySelector('[data-confirm="modal"]');
            const cancelBtn = modalFooter.querySelector('[data-dismiss="modal"]');
            
            if (confirmBtn) {
                confirmBtn.disabled = false;
                confirmBtn.innerHTML = '确认';
            }
            
            if (cancelBtn) {
                cancelBtn.disabled = false;
            }
        }
    }

    async beforeCleanup() {
        // 清理模态框
        if (this.addParticipantModal) {
            await this.addParticipantModal.cleanup();
        }
        if (this.experimentModal) {
            await this.experimentModal.cleanup();
        }
    }
}
