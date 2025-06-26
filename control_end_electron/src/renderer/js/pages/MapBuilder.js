// 地图构建页面 - 支持摄像头监控、机器狗控制、目标点管理
import BasePage from './BasePage.js';
import RobotControlPanel from '../components/RobotControlPanel.js';
import Modal from '../components/modal.js';
import '../components/camera/MultiCameraMonitor.js';
import { EVENTS, PAGES } from '../utils/constants.js';
import { Validator } from '../utils/validator.js';
import Logger from '../utils/logger.js';
import mapsAPI from '../api/maps.js';
import EventBus from '../eventBus.js';

export default class MapBuilder extends BasePage {
    constructor() {
        super();
        this.pageTitle = '地图构建';
        this.viewTemplate = 'map_builder.html';
        
        // 当前地图信息
        this.currentMap = null;
        this.mapId = null;
        this.isNewMap = false;
        
        // 组件实例
        this.robotControl = null;
        
        // 目标点数据
        this.targets = [];
        this.targetIdCounter = 1;
        
        // 模态框
        this.addTargetModal = null;
        this.editTargetModal = null;
        this.reorderModal = null;
        
        // 截图相关
        this.currentScreenshot = null;
        this.cropSelection = {
            x: 0, y: 0, width: 0, height: 0
        };
        
        // 机器狗状态
        this.robotPosition = { x: 0, y: 0, rotation: 0 };
    }

    async beforeRender() {
        // 从URL参数或导航选项中获取地图ID
        const urlParams = new URLSearchParams(window.location.search);
        this.mapId = urlParams.get('mapId');
        
        if (this.mapId) {
            try {
                this.currentMap = await mapsAPI.getById(this.mapId);
                this.isNewMap = false;
                
                // 加载现有目标点
                if (this.currentMap.targets) {
                    this.targets = [...this.currentMap.targets];
                    this.targetIdCounter = Math.max(...this.targets.map(t => t.id), 0) + 1;
                }
            } catch (error) {
                Logger.error('加载地图失败:', error);
                this.showError('错误', '无法加载指定的地图');
                return;
            }
        } else {
            // 新建地图模式
            this.isNewMap = true;
            this.currentMap = {
                mapName: '新建地图',
                mapDescription: '',
                targets: []
            };
        }
    }

    async renderData() {
        this.updateMapInfo();
        await this.initializeComponents();
        this.renderTargetsList();
        this.initializeModals();
        this.initializeCropTool();
    }

    updateMapInfo() {
        const mapInfo = this.querySelector('#map-info');
        if (mapInfo && this.currentMap) {
            mapInfo.textContent = this.isNewMap 
                ? '正在构建新地图...' 
                : `正在编辑地图: ${this.currentMap.mapName}`;
        }
    }

    async initializeComponents() {
        try {
            // 初始化机器狗控制组件
            this.robotControl = new RobotControlPanel('robot-control-container', {
                showJoystick: true,
                showStateControls: true,
                showObjectControls: true,
                enableKeyboard: true
            });
            await this.robotControl.render();
            
            Logger.info('地图构建组件初始化完成');
            
        } catch (error) {
            Logger.error('组件初始化失败:', error);
            this.showError('初始化失败', '无法初始化控制组件');
        }
    }

    setupEventListeners() {
        super.setupEventListeners();

        // 页面操作按钮
        this.addEventListener(this.querySelector('#save-map-btn'), 'click', () => {
            this.handleSaveMap();
        });

        this.addEventListener(this.querySelector('#back-to-maps-btn'), 'click', () => {
            this.handleBackToMaps();
        });

        // 摄像头控制
        this.addEventListener(this.querySelector('#capture-btn'), 'click', () => {
            this.handleCaptureScreen();
        });

        // 目标点操作
        this.addEventListener(this.querySelector('#clear-all-targets-btn'), 'click', () => {
            this.handleClearAllTargets();
        });

        this.addEventListener(this.querySelector('#reorder-targets-btn'), 'click', () => {
            this.handleReorderTargets();
        });

        // 目标点列表事件委托
        this.addEventListener(this.querySelector('#targets-list'), 'click', (e) => {
            this.handleTargetAction(e);
        });

        // 模态框确认按钮
        this.addEventListener(this.querySelector('#confirm-add-target'), 'click', () => {
            this.handleConfirmAddTarget();
        });

        this.addEventListener(this.querySelector('#confirm-edit-target'), 'click', () => {
            this.handleConfirmEditTarget();
        });

        this.addEventListener(this.querySelector('#confirm-reorder-targets'), 'click', () => {
            this.handleConfirmReorderTargets();
        });

        // 监听机器狗状态更新
        this.onEvent(EVENTS.ROBOT_STATUS_UPDATE, (data) => {
            this.updateRobotPosition(data);
        });

        // 监听摄像头截图事件
        this.onEvent('camera_screenshot_taken', (data) => {
            this.handleScreenshotTaken(data);
        });
    }

    async handleCaptureScreen() {
        // This functionality needs to be re-implemented to work with the new camera system.
        // For now, we can use a placeholder.
        this.showWarning('功能待定', '截图功能正在重构中。');
    }

    showAddTargetModal() {
        if (!this.addTargetModal) {
            this.showError('错误', '添加目标点模态框未初始化');
            return;
        }

        // 清空表单
        this.clearAddTargetForm();
        
        // 填充位置信息
        this.fillPositionInfo();
        
        this.addTargetModal.show();
    }

    clearAddTargetForm() {
        const form = this.querySelector('#add-target-form');
        if (form) {
            form.reset();
            form.querySelectorAll('.is-invalid').forEach(input => {
                input.classList.remove('is-invalid');
            });
        }
    }

    fillPositionInfo() {
        const xInput = this.querySelector('#target-x');
        const yInput = this.querySelector('#target-y');
        const rotationInput = this.querySelector('#target-rotation');
        
        if (xInput) xInput.value = this.robotPosition.x.toFixed(2);
        if (yInput) yInput.value = this.robotPosition.y.toFixed(2);
        if (rotationInput) rotationInput.value = this.robotPosition.rotation.toFixed(2);
    }

    async handleConfirmAddTarget() {
        try {
            const targetData = this.getAddTargetFormData();
            
            // 验证数据
            const errors = this.validateTargetData(targetData);
            if (errors.length > 0) {
                this.showWarning('验证失败', errors.join('、'));
                return;
            }
            
            const newTarget = {
                id: this.targetIdCounter++,
                name: targetData.name,
                description: targetData.description,
                position: {
                    x: parseFloat(targetData.x),
                    y: parseFloat(targetData.y),
                    rotation: parseFloat(targetData.rotation)
                },
                image: 'path/to/placeholder.jpg', // Placeholder image
                order: this.targets.length + 1,
                createdAt: new Date().toISOString()
            };

            this.targets.push(newTarget);
            this.renderTargetsList();
            this.updateTargetsCount();
            
            this.addTargetModal.hide();
            this.showSuccess('添加成功', `目标点 "${newTarget.name}" 已添加`);
            
        } catch (error) {
            Logger.error('添加目标点失败:', error);
            this.showError('添加失败', error.message);
        }
    }

    getAddTargetFormData() {
        return {
            name: this.querySelector('#target-name')?.value?.trim() || '',
            description: this.querySelector('#target-description')?.value?.trim() || '',
            x: this.querySelector('#target-x')?.value || '0',
            y: this.querySelector('#target-y')?.value || '0',
            rotation: this.querySelector('#target-rotation')?.value || '0'
        };
    }

    validateTargetData(data) {
        const errors = [];
        
        if (!data.name) {
            errors.push('目标点名称不能为空');
        }
        
        if (this.targets.some(t => t.name === data.name)) {
            errors.push('目标点名称已存在');
        }
        
        if (isNaN(parseFloat(data.x)) || isNaN(parseFloat(data.y)) || isNaN(parseFloat(data.rotation))) {
            errors.push('位置信息格式不正确');
        }
        
        return errors;
    }

    renderTargetsList() {
        const targetsList = this.querySelector('#targets-list');
        if (!targetsList) return;

        if (this.targets.length === 0) {
            targetsList.innerHTML = `
                <div class="empty-targets">
                    <i class="fas fa-map-marker-alt fa-2x text-muted"></i>
                    <p class="text-muted mt-2">暂无目标点</p>
                    <small class="text-muted">使用"截取当前画面"按钮添加目标点</small>
                </div>
            `;
            return;
        }

        const targetsHtml = this.targets
            .sort((a, b) => a.order - b.order)
            .map(target => this.renderTargetItem(target))
            .join('');

        targetsList.innerHTML = targetsHtml;
    }

    renderTargetItem(target) {
        return `
            <div class="target-item" data-target-id="${target.id}">
                <div class="target-header">
                    <div class="target-order">${target.order}</div>
                    <div class="target-info">
                        <h6 class="target-name">${target.name}</h6>
                        <small class="target-position text-muted">
                            (${target.position.x.toFixed(2)}, ${target.position.y.toFixed(2)})
                        </small>
                    </div>
                    <div class="target-actions">
                        <button class="btn btn-sm btn-outline-primary" 
                                data-action="edit" data-target-id="${target.id}"
                                title="编辑">
                            <i class="fas fa-edit"></i>
                        </button>
                        <button class="btn btn-sm btn-outline-danger" 
                                data-action="delete" data-target-id="${target.id}"
                                title="删除">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                </div>
                ${target.description ? `
                    <div class="target-description">
                        <small class="text-muted">${target.description}</small>
                    </div>
                ` : ''}
                <div class="target-image">
                    <img src="${target.image}" alt="${target.name}" class="img-fluid">
                </div>
            </div>
        `;
    }

    handleTargetAction(event) {
        const button = event.target.closest('button[data-action]');
        if (!button) return;

        const action = button.getAttribute('data-action');
        const targetId = parseInt(button.getAttribute('data-target-id'));
        const target = this.targets.find(t => t.id === targetId);

        if (!target) return;

        switch (action) {
            case 'edit':
                this.handleEditTarget(target);
                break;
            case 'delete':
                this.handleDeleteTarget(target);
                break;
        }
    }

    handleEditTarget(target) {
        if (!this.editTargetModal) return;

        // 填充编辑表单
        this.querySelector('#edit-target-name').value = target.name;
        this.querySelector('#edit-target-description').value = target.description || '';
        this.querySelector('#edit-target-id').value = target.id;

        this.editTargetModal.show();
    }

    async handleDeleteTarget(target) {
        const confirmed = await this.confirmDelete(target.name);
        if (!confirmed) return;

        this.targets = this.targets.filter(t => t.id !== target.id);
        this.renderTargetsList();
        this.updateTargetsCount();
        
        this.showSuccess('删除成功', `目标点 "${target.name}" 已删除`);
    }

    async handleConfirmEditTarget() {
        try {
            const targetId = parseInt(this.querySelector('#edit-target-id').value);
            const target = this.targets.find(t => t.id === targetId);
            if (!target) return;

            const newName = this.querySelector('#edit-target-name').value.trim();
            const newDescription = this.querySelector('#edit-target-description').value.trim();

            if (!newName) {
                this.showWarning('验证失败', '目标点名称不能为空');
                return;
            }

            if (newName !== target.name && this.targets.some(t => t.name === newName)) {
                this.showWarning('验证失败', '目标点名称已存在');
                return;
            }

            target.name = newName;
            target.description = newDescription;

            this.renderTargetsList();
            this.editTargetModal.hide();
            this.showSuccess('更新成功', `目标点 "${target.name}" 已更新`);

        } catch (error) {
            Logger.error('编辑目标点失败:', error);
            this.showError('编辑失败', error.message);
        }
    }

    async handleClearAllTargets() {
        if (this.targets.length === 0) return;

        const confirmed = await this.confirmAction(
            '清空确认',
            `确定要清空所有 ${this.targets.length} 个目标点吗？此操作不可撤销。`
        );
        
        if (!confirmed) return;

        this.targets = [];
        this.renderTargetsList();
        this.updateTargetsCount();
        
        this.showSuccess('清空成功', '所有目标点已清空');
    }

    handleReorderTargets() {
        if (!this.reorderModal) return;
        this.renderSortableTargets();
        this.reorderModal.show();
    }

    renderSortableTargets() {
        const container = this.querySelector('#sortable-targets');
        if (!container) return;

        const sortableHtml = this.targets
            .sort((a, b) => a.order - b.order)
            .map(target => `
                <div class="sortable-target-item" data-target-id="${target.id}">
                    <div class="drag-handle"><i class="fas fa-grip-vertical"></i></div>
                    <div class="target-preview"><img src="${target.image}" alt="${target.name}"></div>
                    <div class="target-info"><strong>${target.name}</strong></div>
                    <div class="target-order-number">${target.order}</div>
                </div>
            `).join('');

        container.innerHTML = sortableHtml;
    }

    async handleConfirmReorderTargets() {
        const sortableItems = this.querySelectorAll('#sortable-targets .sortable-target-item');
        
        sortableItems.forEach((item, index) => {
            const targetId = parseInt(item.getAttribute('data-target-id'));
            const target = this.targets.find(t => t.id === targetId);
            if (target) {
                target.order = index + 1;
            }
        });

        this.renderTargetsList();
        this.reorderModal.hide();
        this.showSuccess('排序成功', '目标点顺序已更新');
    }

    updateTargetsCount() {
        const countElement = this.querySelector('#targets-count');
        if (countElement) {
            countElement.textContent = `${this.targets.length} 个目标点`;
        }

        const clearBtn = this.querySelector('#clear-all-targets-btn');
        const reorderBtn = this.querySelector('#reorder-targets-btn');
        
        if (clearBtn) clearBtn.disabled = this.targets.length === 0;
        if (reorderBtn) reorderBtn.disabled = this.targets.length < 2;
    }

    async handleSaveMap() {
        try {
            this.showLoading('正在保存地图...');

            const mapData = {
                mapName: this.currentMap.mapName,
                mapDescription: this.currentMap.mapDescription,
                targets: this.targets,
                targetCount: this.targets.length,
                updatedAt: new Date().toISOString()
            };

            let savedMap;
            if (this.isNewMap) {
                savedMap = await mapsAPI.create(mapData);
            } else {
                savedMap = await mapsAPI.update(this.mapId, mapData);
            }

            this.hideLoading();
            this.showSuccess('保存成功', `地图 "${savedMap.mapName}" 已保存`);

            this.currentMap = savedMap;
            this.mapId = savedMap.mapId;
            this.isNewMap = false;
            this.updateMapInfo();

        } catch (error) {
            this.hideLoading();
            Logger.error('保存地图失败:', error);
            this.showError('保存失败', error.message);
        }
    }

    handleBackToMaps() {
        this.navigateToMaps();
    }

    navigateToMaps() {
        EventBus.emit(EVENTS.NAVIGATE_TO, { page: PAGES.MAP_MANAGEMENT });
    }

    updateRobotPosition(statusData) {
        if (statusData && statusData.position) {
            this.robotPosition = { ...statusData.position };
        }
        
        const statusElement = this.querySelector('#robot-status');
        if (statusElement) {
            statusElement.textContent = statusData?.connected ? '已连接' : '未连接';
            statusElement.className = `status-indicator ${statusData?.connected ? 'connected' : 'disconnected'}`;
        }
    }

    handleScreenshotTaken(data) {
        if (data && data.imageData) {
            this.currentScreenshot = data.imageData;
            this.showAddTargetModal();
        }
    }

    initializeModals() {
        this.addTargetModal = new Modal('add-target-modal');
        this.editTargetModal = new Modal('edit-target-modal');
        this.reorderModal = new Modal('reorder-targets-modal');
    }

    initializeCropTool() {
        // Placeholder for crop tool logic
    }

    async beforeCleanup() {
        if (this.robotControl) {
            await this.robotControl.cleanup();
        }
        Logger.info('地图构建页面已清理');
    }
}
