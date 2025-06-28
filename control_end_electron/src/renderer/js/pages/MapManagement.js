// 地图管理页面
import BasePage from './BasePage.js';
import Modal from '../components/modal.js';
import { EVENTS, PAGES } from '../utils/constants.js';
import { Validator } from '../utils/validator.js';
import Logger from '../utils/logger.js';
import mapsAPI from '../api/maps.js';
import EventBus from '../eventBus.js';
import { formatIdDisplayWithTitle } from '../utils/idFormatter.js';

export default class MapManagement extends BasePage {
    constructor() {
        super();
        this.pageTitle = '地图管理';
        this.viewTemplate = 'map_management.html';
        this.maps = [];
        this.createMapModal = null;
        this.editMapModal = null;
    }

    async loadData() {
        try {
            // 调用真实的地图API
            this.maps = await mapsAPI.getAll();
            Logger.info(`Loaded ${this.maps.length} maps`);
        } catch (error) {
            Logger.error('Failed to load maps:', error);
            // 如果API调用失败，使用mock数据作为fallback
            Logger.warn('Falling back to mock data');
            this.maps = mapsAPI.getMockMaps();
        }
    }

    async renderData() {
        this.renderMapTable();
        this.initializeModals();
    }

    setupEventListeners() {
        super.setupEventListeners();

        // 创建地图按钮
        const createMapBtn = this.querySelector('#create-map-btn');
        if (createMapBtn) {
            this.addEventListener(createMapBtn, 'click', () => this.handleCreateMap());
        }

        // 刷新数据按钮
        const refreshBtn = this.querySelector('#refresh-btn');
        if (refreshBtn) {
            this.addEventListener(refreshBtn, 'click', () => this.refreshData());
        }

        // 表格中的操作按钮（事件委托）
        const tableBody = this.querySelector('#map-table-body');
        if (tableBody) {
            this.addEventListener(tableBody, 'click', (e) => this.handleTableAction(e));
        }

        // 监听页面回到地图管理的事件，用于刷新目标点数量
        this.onEvent(EVENTS.TARGET_UPDATED, () => {
            this.refreshData();
        });

        // 监听页面显示事件，从地图构建页面返回时刷新数据
        this.onEvent(EVENTS.PAGE_SHOW, (data) => {
            if (data.from === PAGES.MAP_BUILDER) {
                this.refreshData();
            }
        });
    }

    renderMapTable() {
        const tableBody = this.querySelector('#map-table-body');
        if (!tableBody) {
            Logger.warn('Map table body not found');
            return;
        }

        if (this.maps.length === 0) {
            tableBody.innerHTML = `
                <tr>
                    <td colspan="5" class="text-center text-muted py-4">
                        <i class="fas fa-map fa-2x mb-2"></i><br>
                        暂无地图数据<br>
                        <small>点击"创建地图"按钮开始添加</small>
                    </td>
                </tr>
            `;
            return;
        }

        const rows = this.maps.map(map => {
            const targetCount = map.targetCount || 0;
            return `
                <tr data-map-id="${map.mapId}">
                    <td>
                        ${formatIdDisplayWithTitle(map.mapId)}
                    </td>
                    <td>
                        <strong>${map.mapName}</strong>
                    </td>
                    <td class="text-muted">${map.mapDescription || '无描述'}</td>
                    <td>
                        <span class="badge badge-${targetCount > 0 ? 'success' : 'secondary'}">
                            ${targetCount} 个目标点
                        </span>
                    </td>
                    <td>
                        <div class="btn-group btn-group-sm" role="group">
                            <button class="btn btn-outline-primary" 
                                    data-action="enter-builder" 
                                    data-map-id="${map.mapId}"
                                    title="进入构建页面">
                                <i class="fas fa-map-marked-alt"></i> 进入构建
                            </button>
                            <button class="btn btn-outline-danger" 
                                    data-action="delete" 
                                    data-map-id="${map.mapId}"
                                    title="删除地图">
                                <i class="fas fa-trash"></i> 删除
                            </button>
                        </div>
                    </td>
                </tr>
            `;
        }).join('');

        tableBody.innerHTML = rows;
    }

    initializeModals() {
        // 初始化创建地图模态框
        this.createMapModal = new Modal('create-map-modal');
        this.createMapModal.render().then(() => {
            this.createMapModal.onConfirm(() => this.handleConfirmCreateMap());
        }).catch(error => {
            Logger.error('Failed to initialize create map modal:', error);
        });
    }

    handleTableAction(event) {
        const button = event.target.closest('button[data-action]');
        if (!button) return;

        const action = button.getAttribute('data-action');
        const mapId = button.getAttribute('data-map-id');
        const map = this.maps.find(m => m.mapId === mapId);

        if (!map) {
            this.showError('错误', '找不到指定的地图');
            return;
        }

        switch (action) {
            case 'enter-builder':
                this.handleEnterBuilder(map);
                break;
            case 'delete':
                this.handleDeleteMap(map);
                break;
        }
    }

    handleEnterBuilder(map) {
        // 跳转到地图构建页面
        EventBus.emit(EVENTS.NAVIGATE_TO, { 
            page: PAGES.MAP_BUILDER,
            options: { mapId: map.mapId }
        });
        Logger.info('Navigate to map builder for map:', map);
    }

    async handleDeleteMap(map) {
        try {
            const confirmed = await this.confirmDelete(map.mapName);
            if (!confirmed) return;

            this.showLoading('正在删除地图...');

            // 调用真实的删除API
            await mapsAPI.delete(map.mapId);

            // 从本地数据中移除
            this.maps = this.maps.filter(m => m.mapId !== map.mapId);
            
            this.hideLoading();
            this.showSuccess(`地图 ${map.mapName} 已删除`);
            this.renderMapTable();

        } catch (error) {
            this.hideLoading();
            Logger.error('Failed to delete map:', error);
            this.showError('删除失败', error.message);
        }
    }

    handleCreateMap() {
        if (!this.createMapModal) {
            this.showError('错误', '模态框未初始化');
            return;
        }

        // 清空表单
        this.clearCreateMapForm();
        this.createMapModal.show();
    }

    clearCreateMapForm() {
        const form = this.querySelector('#create-map-form');
        if (form) {
            form.reset();
            // 清除验证状态
            form.querySelectorAll('.is-invalid').forEach(input => {
                input.classList.remove('is-invalid');
            });
        }
    }

    async handleConfirmCreateMap() {
        try {
            const mapData = this.getMapFormData();
            
            // 验证数据
            console.log('Form data:', mapData);
            const errors = Validator.validateMap(mapData);
            if (errors.length > 0) {
                this.showWarning(`表单验证失败：${errors.map(e => e.message).join('、')}`);
                return false; // 阻止模态框关闭
            }

            // 使用模态框内的loading，而不是全页面loading
            this.showModalLoading('正在创建地图...');

            // 调用真实的创建API
            const newMap = await mapsAPI.create(mapData);
            
            // 添加到本地数据
            this.maps.unshift(newMap);
            
            this.hideModalLoading();
            this.showSuccess(`地图 ${newMap.mapName} 创建成功`);
            this.renderMapTable();

            return true; // 允许模态框关闭

        } catch (error) {
            this.hideModalLoading();
            Logger.error('Failed to create map:', error);
            this.showError('创建失败', error.message);
            return false; // 阻止模态框关闭
        }
    }

    getMapFormData() {
        return {
            mapName: document.querySelector('#map-name-input')?.value?.trim() || '',
            mapDescription: document.querySelector('#map-desc-input')?.value?.trim() || ''
        };
    }


    // 模态框内的loading方法
    showModalLoading(message = '处理中...') {
        const modal = this.createMapModal;
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
        const modal = this.createMapModal;
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
        if (this.createMapModal) {
            await this.createMapModal.cleanup();
        }
        if (this.editMapModal) {
            await this.editMapModal.cleanup();
        }
    }
}
