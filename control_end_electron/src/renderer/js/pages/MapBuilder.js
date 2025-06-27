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
import { formatIdDisplayWithTitle } from '../utils/idFormatter.js';

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
        this.cameraMonitor = null;
        
        // 目标点数据
        this.targets = [];
        
        // 模态框
        this.addTargetModal = null;
        this.editTargetModal = null;
        this.reorderModal = null;
        
        // 截图相关
        this.currentScreenshot = null;
        this.currentEnvironmentImage = null;
        this.cropSelection = {
            x: 0, y: 0, width: 0, height: 0
        };
        
        // 机器狗状态
        this.robotPosition = { x: 0, y: 0, z: 0 };
        this.robotOrientation = { w: 1, qx: 0, qy: 0, qz: 0 };
    }

    async beforeRender() {
        // 从URL参数或导航选项中获取地图ID
        // 支持从hash中读取参数（格式：#page?param=value）
        const urlParams = this.getURLParams();
        this.mapId = urlParams.get('mapId');
        
        if (!this.mapId) {
            this.showError('错误', '缺少地图ID参数');
            this.navigateToMaps();
            return;
        }

        try {
            this.currentMap = await mapsAPI.getById(this.mapId);
            this.isNewMap = false;
            
            // 加载现有目标点
            this.targets = await mapsAPI.getTargets(this.mapId);
            
        } catch (error) {
            Logger.error('加载地图失败:', error);
            this.showError('错误', '无法加载指定的地图');
            this.navigateToMaps();
            return;
        }
    }

    /**
     * 从URL hash中获取参数
     * 支持格式：#page?param=value
     */
    getURLParams() {
        const hash = window.location.hash;
        const queryIndex = hash.indexOf('?');
        
        if (queryIndex === -1) {
            return new URLSearchParams();
        }
        
        const queryString = hash.substring(queryIndex + 1);
        return new URLSearchParams(queryString);
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

        if (this.currentMap && mapInfo) {
            mapInfo.textContent = this.isNewMap 
                ? '正在构建新地图...' 
                : `正在构建地图: ${this.currentMap.mapName}`;
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
            
            // 获取摄像头监控组件
            this.cameraMonitor = this.querySelector('multi-camera-monitor');
            
            Logger.info('地图构建组件初始化完成');
            
        } catch (error) {
            Logger.error('组件初始化失败:', error);
            this.showError('初始化失败', '无法初始化控制组件');
        }
    }

    setupEventListeners() {
        super.setupEventListeners();

        // 页面操作按钮
        this.addEventListener(this.querySelector('#back-to-maps-btn'), 'click', () => {
            this.handleBackToMaps();
        });

        // 摄像头控制
        this.addEventListener(this.querySelector('#capture-btn'), 'click', () => {
            this.handleCaptureScreen();
        });

        this.addEventListener(this.querySelector('#toggle-cameras-btn'), 'click', () => {
            this.handleToggleCameras();
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

        // 模态框关闭按钮
        const addTargetModal = this.querySelector('#add-target-modal');
        if (addTargetModal) {
            const closeButton = addTargetModal.querySelector('.close');
            const cancelButton = addTargetModal.querySelector('.btn-secondary');
            if (closeButton) {
                this.addEventListener(closeButton, 'click', () => this.addTargetModal.hide());
            }
            if (cancelButton) {
                this.addEventListener(cancelButton, 'click', () => this.addTargetModal.hide());
            }
        }

        // 监听机器狗状态更新
        this.onEvent(EVENTS.ROBOT_STATUS_UPDATE, (data) => {
            this.updateRobotPosition(data);
        });

        // 裁剪工具事件
        this.initializeCropEvents();
    }

    // --- Start: Non-destructive UI Methods Override ---
    _showNotification(type, title, message) {
        let container = document.querySelector('.notification-container-global');
        if (!container) {
            container = document.createElement('div');
            container.className = 'notification-container-global';
            container.style.cssText = 'position: fixed; top: 20px; right: 20px; z-index: 2050; width: 350px;';
            document.body.appendChild(container);
        }

        const alertId = `notif-${Date.now()}`;
        const alertEl = document.createElement('div');
        alertEl.id = alertId;
        alertEl.className = `alert alert-${type} alert-dismissible fade show`;
        alertEl.setAttribute('role', 'alert');
        alertEl.innerHTML = `
            <h5 class="alert-heading">${title}</h5>
            <p class="mb-0">${message}</p>
            <button type="button" class="close" data-dismiss="alert" aria-label="Close">
                <span aria-hidden="true">&times;</span>
            </button>
        `;
        
        container.appendChild(alertEl);

        setTimeout(() => {
            const el = document.getElementById(alertId);
            if (el) {
                el.classList.remove('show');
                setTimeout(() => el.remove(), 150);
            }
        }, 5000);
    }

    showError(title, message) {
        Logger.error(`[UI Error] ${title}: ${message}`);
        this._showNotification('danger', title, message);
    }

    showWarning(title, message) {
        Logger.warn(`[UI Warning] ${title}: ${message}`);
        this._showNotification('warning', title, message);
    }

    showSuccess(title, message) {
        Logger.info(`[UI Success] ${title}: ${message}`);
        this._showNotification('success', title, message);
    }
    
    showLoading(message) {
        let overlay = document.querySelector('.global-loading-overlay');
        if (!overlay) {
            overlay = document.createElement('div');
            overlay.className = 'loading-overlay global-loading-overlay';
            overlay.style.position = 'fixed';
            overlay.style.zIndex = '2050';
            overlay.innerHTML = `
                <div class="loading-content">
                    <div class="loading-spinner"></div>
                    <p>${message || '正在加载...'}</p>
                </div>
            `;
            document.body.appendChild(overlay);
        }
        overlay.style.display = 'flex';
        if (message) {
            overlay.querySelector('p').textContent = message;
        }
    }

    hideLoading() {
        const overlay = document.querySelector('.global-loading-overlay');
        if (overlay) {
            overlay.style.display = 'none';
        }
    }
    // --- End: Non-destructive UI Methods Override ---

    async handleCaptureScreen() {
        this.showLoading('正在截取画面...');
        try {
            Logger.info('开始截取画面...');
            
            if (!this.cameraMonitor || typeof this.cameraMonitor.captureCurrentFrame !== 'function') {
                throw new Error('摄像头组件未就绪或不支持截图');
            }
            
            const timeoutPromise = new Promise((_, reject) => {
                setTimeout(() => reject(new Error('截图超时')), 5000);
            });
            
            Logger.info('调用captureCurrentFrame方法');
            const screenshot = await Promise.race([
                this.cameraMonitor.captureCurrentFrame(),
                timeoutPromise
            ]);

            if (!screenshot) {
                throw new Error('无法获取摄像头画面，返回内容为空');
            }
            
            Logger.info('截图成功，准备显示模态框');
            this.currentScreenshot = screenshot;
            this.currentEnvironmentImage = screenshot;
            
            this.hideLoading();
            this.showAddTargetModal();
            
        } catch (error) {
            this.hideLoading();
            Logger.error('截图失败:', error);
            this.showError('截图失败', `无法获取摄像头画面: ${error.message}。请检查摄像头连接。`);
        }
    }

    handleToggleCameras() {
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

    displayScreenshotInModal() {
        const canvas = this.querySelector('#crop-canvas');
        if (!canvas || !this.currentScreenshot) {
            Logger.error('displayScreenshotInModal: Canvas or screenshot missing.');
            return;
        }
        
        const ctx = canvas.getContext('2d');
        const img = new Image();
        
        img.onload = () => {
            Logger.info('displayScreenshotInModal: Image loaded successfully.');
            // 设置画布大小
            canvas.width = Math.min(img.width, 600);
            canvas.height = (canvas.width / img.width) * img.height;
            
            // 绘制图片
            ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
            
            // 初始化裁剪选择区域（默认选择中心区域）
            const defaultSize = Math.min(canvas.width, canvas.height) * 0.3;
            this.cropSelection = {
                x: (canvas.width - defaultSize) / 2,
                y: (canvas.height - defaultSize) / 2,
                width: defaultSize,
                height: defaultSize
            };
            
            this.updateCropSelection();
        };

        img.onerror = (err) => {
            Logger.error('displayScreenshotInModal: Failed to load screenshot image.', err);
            this.showError('显示截图失败', '无法加载截图，图片可能已损坏。');
        };
        
        img.src = this.currentScreenshot;
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
        if (rotationInput) rotationInput.value = this.calculateYawFromQuaternion().toFixed(2);
    }

    calculateYawFromQuaternion() {
        const { w, qx, qy, qz } = this.robotOrientation;
        // 计算偏航角（绕Z轴旋转）
        return Math.atan2(2 * (w * qz + qx * qy), 1 - 2 * (qy * qy + qz * qz));
    }

    async handleConfirmAddTarget() {
        try {
            // 确保有有效的地图ID
            if (!this.mapId) {
                this.showError('错误', '无效的地图ID，无法添加目标点。');
                return;
            }

            const targetData = this.getAddTargetFormData();
            
            // 验证数据
            const errors = this.validateTargetData(targetData);
            if (errors.length > 0) {
                this.showWarning('验证失败', errors.join('、'));
                return;
            }
            
            this.showLoading('正在添加目标点...');
            
            // 准备目标点数据
            const pose = {
                position: {
                    x: parseFloat(targetData.x),
                    y: parseFloat(targetData.y),
                    z: this.robotPosition.z
                },
                orientation: { ...this.robotOrientation }
            };
            
            // 准备图片文件
            const targetImgFile = await this.getCroppedImageFile(targetData.name + '_target');
            const envImgFile = await this.getEnvironmentImageFile(targetData.name + '_env');
            
            const apiData = {
                targetName: targetData.name,
                description: targetData.description,
                pose: pose,
                targetImgFile: targetImgFile,
                envImgFile: envImgFile
            };
            
            // 调用API创建目标点
            const newTarget = await mapsAPI.addTarget(this.mapId, apiData);
            
            // 更新本地数据
            this.targets.push(newTarget);
            this.renderTargetsList();
            this.updateTargetsCount();
            
            // 发送目标点更新事件
            EventBus.emit(EVENTS.TARGET_UPDATED, {
                mapId: this.mapId,
                action: 'add',
                targetId: newTarget.targetId
            });
            
            this.hideLoading();
            this.addTargetModal.hide();
            this.showSuccess('添加成功', `目标点 "${newTarget.targetName}" 已添加`);
            
        } catch (error) {
            this.hideLoading();
            Logger.error('添加目标点失败:', error);
            this.showError('添加失败', error.message);
        }
    }

    async getCroppedImageFile(filename) {
        const canvas = this.querySelector('#crop-canvas');
        if (!canvas) return null;
        
        // 创建新的画布用于裁剪
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
        
        // 转换为Blob
        return new Promise(resolve => {
            cropCanvas.toBlob(blob => {
                const file = new File([blob], `${filename}.png`, { type: 'image/png' });
                resolve(file);
            }, 'image/png');
        });
    }

    async getEnvironmentImageFile(filename) {
        if (!this.currentEnvironmentImage) return null;
        
        // 将base64转换为Blob
        const response = await fetch(this.currentEnvironmentImage);
        const blob = await response.blob();
        return new File([blob], `${filename}.png`, { type: 'image/png' });
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
        
        if (this.targets.some(t => t.targetName === data.name)) {
            errors.push('目标点名称已存在');
        }
        
        if (isNaN(parseFloat(data.x)) || isNaN(parseFloat(data.y))) {
            errors.push('位置信息格式不正确');
        }
        
        return errors;
    }

    async renderTargetsList() {
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

        // 按sequence排序
        const sortedTargets = [...this.targets].sort((a, b) => a.sequence - b.sequence);
        
        const targetsHtml = sortedTargets
            .map(target => this.renderTargetItem(target))
            .join('');

        targetsList.innerHTML = targetsHtml;
        this.updateTargetsCount();
    }

    renderTargetItem(target) {
        const getImageUrl = (path) => {
            if (!path) return '';
            // 根据系统规则动态构建URL
            // 后端基础URL: http://118.31.58.101:45001
            // 假设后端的静态文件服务端口是 8995，前端访问时需要+4，变成 48995
            const backendBaseUrl = 'http://118.31.58.101:48995';
            return `${backendBaseUrl}${path}`;
        };

        const targetImgUrl = getImageUrl(target.targetImgUrl);
        const envImgUrl = getImageUrl(target.envImgUrl);

        return `
            <div class="target-item" data-target-id="${target.targetId}">
                <div class="target-header">
                    <div class="target-order">${target.sequence}</div>
                    <div class="target-info">
                        <h6 class="target-name">${target.targetName}</h6>
                        <small class="target-position text-muted">
                            (${target.pose.position.x.toFixed(2)}, ${target.pose.position.y.toFixed(2)})
                        </small>
                    </div>
                    <div class="target-actions">
                        <button class="btn btn-sm btn-outline-primary" 
                                data-action="edit" data-target-id="${target.targetId}"
                                title="编辑">
                            <i class="fas fa-edit"></i>
                        </button>
                        <button class="btn btn-sm btn-outline-danger" 
                                data-action="delete" data-target-id="${target.targetId}"
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
                <div class="target-images">
                    ${targetImgUrl ? `
                        <div class="target-image">
                            <label class="small">目标图片</label>
                            <img src="${targetImgUrl}" alt="${target.targetName}" class="img-fluid">
                        </div>
                    ` : ''}
                    ${envImgUrl ? `
                        <div class="env-image">
                            <label class="small">环境图片</label>
                            <img src="${envImgUrl}" alt="环境" class="img-fluid">
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
    }

    handleTargetAction(event) {
        const button = event.target.closest('button[data-action]');
        if (!button) return;

        const action = button.getAttribute('data-action');
        const targetId = button.getAttribute('data-target-id');
        const target = this.targets.find(t => t.targetId === targetId);

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
        this.querySelector('#edit-target-name').value = target.targetName;
        this.querySelector('#edit-target-description').value = target.description || '';
        this.querySelector('#edit-target-id').value = target.targetId;

        this.editTargetModal.show();
    }

    async handleDeleteTarget(target) {
        const confirmed = await this.confirmDelete(target.targetName);
        if (!confirmed) return;

        try {
            this.showLoading('正在删除目标点...');
            
            await mapsAPI.deleteTarget(target.targetId);
            
            this.targets = this.targets.filter(t => t.targetId !== target.targetId);
            this.renderTargetsList();
            
            // 发送目标点更新事件
            EventBus.emit(EVENTS.TARGET_UPDATED, {
                mapId: this.mapId,
                action: 'delete',
                targetId: target.targetId
            });
            
            this.hideLoading();
            this.showSuccess('删除成功', `目标点 "${target.targetName}" 已删除`);
            
        } catch (error) {
            this.hideLoading();
            Logger.error('删除目标点失败:', error);
            this.showError('删除失败', error.message);
        }
    }

    async handleConfirmEditTarget() {
        try {
            const targetId = this.querySelector('#edit-target-id').value;
            const target = this.targets.find(t => t.targetId === targetId);
            if (!target) return;

            const newName = this.querySelector('#edit-target-name').value.trim();
            const newDescription = this.querySelector('#edit-target-description').value.trim();

            if (!newName) {
                this.showWarning('验证失败', '目标点名称不能为空');
                return;
            }

            if (newName !== target.targetName && this.targets.some(t => t.targetName === newName)) {
                this.showWarning('验证失败', '目标点名称已存在');
                return;
            }

            this.showLoading('正在更新目标点...');
            
            const updateData = {
                targetName: newName,
                description: newDescription,
                pose: target.pose
            };
            
            const updatedTarget = await mapsAPI.updateTarget(targetId, updateData);
            
            // 更新本地数据
            const index = this.targets.findIndex(t => t.targetId === targetId);
            if (index !== -1) {
                this.targets[index] = updatedTarget;
            }

            this.renderTargetsList();
            this.editTargetModal.hide();
            this.hideLoading();
            this.showSuccess('更新成功', `目标点 "${updatedTarget.targetName}" 已更新`);

        } catch (error) {
            this.hideLoading();
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

        try {
            this.showLoading('正在清空目标点...');
            
            // 逐个删除目标点
            for (const target of this.targets) {
                await mapsAPI.deleteTarget(target.targetId);
            }
            
            this.targets = [];
            this.renderTargetsList();
            
            this.hideLoading();
            this.showSuccess('清空成功', '所有目标点已清空');
            
        } catch (error) {
            this.hideLoading();
            Logger.error('清空目标点失败:', error);
            this.showError('清空失败', error.message);
        }
    }

    handleReorderTargets() {
        if (!this.reorderModal) return;
        this.renderSortableTargets();
        this.reorderModal.show();
    }

    renderSortableTargets() {
        const container = this.querySelector('#sortable-targets');
        if (!container) return;

        const sortedTargets = [...this.targets].sort((a, b) => a.sequence - b.sequence);
        
        const sortableHtml = sortedTargets
            .map(target => `
                <div class="sortable-target-item" data-target-id="${target.targetId}">
                    <div class="drag-handle"><i class="fas fa-grip-vertical"></i></div>
                    <div class="target-preview">
                        ${target.targetImgUrl ? 
                            `<img src="${target.targetImgUrl}" alt="${target.targetName}">` :
                            `<div class="no-image"><i class="fas fa-image"></i></div>`
                        }
                    </div>
                    <div class="target-info"><strong>${target.targetName}</strong></div>
                    <div class="target-order-number">${target.sequence}</div>
                </div>
            `).join('');

        container.innerHTML = sortableHtml;
        
        // 初始化拖拽排序
        this.initializeSortable(container);
    }

    initializeSortable(container) {
        // 简单的拖拽排序实现
        let draggedElement = null;
        
        container.addEventListener('dragstart', (e) => {
            draggedElement = e.target.closest('.sortable-target-item');
            e.dataTransfer.effectAllowed = 'move';
        });
        
        container.addEventListener('dragover', (e) => {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';
        });
        
        container.addEventListener('drop', (e) => {
            e.preventDefault();
            const dropTarget = e.target.closest('.sortable-target-item');
            if (dropTarget && draggedElement && dropTarget !== draggedElement) {
                const rect = dropTarget.getBoundingClientRect();
                const midpoint = rect.top + rect.height / 2;
                
                if (e.clientY < midpoint) {
                    container.insertBefore(draggedElement, dropTarget);
                } else {
                    container.insertBefore(draggedElement, dropTarget.nextSibling);
                }
            }
        });
        
        // 为每个项目添加draggable属性
        container.querySelectorAll('.sortable-target-item').forEach(item => {
            item.draggable = true;
        });
    }

    async handleConfirmReorderTargets() {
        try {
            const sortableItems = this.querySelectorAll('#sortable-targets .sortable-target-item');
            const newOrder = Array.from(sortableItems).map(item => 
                item.getAttribute('data-target-id')
            );
            
            this.showLoading('正在更新顺序...');
            
            await mapsAPI.updateTargetsOrder(this.mapId, newOrder);
            
            // 重新加载目标点列表
            this.targets = await mapsAPI.getTargets(this.mapId);
            this.renderTargetsList();
            
            this.reorderModal.hide();
            this.hideLoading();
            this.showSuccess('排序成功', '目标点顺序已更新');
            
        } catch (error) {
            this.hideLoading();
            Logger.error('更新顺序失败:', error);
            this.showError('排序失败', error.message);
        }
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
        
        if (statusData && statusData.orientation) {
            this.robotOrientation = { ...statusData.orientation };
        }
        
        const statusElement = this.querySelector('#robot-status');
        if (statusElement) {
            statusElement.textContent = statusData?.connected ? '已连接' : '未连接';
            statusElement.className = `status-indicator ${statusData?.connected ? 'connected' : 'disconnected'}`;
        }
    }

    initializeModals() {
        this.addTargetModal = new Modal('add-target-modal');
        this.editTargetModal = new Modal('edit-target-modal');
        this.reorderModal = new Modal('reorder-targets-modal');
    }

    initializeCropTool() {
        // 裁剪工具初始化在displayScreenshotInModal中完成
    }

    initializeCropEvents() {
        const cropOverlay = this.querySelector('#crop-overlay');
        const cropSelection = this.querySelector('#crop-selection');
        
        if (!cropOverlay || !cropSelection) return;
        
        let isDragging = false;
        let isResizing = false;
        let startX, startY;
        let startSelection;
        
        // 拖拽移动
        cropSelection.addEventListener('mousedown', (e) => {
            if (e.target.classList.contains('crop-handle')) return;
            
            isDragging = true;
            startX = e.clientX;
            startY = e.clientY;
            startSelection = { ...this.cropSelection };
            e.preventDefault();
        });
        
        // 调整大小
        cropSelection.querySelectorAll('.crop-handle').forEach(handle => {
            handle.addEventListener('mousedown', (e) => {
                isResizing = true;
                startX = e.clientX;
                startY = e.clientY;
                startSelection = { ...this.cropSelection };
                e.preventDefault();
                e.stopPropagation();
            });
        });
        
        document.addEventListener('mousemove', (e) => {
            if (isDragging) {
                const deltaX = e.clientX - startX;
                const deltaY = e.clientY - startY;
                
                this.cropSelection.x = Math.max(0, startSelection.x + deltaX);
                this.cropSelection.y = Math.max(0, startSelection.y + deltaY);
                
                this.updateCropSelection();
            } else if (isResizing) {
                // 简化的调整大小逻辑
                const deltaX = e.clientX - startX;
                const deltaY = e.clientY - startY;
                
                this.cropSelection.width = Math.max(50, startSelection.width + deltaX);
                this.cropSelection.height = Math.max(50, startSelection.height + deltaY);
                
                this.updateCropSelection();
            }
        });
        
        document.addEventListener('mouseup', () => {
            isDragging = false;
            isResizing = false;
        });
    }

    updateCropSelection() {
        const cropSelection = this.querySelector('#crop-selection');
        if (!cropSelection) return;
        
        cropSelection.style.left = this.cropSelection.x + 'px';
        cropSelection.style.top = this.cropSelection.y + 'px';
        cropSelection.style.width = this.cropSelection.width + 'px';
        cropSelection.style.height = this.cropSelection.height + 'px';
    }

    /**
     * 生成测试截图（当摄像头不可用时使用）
     */
    async generateTestScreenshot() {
        return new Promise((resolve) => {
            const canvas = document.createElement('canvas');
            const ctx = canvas.getContext('2d');
            
            canvas.width = 640;
            canvas.height = 480;
            
            // 绘制测试图像
            ctx.fillStyle = '#f0f0f0';
            ctx.fillRect(0, 0, canvas.width, canvas.height);
            
            // 绘制网格
            ctx.strokeStyle = '#ddd';
            ctx.lineWidth = 1;
            for (let x = 0; x < canvas.width; x += 50) {
                ctx.beginPath();
                ctx.moveTo(x, 0);
                ctx.lineTo(x, canvas.height);
                ctx.stroke();
            }
            for (let y = 0; y < canvas.height; y += 50) {
                ctx.beginPath();
                ctx.moveTo(0, y);
                ctx.lineTo(canvas.width, y);
                ctx.stroke();
            }
            
            // 绘制中心圆
            ctx.fillStyle = '#007bff';
            ctx.beginPath();
            ctx.arc(canvas.width / 2, canvas.height / 2, 50, 0, 2 * Math.PI);
            ctx.fill();
            
            // 添加文字
            ctx.fillStyle = '#333';
            ctx.font = '20px Arial';
            ctx.textAlign = 'center';
            ctx.fillText('测试图像', canvas.width / 2, canvas.height / 2 - 80);
            ctx.fillText('摄像头不可用', canvas.width / 2, canvas.height / 2 + 80);
            
            // 添加时间戳
            ctx.font = '14px Arial';
            ctx.fillText(new Date().toLocaleString(), canvas.width / 2, canvas.height - 20);
            
            const dataURL = canvas.toDataURL('image/png');
            Logger.info('生成测试截图成功');
            resolve(dataURL);
        });
    }

    async beforeCleanup() {
        if (this.robotControl) {
            await this.robotControl.cleanup();
        }
        Logger.info('地图构建页面已清理');
    }
}
