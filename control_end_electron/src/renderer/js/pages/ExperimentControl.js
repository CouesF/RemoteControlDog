// 实验控制页面
import BasePage from './BasePage.js';
import RobotController from '../components/RobotController.js';
import '../components/camera/MultiCameraMonitor.js';
import SessionsAPI from '../api/sessions.js';
import { EVENTS, SESSION_STATUS } from '../utils/constants.js';
import Logger from '../utils/logger.js';

export default class ExperimentControl extends BasePage {
    constructor() {
        super();
        this.pageTitle = '实验控制';
        this.viewTemplate = 'experiment_control.html';
        this.robotController = null;
        this.cameraMonitor = null;
        this.currentSessionId = null;
        this.speechText = '';
    }

    async loadData() {
        // 获取当前会话ID
        this.currentSessionId = sessionStorage.getItem('currentSessionId');
        
        if (!this.currentSessionId) {
            throw new Error('没有活动的实验会话，请先开始实验');
        }

        Logger.info(`Loading experiment control for session: ${this.currentSessionId}`);
    }

    async renderData() {
        // 初始化机器人控制器
        this.initializeComponents();
        
        // 设置会话信息显示
        this.updateSessionInfo();
    }

    setupEventListeners() {
        super.setupEventListeners();

        // 结束实验按钮
        const endExperimentBtn = this.querySelector('#end-experiment-btn');
        if (endExperimentBtn) {
            this.addEventListener(endExperimentBtn, 'click', () => this.handleEndExperiment());
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

        // RJA 指令控制按钮
        const startInstructionBtn = this.querySelector('#start-instruction-btn');
        if (startInstructionBtn) {
            this.addEventListener(startInstructionBtn, 'click', () => this.handleStartInstruction());
        }

        const instructionSuccessBtn = this.querySelector('#instruction-success-btn');
        if (instructionSuccessBtn) {
            this.addEventListener(instructionSuccessBtn, 'click', () => this.handleInstructionResult('success'));
        }

        const instructionFailureBtn = this.querySelector('#instruction-failure-btn');
        if (instructionFailureBtn) {
            this.addEventListener(instructionFailureBtn, 'click', () => this.handleInstructionResult('failure'));
        }

        // 快捷语音按钮
        this.setupQuickSpeechButtons();
    }

    initializeComponents() {
        try {
            this.robotController = new RobotController('robot-control-container');
            this.robotController.render();
            Logger.info('Robot controller initialized');

            this.cameraMonitor = this.querySelector('multi-camera-monitor');
            Logger.info('Camera monitor initialized');

        } catch (error) {
            Logger.error('Failed to initialize components:', error);
            this.showError('组件初始化失败', error.message);
        }
    }

    updateSessionInfo() {
        const sessionInfoElement = this.querySelector('#session-info');
        if (sessionInfoElement && this.currentSessionId) {
            const startTime = sessionStorage.getItem('sessionStartTime') || new Date().toISOString();
            const participantName = sessionStorage.getItem('currentParticipantName') || '未知';
            const mapName = sessionStorage.getItem('currentMapName') || '未知';

            sessionInfoElement.innerHTML = `
                <div class="session-details">
                    <h6>当前实验信息</h6>
                    <p><strong>会话ID:</strong> ${this.currentSessionId}</p>
                    <p><strong>被试:</strong> ${participantName}</p>
                    <p><strong>地图:</strong> ${mapName}</p>
                    <p><strong>开始时间:</strong> ${new Date(startTime).toLocaleString()}</p>
                    <p><strong>状态:</strong> <span class="badge badge-success">进行中</span></p>
                </div>
            `;
        }
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

    async handleStartInstruction() {
        try {
            // TODO: 实现指令开始逻辑
            // 这里需要选择目标点，创建指令等
            this.showInfo('TODO: 实现开始指令功能');
            
            Logger.info('TODO: Start instruction implementation needed');

        } catch (error) {
            Logger.error('Failed to start instruction:', error);
            this.showError('开始指令失败', error.message);
        }
    }

    async handleInstructionResult(status) {
        try {
            // TODO: 实现指令结果记录逻辑
            // 这里需要当前指令的上下文
            this.showInfo(`TODO: 记录指令结果为 ${status}`);
            
            // 记录事件
            await SessionsAPI.triggerAction(this.currentSessionId, 'LOG_EVENT', {
                eventName: 'INSTRUCTION_RESULT',
                details: `Instruction result: ${status}`
            });

            Logger.info(`Instruction result: ${status}`);

        } catch (error) {
            Logger.error('Failed to record instruction result:', error);
            this.showError('记录指令结果失败', error.message);
        }
    }

    clearSessionData() {
        sessionStorage.removeItem('currentSessionId');
        sessionStorage.removeItem('sessionStartTime');
        sessionStorage.removeItem('currentParticipantName');
        sessionStorage.removeItem('currentMapName');
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
    }
}
