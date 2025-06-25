// 参与者管理页面
import BasePage from './BasePage.js';
import Modal from '../components/modal.js';
import ParticipantsAPI from '../api/participants.js';
import SessionsAPI from '../api/sessions.js';
import { EVENTS } from '../utils/constants.js';
import { Validator } from '../utils/validator.js';
import Logger from '../utils/logger.js';

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
        // TODO: 实现地图API加载
        if (window.api?.getMaps) {
            return await window.api.getMaps();
        }
        return [
            { mapId: 'map1', mapName: '测试地图1', mapDescription: '用于测试的地图' },
            { mapId: 'map2', mapName: '测试地图2', mapDescription: '另一个测试地图' }
        ];
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
                        <code>${participant.participantId}</code>
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
        if (!this.addParticipantModal) {
            // 尝试重新初始化
            this.initializeModals().then(() => {
                if (this.addParticipantModal) {
                    this.clearAddParticipantForm();
                    this.addParticipantModal.show();
                } else {
                    this.showError('错误', '模态框初始化失败，请刷新页面重试');
                }
            });
            return;
        }
    
        this.clearAddParticipantForm();
        this.addParticipantModal.show();
    }
    

    clearAddParticipantForm() {
        const form = this.querySelector('#add-participant-form');
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

            // 验证数据
            const errors = Validator.validateParticipant(participantData);
            if (errors.length > 0) {
                this.showWarning(`表单验证失败：${errors.map(e => e.message).join('、')}`);
                return false; // 阻止模态框关闭
            }

            this.showLoading('正在添加被试...');

            const newParticipant = await ParticipantsAPI.create(participantData);

            // 添加到本地数据
            this.participants.unshift(newParticipant);

            this.hideLoading();
            this.showSuccess(`被试 ${newParticipant.participantName} 添加成功`);
            this.renderParticipantTable();

            return true; // 允许模态框关闭

        } catch (error) {
            this.hideLoading();
            Logger.error('Failed to add participant:', error);
            this.showError('添加失败', error.message);
            return false; // 阻止模态框关闭
        }
    }

    getParticipantFormData() {
        return {
            participantName: this.querySelector('#participant-name-input')?.value?.trim() || '',
            year: parseInt(this.querySelector('#participant-year-input')?.value) || 0,
            month: parseInt(this.querySelector('#participant-month-input')?.value) || 0,
            parentName: this.querySelector('#parent-name-input')?.value?.trim() || '',
            parentPhone: this.querySelector('#parent-phone-input')?.value?.trim() || '',
            diagnosticInfo: this.querySelector('#diagnostic-info-input')?.value?.trim() || '',
            preferenceInfo: this.querySelector('#preference-info-input')?.value?.trim() || ''
        };
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
        const participantSelect = this.querySelector('#participant-select');
        if (participantSelect) {
            const options = this.participants.map(p =>
                `<option value="${p.participantId}">${p.participantName} (${p.year}岁${p.month}个月)</option>`
            ).join('');
            participantSelect.innerHTML = options;
        }

        // 填充地图选择器
        const mapSelect = this.querySelector('#map-select');
        if (mapSelect) {
            const options = this.maps.map(m =>
                `<option value="${m.mapId}">${m.mapName}</option>`
            ).join('');
            mapSelect.innerHTML = options;
        }
    }

    async handleConfirmStartExperiment() {
        try {
            const participantId = this.querySelector('#participant-select')?.value;
            const mapId = this.querySelector('#map-select')?.value;

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
