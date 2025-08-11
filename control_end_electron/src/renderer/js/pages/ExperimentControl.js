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
        this.jaScripts = null;
        this.generalScripts = null;
        
        // 远程控制状态
        this.remoteControlStatus = {
            isConnected: false,
            isAuthenticated: false
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

        // 加载JA脚本
        await this.loadJAScripts();
        await this.loadGeneralScripts();
        
        // 初始化远程控制
        this.initializeRemoteControl();
    }

    async loadGeneralScripts() {
        try {
            const response = await fetch('../../resources/general.json');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            this.generalScripts = await response.json();
            Logger.info('General scripts loaded successfully.');
        } catch (error) {
            Logger.error('Failed to load general scripts:', error);
            this.generalScripts = {}; // Assign an empty object on failure
        }
    }

    async loadJAScripts() {
        try {
            const scriptPath = sessionStorage.getItem('currentScriptPath') || '../../resources/ja_scripts.json';
            const response = await fetch(`../../${scriptPath}`);

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            this.jaScripts = await response.json();
            Logger.info('JA scripts loaded successfully.');
        } catch (error) {
            Logger.error('Failed to load JA scripts:', error);
            this.jaScripts = {}; // Assign an empty object on failure to prevent errors
        }
    }

    async renderData() {
        this.initializeComponents();
        this.updateSessionInfo();
        this.renderJATargetList();
        this.renderJATargetDetail();
        this.renderGeneralScripts();
        this.updateExperimentState(EXPERIMENT_STATE.NAVIGATION);
    }

    renderGeneralScripts() {
        const container = this.querySelector('#general-scripts-container');
        if (!container || !this.generalScripts) return;

        let html = '';
        for (const category in this.generalScripts) {
            html += `<p>${category}</p>`;
            const buttons = this.generalScripts[category];
            html += '<div class="d-flex flex-wrap">';
            for (const buttonName in buttons) {
                const buttonData = buttons[buttonName];
                html += `
                    <button class="btn btn-outline-secondary btn-sm m-1 general-script-btn" data-texts='${JSON.stringify(buttonData.texts)}'>
                        ${buttonName}
                    </button>
                `;
            }
            html += '</div>';
        }
        container.innerHTML = html;

        // Add event listeners
        const generalScriptBtns = container.querySelectorAll('.general-script-btn');
        generalScriptBtns.forEach(btn => {
            this.addEventListener(btn, 'click', () => {
                const texts = JSON.parse(btn.getAttribute('data-texts'));
                this.handleGeneralScriptClick(texts);
            });
        });
    }

    handleGeneralScriptClick(texts) {
        if (texts && texts.length > 0) {
            const randomIndex = Math.floor(Math.random() * texts.length);
            const text = texts[randomIndex];
            this.generateSpeech(text);
        } else {
            Logger.warn('No texts found for this general script button.');
        }
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
            if (this.cameraMonitor && this.robotController) {
                // Listen for camera clicks to update the joystick
                this.addEventListener(this.cameraMonitor, 'set-head-joystick', (e) => {
                    const { x, y } = e.detail;
                    if (this.robotController.headJoystickController) {
                        this.robotController.headJoystickController.setPosition(x, y);
                    }
                });

                // Listen for manual joystick moves to update the camera indicator
                this.addEventListener(this.robotController.container, 'head-joystick-move', (e) => {
                    const { x, y } = e.detail;
                    if (this.cameraMonitor.updateIndicatorFromJoystick) {
                        this.cameraMonitor.updateIndicatorFromJoystick(x, y);
                    }
                });

                Logger.info('Camera monitor and robot controller two-way binding initialized.');
            } else {
                Logger.error('Camera monitor or robot controller component not found!');
            }

        } catch (error) {
            Logger.error('Failed to initialize components:', error);
            this.showError('组件初始化失败', error.message);
        }
    }

    handleIndicatorClick(event) {
        // This handler is now replaced by the 'set-head-joystick' listener,
        // but we'll keep it here in case it's needed for other purposes.
        const { x, y } = event.detail;
        Logger.info(`Legacy indicator click event received: { x: ${x}, y: ${y} }`);
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
            let processedText = text.trim();
            if (!processedText) {
                this.showWarning('语音内容不能为空');
                return;
            }

            // 获取参与者姓名并替换占位符
            const participantName = sessionStorage.getItem('currentParticipantName');
            if (participantName && participantName !== '未知') {
                processedText = processedText.replace(/小朋友/g, participantName);
            }
    
            this.showInfo('正在请求语音合成...');
    
            // 直接调用新的API方法
            await SessionsAPI.synthesisSpeech(processedText);
    
            // 记录语音生成事件
            await SessionsAPI.triggerAction(this.currentSessionId, 'LOG_EVENT', {
                eventName: 'SPEECH_SYNTHESIS_REQUESTED',
                details: `Requested speech synthesis for: "${processedText}" (Original: "${text}")`
            });
    
            Logger.info(`Speech synthesis requested for: ${processedText}`);
            this.showSuccess('语音合成请求已发送');
    
        } catch (error) {
            Logger.error('Failed to request speech synthesis:', error);
            this.showError('语音合成失败', error.message);
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
                    <p>目标图</p>
                    <img src="${targetImgUrl}" alt="目标图片" class="img-fluid rounded" style="max-width: 6%">
                </div>
                <div class="col-md-6">
                    <p>环境图</p>
                    <img src="${envImgUrl}" alt="环境图片" class="img-fluid rounded" style="max-width: 6%">
                </div>
            </div>
            <button id="start-ja-instruction-btn" class="btn btn-primary mt-3">
                <i class="fas fa-play"></i> 开始Target指示
            </button>
        `;
    }

    getJADetailInstructionHtml(target) {
        const { instructionLevel } = this.state;
    
        const buttons = {
            1: '<button id="call-name-btn" class="btn btn-info mr-2">呼唤名字</button>',
            2: `
                <button id="call-name-btn" class="btn btn-info mr-2">呼唤名字</button>
                <button id="voice-prompt-btn" class="btn btn-info mr-2">语言提示</button>
            `,
            3: `
                <button id="call-name-btn" class="btn btn-info mr-2">呼唤名字</button>
                <button id="voice-prompt-btn" class="btn btn-info mr-2">语言提示</button>
                <button id="end-leg-lift-btn" class="btn btn-warning mr-2">结束抬脚</button>
            `
        };
    
        return `
            <h5>
                ${target.targetName} - 指示中
                <select id="instruction-level-select" class="form-control" style="width: auto; display: inline-block; margin-left: 10px;">
                    <option value="1" ${instructionLevel === 1 ? 'selected' : ''}>等级 1</option>
                    <option value="2" ${instructionLevel === 2 ? 'selected' : ''}>等级 2</option>
                    <option value="3" ${instructionLevel === 3 ? 'selected' : ''}>等级 3</option>
                </select>
            </h5>
            <div class="alert alert-info mt-3" id="instruction-description">
                ${this.getInstructionDescription(instructionLevel)}
            </div>
            <div class="mt-3" id="instruction-buttons">
                ${buttons[instructionLevel] || ''}
            </div>
            <hr>
            <div class="mt-3">
                <button id="ja-success-btn" class="btn btn-success mr-2">
                    <i class="fas fa-check"></i> JA成功
                </button>
                <button id="ja-failure-btn" class="btn btn-danger mr-2">
                    <i class="fas fa-times"></i> JA失败
                </button>
                <button id="child-left-btn" class="btn btn-warning">
                    <i class="fas fa-exclamation-triangle"></i> 如果孩子脱离画面
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

        const callNameBtn = this.querySelector('#call-name-btn');
        if (callNameBtn) {
            this.addEventListener(callNameBtn, 'click', () => this.handleCallName());
        }

        const voicePromptBtn = this.querySelector('#voice-prompt-btn');
        if (voicePromptBtn) {
            this.addEventListener(voicePromptBtn, 'click', () => this.handleVoicePrompt());
        }

        const endLegLiftBtn = this.querySelector('#end-leg-lift-btn');
        if (endLegLiftBtn) {
            this.addEventListener(endLegLiftBtn, 'click', () => this.handleEndLegLift());
        }

        const childLeftBtn = this.querySelector('#child-left-btn');
        if (childLeftBtn) {
            this.addEventListener(childLeftBtn, 'click', () => this.handleChildLeftFrame());
        }
    }

    getInstructionDescription(level) {
        switch (level) {
            case 1:
                return '请你遥控狗头，使其先看向小孩，呼唤其名字。<br>当他注视你的时候<br>狗头提示（重复两次）<br>观察5s内是否成功看向对象';
            case 2:
                return '请你遥控狗头，使其先看向小孩，呼唤其名字。<br>当他注视你的时候➡️<br>语音提示➡️狗头提示（重复两次）<br>观察5s内是否成功看向对象';
            case 3:
                return '请你遥控狗头，使其先看向小孩，呼唤其名字。<br>当他注视你的时候➡️点击语音提示➡️<br>抬手-手部提示➡️<br>狗头提示（重复两次）。<br>观察5s内是否成功看向对象';
            default:
                return '未知的指示等级';
        }
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

    async handleCallName() {
        const participantName = sessionStorage.getItem('currentParticipantName') || '未知';
        Logger.info(`Calling name: ${participantName}`);
        try {
            await SessionsAPI.callName(this.currentSessionId, participantName);
            this.showSuccess(`已发送呼唤名字指令: ${participantName}`);
        } catch (error) {
            Logger.error('Failed to call name:', error);
            this.showError('呼唤名字失败', error.message);
        }
    }

    async handleVoicePrompt() {
        const { currentTarget, instructionLevel } = this.state;
        if (!currentTarget) {
            this.showWarning('没有选择JA目标');
            return;
        }
    
        let promptText = '';
        const targetName = currentTarget.targetName;
        console.log(targetName);
        
    
        if (this.jaScripts && this.jaScripts[targetName]) {
            const script = this.jaScripts[targetName];
            // Levels 2 and 3 use L2_AUDIO_TEXT for the prompt
            console.log(script.L2_AUDIO_TEXT)
            if ((instructionLevel === 1)) {
                promptText = `小朋友，请看看${targetName}`;
            } else if (instructionLevel === 2 && script.L2_AUDIO_TEXT) {
                // Fallback for level 1 or if L2 text is missing
                promptText = script.L2_AUDIO_TEXT || `小朋友，请看看${targetName}`;
            } else if(instructionLevel ===3 && script.L3_AUDIO_TEXT){
                promptText = script.L3_AUDIO_TEXT || `小朋友，请看看${targetName}`;
            } else{
                promptText  = `小朋友，请看看${targetName}`;
            }
        } else {
            promptText = `小朋友，请看看${targetName}`; // Default prompt if target not in scripts
        }
    
        Logger.info(`Sending voice prompt for target: ${targetName}, level: ${instructionLevel}, text: "${promptText}"`);
        
        try{
            await this.generateSpeech(promptText);
            
            // Log the action
            await SessionsAPI.triggerAction(this.currentSessionId, 'LOG_EVENT', {
                eventName: 'VOICE_PROMPT_SENT',
                details: `Target: ${targetName}, Level: ${instructionLevel}, Text: "${promptText}"`
            });
    
            this.showSuccess('已发送语音提示指令');
        } catch (error) {
            Logger.error('Failed to send voice prompt:', error);
            this.showError('发送语音提示失败', error.message);
        }
    }

    async handleEndLegLift() {
        Logger.info('Ending leg lift');
        try {
            await SessionsAPI.endLegLift(this.currentSessionId);
            this.showSuccess('已发送结束抬脚指令');
        } catch (error) {
            Logger.error('Failed to end leg lift:', error);
            this.showError('结束抬脚失败', error.message);
        }
    }

    async handleChildLeftFrame() {
        const { currentTarget } = this.state;
        const participantName = sessionStorage.getItem('currentParticipantName') || '未知';
        if (!currentTarget) {
            this.showWarning('没有选择JA目标');
            return;
        }
        Logger.info(`Child left frame for target: ${currentTarget.targetName}`);
        try {
            await SessionsAPI.childLeftFrame(this.currentSessionId, {
                participantName,
                targetId: currentTarget.targetId,
                targetName: currentTarget.targetName,
            });
            this.showSuccess('已记录孩子脱离画面事件');
        } catch (error) {
            Logger.error('Failed to record child left frame:', error);
            this.showError('记录孩子脱离画面失败', error.message);
        }
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
        const participantName = sessionStorage.getItem('currentParticipantName') || '未知';
        const targetName = currentTarget.targetName;
    
        try {
            if (status === 'success') {
                this.showSuccess(`JA成功，等级: ${instructionLevel}`);
                this.updateTargetCompletionStatus(currentTarget.targetId, `完成 (L${instructionLevel})`, 'success');
    
                // 1. 发送语音合成请求
                const successSpeech = this.jaScripts?.[targetName]?.SUCCESS;
                if (successSpeech) {
                    await SessionsAPI.synthesisSpeech(successSpeech);
                }
    
                // 2. 发送JA成功逻辑请求
                await SessionsAPI.jaSuccess(this.currentSessionId, {
                    participantName,
                    targetId: currentTarget.targetId,
                    targetName: targetName,
                    instructionLevel: instructionLevel
                });
    
                this.updateExperimentState(EXPERIMENT_STATE.NAVIGATION);
    
            } else { // failure
                // Play failure audio for the current level
                const script = this.jaScripts?.[targetName];
                if (script) {
                    const failText = instructionLevel === 1 ? script.L1_FAIL : script.L2_FAIL;
                    if (failText) {
                        await SessionsAPI.synthesisSpeech(failText);
                    }
                }
    
                await SessionsAPI.jaFailure(this.currentSessionId, {
                    participantName,
                    targetId: currentTarget.targetId,
                    targetName: currentTarget.targetName,
                    instructionLevel: instructionLevel
                });
    
                if (instructionLevel < 3) {
                    this.state.instructionLevel++;
                    this.showWarning(`JA失败，进入下一等级: ${this.state.instructionLevel}`);
                    this.renderJATargetDetail();
                } else {
                    this.showWarning('JA失败，已达到最高等级');
                    this.updateTargetCompletionStatus(currentTarget.targetId, '失败', 'danger');
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
        sessionStorage.removeItem('currentScriptPath');
    }

    // === 远程控制相关方法 ===
    
    initializeRemoteControl() {
        try {
            if (!window.api?.onRemoteControlCommand) {
                Logger.warn('Remote control API not available');
                return;
            }

            // 监听远程控制命令
            window.api.onRemoteControlCommand((data) => {
                this.handleRemoteControlCommand(data);
            });

            // 监听远程控制状态变化
            window.api.onRemoteControlConnected(() => {
                this.remoteControlStatus.isConnected = true;
                this.updateRemoteControlStatusDisplay();
                Logger.info('Remote control connected');
            });

            window.api.onRemoteControlDisconnected(() => {
                this.remoteControlStatus.isConnected = false;
                this.remoteControlStatus.isAuthenticated = false;
                this.updateRemoteControlStatusDisplay();
                Logger.info('Remote control disconnected');
            });

            window.api.onRemoteControlAuthenticated(() => {
                this.remoteControlStatus.isAuthenticated = true;
                this.updateRemoteControlStatusDisplay();
                Logger.info('Remote control authenticated');
            });

            window.api.onRemoteControlAuthFailed((message) => {
                this.remoteControlStatus.isAuthenticated = false;
                this.updateRemoteControlStatusDisplay();
                Logger.error(`Remote control auth failed: ${message}`);
            });

            // 获取初始状态
            this.updateRemoteControlStatus();

            Logger.info('Remote control initialized');

        } catch (error) {
            Logger.error('Failed to initialize remote control:', error);
        }
    }

    async updateRemoteControlStatus() {
        try {
            if (window.api?.getRemoteControlStatus) {
                const status = await window.api.getRemoteControlStatus();
                this.remoteControlStatus = status;
                this.updateRemoteControlStatusDisplay();
            }
        } catch (error) {
            Logger.error('Failed to get remote control status:', error);
        }
    }

    updateRemoteControlStatusDisplay() {
        // 可以在UI上显示远程控制状态，比如在顶部栏添加状态指示器
        const { isConnected, isAuthenticated } = this.remoteControlStatus;
        
        // 查找或创建远程控制状态指示器
        let statusIndicator = this.querySelector('#remote-control-status');
        if (!statusIndicator) {
            // 如果不存在，可以在适当的位置创建一个
            statusIndicator = document.createElement('div');
            statusIndicator.id = 'remote-control-status';
            statusIndicator.style.cssText = `
                position: fixed;
                top: 10px;
                right: 10px;
                padding: 8px 12px;
                border-radius: 20px;
                font-size: 0.8rem;
                font-weight: 600;
                z-index: 1000;
                transition: all 0.3s ease;
            `;
            document.body.appendChild(statusIndicator);
        }

        // 更新状态显示
        if (isConnected && isAuthenticated) {
            statusIndicator.textContent = '🟢 远程控制已连接';
            statusIndicator.style.background = '#d4edda';
            statusIndicator.style.color = '#155724';
            statusIndicator.style.border = '1px solid #c3e6cb';
        } else if (isConnected) {
            statusIndicator.textContent = '🟡 远程控制认证中';
            statusIndicator.style.background = '#fff3cd';
            statusIndicator.style.color = '#856404';
            statusIndicator.style.border = '1px solid #ffeaa7';
        } else {
            statusIndicator.textContent = '🔴 远程控制断开';
            statusIndicator.style.background = '#f8d7da';
            statusIndicator.style.color = '#721c24';
            statusIndicator.style.border = '1px solid #f5c6cb';
        }
    }

    handleRemoteControlCommand(data) {
        const { action, from_client, timestamp } = data;
        
        Logger.info(`Received remote control command: ${action} from ${from_client}`);

        try {
            let result = null;

            switch (action) {
                case 'ja_success':
                    result = this.executeRemoteJASuccess();
                    break;
                case 'ja_failure':
                    result = this.executeRemoteJAFailure();
                    break;
                default:
                    result = {
                        success: false,
                        message: `未知的远程控制命令: ${action}`
                    };
            }

            // 发送命令执行结果
            this.sendRemoteControlResult({
                action,
                success: result.success,
                message: result.message,
                timestamp: Date.now()
            });

        } catch (error) {
            Logger.error(`Error executing remote command ${action}:`, error);
            
            this.sendRemoteControlResult({
                action,
                success: false,
                message: `命令执行错误: ${error.message}`,
                timestamp: Date.now()
            });
        }
    }

    executeRemoteJASuccess() {
        try {
            // 检查当前状态是否允许执行JA成功
            if (this.state.experimentStatus !== EXPERIMENT_STATE.JA_INSTRUCTION) {
                return {
                    success: false,
                    message: '当前不在JA指示状态，无法执行JA成功'
                };
            }

            if (!this.state.currentTarget) {
                return {
                    success: false,
                    message: '没有选择当前JA目标'
                };
            }

            // 直接调用现有的JA成功处理逻辑
            this.handleJAInstructionResult('success');

            Logger.info('Remote JA success command executed successfully');
            
            return {
                success: true,
                message: `JA成功指令已执行 - 目标: ${this.state.currentTarget.targetName}, 等级: ${this.state.instructionLevel}`
            };

        } catch (error) {
            Logger.error('Error executing remote JA success:', error);
            return {
                success: false,
                message: `执行JA成功时出错: ${error.message}`
            };
        }
    }

    executeRemoteJAFailure() {
        try {
            // 检查当前状态是否允许执行JA失败
            if (this.state.experimentStatus !== EXPERIMENT_STATE.JA_INSTRUCTION) {
                return {
                    success: false,
                    message: '当前不在JA指示状态，无法执行JA失败'
                };
            }

            if (!this.state.currentTarget) {
                return {
                    success: false,
                    message: '没有选择当前JA目标'
                };
            }

            // 直接调用现有的JA失败处理逻辑
            this.handleJAInstructionResult('failure');

            Logger.info('Remote JA failure command executed successfully');
            
            return {
                success: true,
                message: `JA失败指令已执行 - 目标: ${this.state.currentTarget.targetName}, 等级: ${this.state.instructionLevel}`
            };

        } catch (error) {
            Logger.error('Error executing remote JA failure:', error);
            return {
                success: false,
                message: `执行JA失败时出错: ${error.message}`
            };
        }
    }

    sendRemoteControlResult(result) {
        try {
            if (window.api?.sendRemoteControlResult) {
                window.api.sendRemoteControlResult(result);
                Logger.info(`Remote control result sent: ${result.action} - ${result.success}`);
            }
        } catch (error) {
            Logger.error('Failed to send remote control result:', error);
        }
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

        // 清理远程控制状态指示器
        const statusIndicator = document.querySelector('#remote-control-status');
        if (statusIndicator) {
            statusIndicator.remove();
        }
    }
}
