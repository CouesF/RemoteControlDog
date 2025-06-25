// 地图构建页面 - 支持摄像头监控、机器狗控制、目标点管理
import BasePage from './BasePage.js';
import MultiCameraMonitor from '../components/MultiCameraMonitor.js';
import RobotControlPanel from '../components/RobotControlPanel.js';
import Modal from '../components/modal.js';
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
        this.cameraMonitor = null;
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
            // 初始化摄像头监控组件
            this.cameraMonitor = new MultiCameraMonitor('camera-monitor-container', {
                layout: 'grid',
                showControls: true,
                enableScreenshot: true
            });
            await this.cameraMonitor.render();
            
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
            this.showError('初始化失败', '无法初始化摄像头或控制组件');
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

        this.addEventListener(this.querySelector('#toggle-cameras-btn'), 'click', () => {
            this.handleToggleCameraLayout();
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
        try {
            if (!this.cameraMonitor) {
                this.showWarning('警告', '摄像头监控组件未初始化');
                return;
            }

            // 获取当前机器狗位置
            if (this.robotControl) {
                const controlState = this.robotControl.getControlState();
                // 这里应该从实际的机器狗状态获取位置信息
                // 暂时使用模拟数据
                this.robotPosition = {
                    x: Math.random() * 10 - 5, // -5 到 5
                    y: Math.random() * 10 - 5,
                    rotation: Math.random() * 360
                };
            }

            // 截取摄像头画面
            const screenshot = await this.cameraMonitor.takeScreenshot();
            if (screenshot) {
                this.currentScreenshot = screenshot;
                this.showAddTargetModal();
            } else {
                this.showWarning('警告', '无法截取摄像头画面，请检查摄像头连接');
            }

        } catch (error) {
            Logger.error('截取画面失败:', error);
            this.showError('截取失败', '无法截取当前画面');
        }
    }

    handleToggleCameraLayout() {
        if (this.cameraMonitor) {
            this.cameraMonitor.toggleLayout();
        }
    }

    showAddTargetModal() {
        if (!this.addTargetModal) {
            this.showError('错误', '添加目标点模态框未初始化');
            return;
        }

        // 清空表单
        this.clearAddTargetForm();
        
        // 显示截图
        this.displayScreenshotInModal();
        
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

    displayScreenshotInModal() {
        const canvas = this.querySelector('#crop-canvas');
        if (!canvas || !this.currentScreenshot) return;

        const ctx = canvas.getContext('2d');
        const img = new Image();
        
        img.onload = () => {
            // 设置画布大小
            const maxWidth = 600;
            const maxHeight = 400;
            const scale = Math.min(maxWidth / img.width, maxHeight / img.height);
            
            canvas.width = img.width * scale;
            canvas.height = img.height * scale;
            
            // 绘制图像
            ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
            
            // 初始化裁剪选择区域
            this.initializeCropSelection(canvas.width, canvas.height);
        };
        
        img.src = this.currentScreenshot;
    }

    initializeCropSelection(canvasWidth, canvasHeight) {
        // 默认选择中心区域
        const defaultWidth = canvasWidth * 0.6;
        const defaultHeight = canvasHeight * 0.6;
        const defaultX = (canvasWidth - defaultWidth) / 2;
        const defaultY = (canvasHeight - defaultHeight) / 2;
        
        this.cropSelection = {
            x: defaultX,
            y: defaultY,
            width: defaultWidth,
            height: defaultHeight
        };
        
        this.updateCropSelectionDisplay();
    }

    updateCropSelectionDisplay() {
        const selection = this.querySelector('#crop-selection');
        if (!selection) return;
        
        selection.style.left = this.cropSelection.x + 'px';
        selection.style.top = this.cropSelection.y + 'px';
        selection.style.width = this.cropSelection.width + 'px';
        selection.style.height = this.cropSelection.height + 'px';
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

            // 生成裁剪后的图像
            const croppedImage = await this.getCroppedImage();
            
            // 创建目标点
            const newTarget = {
                id: this.targetIdCounter++,
                name: targetData.name,
                description: targetData.description,
                position: {
                    x: parseFloat(targetData.x),
                    y: parseFloat(targetData.y),
                    rotation: parseFloat(targetData.rotation)
                },
                image: croppedImage,
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

    async getCroppedImage() {
        const canvas = this.querySelector('#crop-canvas');
        if (!canvas) throw new Error('画布未找到');
        
        // 创建新画布用于裁剪
        const cropCanvas = document.createElement('canvas');
        const cropCtx = cropCanvas.getContext('2d');
        
        cropCanvas.width = this.cropSelection.width;
        cropCanvas.height = this.cropSelection.height;
        
        // 从原画布裁剪图像
        cropCtx.drawImage(
            canvas,
            this.cropSelection.x, this.cropSelection.y,
            this.cropSelection.width, this.cropSelection.height,
            0, 0,
            this.cropSelection.width, this.cropSelection.height
        );
        
        return cropCanvas.toDataURL('image/jpeg', 0.8);
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

            // 验证名称
            if (!newName) {
                this.showWarning('验证失败', '目标点名称不能为空');
                return;
            }

            if (newName !== target.name && this.targets.some(t => t.name === newName)) {
                this.showWarning('验证失败', '目标点名称已存在');
                return;
            }

            // 更新目标点
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

        // 渲染可排序的目标点列表
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
                    <div class="drag-handle">
                        <i class="fas fa-grip-vertical"></i>
                    </div>
                    <div class="target-preview">
                        <img src="${target.image}" alt="${target.name}">
                    </div>
                    <div class="target-info">
                        <strong>${target.name}</strong>
                        <small class="text-muted d-block">
                            (${target.position.x.toFixed(2)}, ${target.position.y.toFixed(2)})
                        </small>
                    </div>
                    <div class="target-order-number">
                        ${target.order}
                    </div>
                </div>
            `)
            .join('');

        container.innerHTML = sortableHtml;
        
        // 这里可以集成拖拽排序库，如 Sortable.js
        // 暂时使用简单的上下移动按钮
    }

    async handleConfirmReorderTargets() {
        // 获取新的排序
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

        // 更新操作按钮状态
        const clearBtn = this.querySelector('#clear-all-targets-btn');
        const reorderBtn = this.querySelector('#reorder-targets-btn');
        
        if (clearBtn) clearBtn.disabled = this.targets.length === 0;
        if (reorderBtn) reorderBtn.disabled = this.targets.length < 2;
    }

    async handleSaveMap() {
        try {
            if (this.targets.length === 0) {
                const confirmed = await this.confirmAction(
                    '保存确认',
                    '当前地图没有目标点，确定要保存吗？'
                );
                if (!confirmed) return;
            }

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
            this.showSuccess(
                '保存成功', 
                `地图 "${savedMap.mapName}" 已保存，包含 ${this.targets.length} 个目标点`
            );

            // 更新当前地图信息
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
        if (this.hasUnsavedChanges()) {
            this.confirmAction(
                '未保存的更改',
                '您有未保存的更改，确定要离开吗？'
            ).then(confirmed => {
                if (confirmed) {
                    this.navigateToMaps();
                }
            });
        } else {
            this.navigateToMaps();
        }
    }

    navigateToMaps() {
        EventBus.emit(EVENTS.NAVIGATE_TO, { 
            page: PAGES.MAP_MANAGEMENT 
        });
    }

    hasUnsavedChanges() {
        // 简单的更改检测逻辑
        if (this.isNewMap && this.targets.length > 0) return true;
        if (!this.isNewMap && this.currentMap) {
            const originalTargetCount = this.currentMap.targets?.length || 0;
            return this.targets.length !== originalTargetCount;
        }
        return false;
    }

    updateRobotPosition(statusData) {
        if (statusData && statusData.position) {
            this.robotPosition = { ...statusData.position };
        }
        
        // 更新状态显示
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
        // 初始化添加目标点模态框
        this.addTargetModal = new Modal('add-target-modal');
        this.addTargetModal.render().catch(error => {
            Logger.error('初始化添加目标点模态框失败:', error);
        });

        // 初始化编辑目标点模态框
        this.editTargetModal = new Modal('edit-target-modal');
        this.editTargetModal.render().catch(error => {
            Logger.error('初始化编辑目标点模态框失败:', error);
        });

        // 初始化重排序模态框
        this.reorderModal = new Modal('reorder-targets-modal');
        this.reorderModal.render().catch(error => {
            Logger.error('初始化重排序模态框失败:', error);
        });
    }

    initializeCropTool() {
        // 初始化图像裁剪工具
        const cropOverlay = this.querySelector('#crop-overlay');
        const cropSelection = this.querySelector('#crop-selection');
        
        if (!cropOverlay || !cropSelection) return;

        let isDragging = false;
        let dragStart = { x: 0, y: 0 };
        let selectionStart = { x: 0, y: 0, width: 0, height: 0 };

        // 鼠标事件处理
        cropSelection.addEventListener('mousedown', (e) => {
            isDragging = true;
            dragStart = { x: e.clientX, y: e.clientY };
            selectionStart = { ...this.cropSelection };
            e.preventDefault();
        });

        document.addEventListener('mousemove', (e) => {
            if (!isDragging) return;
            
            const deltaX = e.clientX - dragStart.x;
            const deltaY = e.clientY - dragStart.y;
            
            this.cropSelection.x = selectionStart.x + deltaX;
            this.cropSelection.y = selectionStart.y + deltaY;
            
            this.updateCropSelectionDisplay();
        });

        document.addEventListener('mouseup', () => {
            isDragging = false;
        });
    }

    async beforeCleanup() {
        // 清理组件
        if (this.cameraMonitor) {
            await this.cameraMonitor.cleanup();
        }
        
        if (this.robotControl) {
            await this.robotControl.cleanup();
        }

        // 清理模态框
        if (this.addTargetModal) {
            await this.addTargetModal.cleanup();
        }
        
        if (this.editTargetModal) {
            await this.editTargetModal.cleanup();
        }
        
        if (this.reorderModal) {
            await this.reorderModal.cleanup();
        }

        Logger.info('地图构建页面已清理');
    }
}
