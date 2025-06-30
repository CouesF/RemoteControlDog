// 实验控制页面
import BasePage from './BasePage.js';
import RobotDogController from '../components/RobotDogController.js';
import '../components/camera/MultiCameraMonitor.js';
import SessionsAPI from '../api/sessions.js';
import MapsAPI from '../api/maps.js';
import { EVENTS, SESSION_STATUS } from '../utils/constants.js';
import Logger from '../utils/logger.js';
import CONFIG from '../config.js';

const EXPERIMENT_STATE = {
    NAVIGATION: 'navigation',
    JA_INSTRUCTION: 'ja_instruction',
    PAUSED: 'paused',
};

export default class ExperimentControl extends BasePage {
    constructor() {
        super();
        this.pageTitle = '实验控制';
        this.viewTemplate = 'experiment_control.html';
        this.robotController = null;
        this.cameraMonitor = null;
        this.currentSessionId = null;
        this.currentMapId = null;
        this.speechText = '';
        this.durationInterval = null;

        this.state = {
            experimentStatus: EXPERIMENT_STATE.NAVIGATION,
            jaTargets: [],
            currentTarget: null,
            currentInstruction: null,
            instructionLevel: 1,
        };
    }

    async loadData() {
        this.currentSessionId = sessionStorage.getItem('currentSessionId');
        this.currentMapId = sessionStorage.getItem('currentMapId');

        if (!this.currentSessionId || !this.currentMapId) {
            throw new Error('没有活动的实验会话或地图，请先开始实验');
        }

        Logger.info(`Loading experiment control for session: ${this.currentSessionId}, map: ${this.currentMapId}`);
        
        // 获取JA目标
        this.state.jaTargets = await MapsAPI.getTargets(this.currentMapId);
        Logger.info(`Loaded ${this.state.jaTargets.length} JA targets`);
    }

    async renderData() {
        this.initializeComponents();
        this.updateSessionInfo();
        this.renderJATargetList();
        this.renderJATargetDetail();
        this.updateExperimentState(EXPERIMENT_STATE.NAVIGATION);
    }

    setupEventListeners() {
        super.setupEventListeners();

        // 结束实验按钮
        const endExperimentBtn = this.querySelector('#end-experiment-btn');
        if (endExperimentBtn) {
            this.addEventListener(endExperimentBtn, 'click', () => this.handleEndExperiment());
        }

        // 紧急停止按钮
        const emergencyStopBtn = this.querySelector('#emergency-stop-btn');
        if (emergencyStopBtn) {
            this.addEventListener(emergencyStopBtn, 'click', () => this.handleEmergencyStop());
        }

        // 语音合成按钮
        const generateSpeechBtn = this.querySelector('#generate-speech-btn');
        if (generateSpeechBtn) {
            this.addEventListener(generateSpeechBtn, 'click', () => this.handleGenerateSpeech());
        }

        // 语音文本输入
        const speechTextArea = this.querySelector('#speech-text');
        if (speechTextArea) {
            this.addEventListener(speechTextArea, 'input', (e) => {
                this.speechText = e.target.value;
            });
        }

        // 快捷语音按钮
        this.setupQuickSpeechButtons();
    }

    initializeComponents() {
        try {
            this.robotController = new RobotDogController('robot-control-container');
            this.robotController.render();
            Logger.info('Robot dog controller initialized');

            this.cameraMonitor = this.querySelector('multi-camera-monitor');
            Logger.info('Camera monitor initialized');

        } catch (error) {
            Logger.error('Failed to initialize components:', error);
            this.showError('组件初始化失败', error.message);
        }
    }

    updateSessionInfo() {
        const participantName = sessionStorage.getItem('currentParticipantName') || '未知';
        const mapName = sessionStorage.getItem('currentMapName') || '未知';
        const startTimeISO = sessionStorage.getItem('sessionStartTime') || new Date().toISOString();
        const startTime = new Date(startTimeISO);

        this.querySelector('#exp-participant-name').textContent = participantName;
        this.querySelector('#exp-map-name').textContent = mapName;
        this.querySelector('#exp-start-time').textContent = startTime.toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' });

        this.startDurationTimer(startTime);
    }

    startDurationTimer(startTime) {
        if (this.durationInterval) {
            clearInterval(this.durationInterval);
        }

        const durationElement = this.querySelector('#exp-duration');

        this.durationInterval = setInterval(() => {
            const now = new Date();
            const diff = now - startTime; // a diferença em milissegundos

            const hours = Math.floor(diff / 3600000);
            const minutes = Math.floor((diff % 3600000) / 60000);
            const seconds = Math.floor((diff % 60000) / 1000);

            let durationText;
            if (hours > 0) {
                durationText = `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}`;
            } else {
                durationText = `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
            }
            durationElement.textContent = durationText;
        }, 1000);
    }

    setupQuickSpeechButtons() {
        const quickSpeechContainer = this.querySelector('#quick-speech-container');
        if (!quickSpeechContainer) return;

        const quickPhrases = [
            '很好，继续',
            '请看这里',
            '跟我来',
            '做得不错',
            '试试看',
            '注意看'
        ];

        const buttonsHtml = quickPhrases.map(phrase => 
            `<button class="btn btn-outline-primary btn-sm m-1 quick-speech-btn" data-text="${phrase}">
                ${phrase}
            </button>`
        ).join('');

        quickSpeechContainer.innerHTML = `
            <h6>快捷语音</h6>
            <div class="quick-speech-buttons">
                ${buttonsHtml}
            </div>
        `;

        // 添加事件监听器
        const quickSpeechBtns = quickSpeechContainer.querySelectorAll('.quick-speech-btn');
        quickSpeechBtns.forEach(btn => {
            this.addEventListener(btn, 'click', () => {
                const text = btn.getAttribute('data-text');
                this.generateSpeech(text);
            });
        });
    }

    handleEmergencyStop() {
        if (this.robotController) {
            this.robotController.switchMode('damp');
            this.showInfo('已发送紧急停止(Damp)指令');
        } else {
            this.showWarning('机器人控制器未初始化');
        }
    }

    async handleEndExperiment() {
        try {
            const confirmed = await this.confirmAction(
                '结束实验',
                '确定要结束当前实验吗？所有数据将被保存。'
            );

            if (!confirmed) return;

            this.showLoading('正在结束实验...');

            // 停止机器人控制
            if (this.robotController) {
                this.robotController.stopControl();
            }

            // 更新会话状态
            await SessionsAPI.updateStatus(this.currentSessionId, SESSION_STATUS.ENDED);

            // 清理会话数据
            this.clearSessionData();

            this.hideLoading();
            this.showSuccess('实验已成功结束');

            // 延迟导航到结果页面
            setTimeout(() => {
                this.navigateTo('session_results');
            }, 1500);

        } catch (error) {
            this.hideLoading();
            Logger.error('Failed to end experiment:', error);
            this.showError('结束实验失败', error.message);
        }
    }

    async handleGenerateSpeech() {
        const speechText = this.speechText.trim();
        if (!speechText) {
            this.showWarning('请输入要合成的语音内容');
            return;
        }

        await this.generateSpeech(speechText);
    }

    async generateSpeech(text) {
        try {
            if (!text || !text.trim()) {
                this.showWarning('语音内容不能为空');
                return;
            }

            this.showInfo('正在生成语音...');

            // 通过SessionsAPI触发语音生成
            await SessionsAPI.triggerAction(this.currentSessionId, 'GENERATE_SPEECH', { text });

            // 记录语音生成事件
            await SessionsAPI.triggerAction(this.currentSessionId, 'LOG_EVENT', {
                eventName: 'SPEECH_GENERATED',
                details: `Generated speech: "${text}"`
            });

            Logger.info(`Speech generated: ${text}`);

        } catch (error) {
            Logger.error('Failed to generate speech:', error);
            this.showError('语音生成失败', error.message);
        }
    }

    // 渲染JA目标列表
    renderJATargetList() {
        const container = this.querySelector('#ja-target-list-container');
        if (!container) return;

        if (this.state.jaTargets.length === 0) {
            container.innerHTML = '<p class="text-muted">当前地图没有JA目标点。</p>';
            return;
        }

        const listHtml = this.state.jaTargets.map((target, index) => `
            <div class="ja-target-item list-group-item list-group-item-action d-flex justify-content-between align-items-center" data-target-id="${target.targetId}">
                <div>
                    <span class="target-index font-weight-bold">${index + 1}.</span>
                    <span class="target-name">${target.targetName}</span>
                </div>
                <span class="badge badge-secondary completion-status">未开始</span>
            </div>
        `).join('');

        container.innerHTML = `<div class="list-group">${listHtml}</div>`;

        // 添加事件监听器
        const items = container.querySelectorAll('.ja-target-item');
        items.forEach(item => {
            this.addEventListener(item, 'click', () => {
                const targetId = item.getAttribute('data-target-id');
                this.handleSelectJATarget(targetId);
            });
        });
    }

    // 渲染JA目标详情
    renderJATargetDetail() {
        const container = this.querySelector('#ja-target-detail-container');
        if (!container) return;

        const { currentTarget, experimentStatus } = this.state;

        if (!currentTarget) {
            container.innerHTML = '<p class="text-muted">请从左侧列表选择一个JA目标。</p>';
            return;
        }

        if (experimentStatus === EXPERIMENT_STATE.NAVIGATION) {
            container.innerHTML = this.getJADetailNavigationHtml(currentTarget);
            const startBtn = this.querySelector('#start-ja-instruction-btn');
            if (startBtn) {
                this.addEventListener(startBtn, 'click', () => this.handleStartJAInstruction());
            }
        } else if (experimentStatus === EXPERIMENT_STATE.JA_INSTRUCTION) {
            container.innerHTML = this.getJADetailInstructionHtml(currentTarget);
            this.setupJAInstructionListeners();
        }
    }

    getJADetailNavigationHtml(target) {
        // 构建完整的图片URL
        const getImageUrl = (path) => {
            if (!path) return '';
            // 使用配置中的API基础URL
            const backendBaseUrl = CONFIG.API.BASE_URL;
            return `${backendBaseUrl}${path}`;
        };

        const targetImgUrl = getImageUrl(target.targetImgUrl);
        const envImgUrl = getImageUrl(target.envImgUrl);

        return `
            <h5>${target.targetName}</h5>
            <div class="row">
                <div class="col-md-6">
                    <p><strong>目标图片:</strong></p>
                    <img src="${targetImgUrl}" alt="目标图片" class="img-fluid rounded">
                </div>
                <div class="col-md-6">
                    <p><strong>环境图片:</strong></p>
                    <img src="${envImgUrl}" alt="环境图片" class="img-fluid rounded">
                </div>
            </div>
            <button id="start-ja-instruction-btn" class="btn btn-primary mt-3">
                <i class="fas fa-play"></i> 开始Target指示
            </button>
        `;
    }

    getJADetailInstructionHtml(target) {
        const { instructionLevel } = this.state;
        return `
            <h5>${target.targetName} - 指示中</h5>
            <div class="form-group">
                <label for="instruction-level-select"><strong>指示等级:</strong></label>
                <select id="instruction-level-select" class="form-control" style="width: auto; display: inline-block; margin-left: 10px;">
                    <option value="1" ${instructionLevel === 1 ? 'selected' : ''}>等级 1</option>
                    <option value="2" ${instructionLevel === 2 ? 'selected' : ''}>等级 2</option>
                    <option value="3" ${instructionLevel === 3 ? 'selected' : ''}>等级 3</option>
                </select>
            </div>
            <div class="alert alert-info mt-3" id="instruction-description">
                <!-- 等级描述将在这里动态加载 -->
                ${this.getInstructionDescription(instructionLevel)}
            </div>
            <div class="mt-3">
                <button id="ja-success-btn" class="btn btn-success mr-2">
                    <i class="fas fa-check"></i> JA成功
                </button>
                <button id="ja-failure-btn" class="btn btn-danger">
                    <i class="fas fa-times"></i> JA失败
                </button>
            </div>
        `;
    }

    setupJAInstructionListeners() {
        const levelSelect = this.querySelector('#instruction-level-select');
        if (levelSelect) {
            this.addEventListener(levelSelect, 'change', (e) => {
                this.state.instructionLevel = parseInt(e.target.value, 10);
                this.renderJATargetDetail();
            });
        }

        const successBtn = this.querySelector('#ja-success-btn');
        if (successBtn) {
            this.addEventListener(successBtn, 'click', () => this.handleJAInstructionResult('success'));
        }

        const failureBtn = this.querySelector('#ja-failure-btn');
        if (failureBtn) {
            this.addEventListener(failureBtn, 'click', () => this.handleJAInstructionResult('failure'));
        }
    }

    getInstructionDescription(level) {
        // TODO: 根据不同等级提供不同的描述
        return `这是等级 ${level} 的指示描述。请根据此描述完成操作。`;
    }

    handleSelectJATarget(targetId) {
        this.state.currentTarget = this.state.jaTargets.find(t => t.targetId === targetId);
        Logger.info(`Selected JA target:`, this.state.currentTarget);
        this.renderJATargetDetail();
        
        // 高亮显示选中的目标
        const items = this.querySelectorAll('.ja-target-item');
        items.forEach(item => {
            item.classList.toggle('active', item.getAttribute('data-target-id') === targetId);
        });
    }

    async handleStartJAInstruction() {
        if (!this.state.currentTarget) {
            this.showWarning('请先选择一个JA目标');
            return;
        }
        
        // TODO: 调用API创建指令
        // this.state.currentInstruction = await SessionsAPI.createInstruction(this.currentSessionId, this.state.currentTarget.targetId);
        
        this.state.instructionLevel = 1;
        this.updateExperimentState(EXPERIMENT_STATE.JA_INSTRUCTION);
    }

    async handleJAInstructionResult(status) {
        const { currentTarget, instructionLevel } = this.state;

        try {
            if (status === 'success') {
                this.showSuccess(`JA成功，等级: ${instructionLevel}`);
                this.updateTargetCompletionStatus(currentTarget.targetId, `完成 (L${instructionLevel})`, 'success');
                
                // TODO: 执行奖励指令
                await this.executeRewardSequence(currentTarget, instructionLevel);
                
                // TODO: 记录成功结果到后端
                await this.recordInstructionResult(currentTarget.targetId, instructionLevel, 'success');
                
                this.updateExperimentState(EXPERIMENT_STATE.NAVIGATION);
            } else { // failure
                if (instructionLevel < 3) {
                    this.state.instructionLevel++;
                    this.showWarning(`JA失败，进入下一等级: ${this.state.instructionLevel}`);
                    this.renderJATargetDetail();
                } else {
                    // 第3级失败处理
                    this.showWarning('JA失败，已达到最高等级');
                    this.updateTargetCompletionStatus(currentTarget.targetId, '失败', 'danger');
                    
                    // TODO: 记录失败结果到后端
                    await this.recordInstructionResult(currentTarget.targetId, 3, 'failure');
                    
                    // TODO: 执行失败后的处理流程
                    await this.handleTargetFailure(currentTarget);
                    
                    this.updateExperimentState(EXPERIMENT_STATE.NAVIGATION);
                }
            }
        } catch (error) {
            Logger.error('Error in handleJAInstructionResult:', error);
            this.showError('处理JA结果时出错', error.message);
        }
    }

    // TODO: 实现奖励序列
    async executeRewardSequence(target, level) {
        Logger.info(`TODO: Execute reward sequence for target ${target.targetName} at level ${level}`);
        // 这里应该实现：
        // 1. 根据等级执行不同的奖励动作
        // 2. 播放奖励音效或语音
        // 3. 控制机器人执行奖励动作
    }

    // TODO: 记录指令结果
    async recordInstructionResult(targetId, level, status) {
        Logger.info(`TODO: Record instruction result - Target: ${targetId}, Level: ${level}, Status: ${status}`);
        // 这里应该实现：
        // 1. 通过API将结果发送到后端
        // 2. 更新本地统计数据
    }

    // TODO: 处理目标失败
    async handleTargetFailure(target) {
        Logger.info(`TODO: Handle failure for target ${target.targetName}`);
        // 这里应该实现：
        // 1. 记录失败原因
        // 2. 可能的安抚动作或语音
        // 3. 准备进入下一个目标
    }

    updateTargetCompletionStatus(targetId, text, statusClass) {
        const targetItem = this.querySelector(`.ja-target-item[data-target-id="${targetId}"]`);
        if (targetItem) {
            const statusBadge = targetItem.querySelector('.completion-status');
            statusBadge.textContent = text;
            statusBadge.className = `badge badge-${statusClass} completion-status`;
        }
    }

    updateExperimentState(newState) {
        this.state.experimentStatus = newState;
        Logger.info(`Experiment state changed to: ${newState}`);

        const statusBadge = this.querySelector('#experiment-status-badge');
        if (statusBadge) {
            let badgeClass = 'secondary';
            let statusText = '未知';
            switch (newState) {
                case EXPERIMENT_STATE.NAVIGATION:
                    badgeClass = 'primary';
                    statusText = '导航中';
                    break;
                case EXPERIMENT_STATE.JA_INSTRUCTION:
                    badgeClass = 'warning';
                    statusText = 'JA指示中';
                    break;
                case EXPERIMENT_STATE.PAUSED:
                    badgeClass = 'info';
                    statusText = '已暂停';
                    break;
            }
            statusBadge.innerHTML = `<span class="badge badge-${badgeClass}">${statusText}</span>`;
        }
        
        this.renderJATargetDetail();
    }

    clearSessionData() {
        sessionStorage.removeItem('currentSessionId');
        sessionStorage.removeItem('sessionStartTime');
        sessionStorage.removeItem('currentParticipantName');
        sessionStorage.removeItem('currentMapName');
        sessionStorage.removeItem('currentMapId');
    }

    async beforeCleanup() {
        // 清理机器人控制器
        if (this.robotController) {
            await this.robotController.cleanup();
            this.robotController = null;
        }
        if (this.cameraMonitor) {
            // 如果 cameraMonitor 有 cleanup 方法，可以在这里调用
            this.cameraMonitor = null;
        }
        if (this.durationInterval) {
            clearInterval(this.durationInterval);
        }
    }
}
