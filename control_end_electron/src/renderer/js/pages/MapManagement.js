// 地图管理页面
import BasePage from './BasePage.js';
import Modal from '../components/modal.js';
import { EVENTS } from '../utils/constants.js';
import { Validator } from '../utils/validator.js';
import Logger from '../utils/logger.js';

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
            // TODO: 实现真实的地图API调用
            if (window.api?.getMaps) {
                this.maps = await window.api.getMaps();
            } else {
                this.maps = this.getMockMaps();
            }
            
            Logger.info(`Loaded ${this.maps.length} maps`);
        } catch (error) {
            Logger.error('Failed to load maps:', error);
            throw error;
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
                        <code>${map.mapId}</code>
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
                                    data-action="edit-targets" 
                                    data-map-id="${map.mapId}"
                                    title="编辑目标点">
                                <i class="fas fa-map-marker-alt"></i>
                            </button>
                            <button class="btn btn-outline-secondary" 
                                    data-action="edit" 
                                    data-map-id="${map.mapId}"
                                    title="编辑地图">
                                <i class="fas fa-edit"></i>
                            </button>
                            <button class="btn btn-outline-info" 
                                    data-action="view" 
                                    data-map-id="${map.mapId}"
                                    title="查看详情">
                                <i class="fas fa-eye"></i>
                            </button>
                            <button class="btn btn-outline-danger" 
                                    data-action="delete" 
                                    data-map-id="${map.mapId}"
                                    title="删除地图">
                                <i class="fas fa-trash"></i>
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
            case 'view':
                this.handleViewMap(map);
                break;
            case 'edit':
                this.handleEditMap(map);
                break;
            case 'edit-targets':
                this.handleEditTargets(map);
                break;
            case 'delete':
                this.handleDeleteMap(map);
                break;
        }
    }

    handleViewMap(map) {
        // TODO: 实现查看地图详情功能
        this.showInfo(`TODO: 显示地图 ${map.mapName} 的详细信息`);
        Logger.info('View map:', map);
    }

    handleEditMap(map) {
        // TODO: 实现编辑地图功能
        this.showInfo(`TODO: 编辑地图 ${map.mapName}`);
        Logger.info('Edit map:', map);
    }

    handleEditTargets(map) {
        // TODO: 实现编辑目标点功能
        this.showInfo(`TODO: 编辑地图 ${map.mapName} 的目标点`);
        Logger.info('Edit targets for map:', map);
    }

    async handleDeleteMap(map) {
        try {
            const confirmed = await this.confirmDelete(map.mapName);
            if (!confirmed) return;

            this.showLoading('正在删除地图...');

            // TODO: 实现真实的删除API调用
            Logger.info(`TODO: Delete map ${map.mapId}`);

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

            this.showLoading('正在创建地图...');

            // TODO: 实现真实的创建API调用
            const newMap = await this.createMapMock(mapData);
            
            // 添加到本地数据
            this.maps.unshift(newMap);
            
            this.hideLoading();
            this.showSuccess(`地图 ${newMap.mapName} 创建成功`);
            this.renderMapTable();

            return true; // 允许模态框关闭

        } catch (error) {
            this.hideLoading();
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

    // Mock数据和方法（临时使用）
    getMockMaps() {
        return [
            {
                mapId: 'uuid-m1',
                mapName: '公园北区',
                mapDescription: '适合初级训练的开阔草地',
                targetCount: 6
            },
            {
                mapId: 'uuid-m2',
                mapName: '小区花园',
                mapDescription: '有更多互动元素的复杂环境',
                targetCount: 10
            },
            {
                mapId: 'uuid-m3',
                mapName: '室内训练场',
                mapDescription: '室内环境，适合恶劣天气时使用',
                targetCount: 4
            }
        ];
    }

    async createMapMock(mapData) {
        // TODO: 实现真实API调用
        if (window.api?.createMap) {
            return await window.api.createMap(mapData);
        }
        
        return {
            ...mapData,
            mapId: `uuid-m${Date.now()}`,
            targetCount: 0
        };
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
