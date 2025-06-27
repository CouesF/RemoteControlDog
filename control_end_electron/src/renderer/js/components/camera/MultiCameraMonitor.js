/**
 * @file MultiCameraMonitor.js
 * @description A web component for displaying and managing multiple camera feeds.
 *
 * This component creates a configurable layout of camera views, subscribes to
 * the necessary camera streams via the CameraManager, and handles the
 * lifecycle of the camera display elements.
 */

import { cameraManager } from './CameraManager.js';
import CAMERA_CONFIG from '../../config/camera-config.js';
import logger from '../../utils/logger.js';
import './CameraDisplay.js'; // Make sure the custom element is defined

class MultiCameraMonitor extends HTMLElement {
    constructor() {
        super();
        this.attachShadow({ mode: 'open' });
        this.shadowRoot.innerHTML = `
            <style>
                :host {
                    display: grid;
                    grid-template-areas:
                        "main main aux1"
                        "main main aux2";
                    grid-template-columns: 1fr 1fr 1fr;
                    grid-template-rows: 1fr 1fr;
                    gap: 10px;
                    width: 100%;
                    height: 100%;
                    padding: 10px;
                    box-sizing: border-box;
                }
                .camera-view {
                    background-color: #000;
                    border-radius: 8px;
                    overflow: hidden;
                }
                #main-camera {
                    grid-area: main;
                }
                #aux-camera-1 {
                    grid-area: aux1;
                }
                #aux-camera-2 {
                    grid-area: aux2;
                }
            </style>
            <div id="main-camera" class="camera-view"></div>
            <div id="aux-camera-1" class="camera-view"></div>
            <div id="aux-camera-2" class="camera-view"></div>
        `;
    }

    connectedCallback() {
        this.init();
    }

    disconnectedCallback() {
        const cameraIds = this._getCameraIdsFromLayout();
        cameraManager.unsubscribe(cameraIds);
        logger.info('MultiCameraMonitor disconnected and unsubscribed from cameras.');
    }

    async init() {
        logger.info('Initializing MultiCameraMonitor...');
        await cameraManager.initialize();
        this._renderLayout();
        const cameraIds = this._getCameraIdsFromLayout();
        cameraManager.subscribe(cameraIds);
        logger.info(`MultiCameraMonitor subscribed to cameras: ${cameraIds.join(', ')}`);
    }

    _renderLayout() {
        const layout = CAMERA_CONFIG.LAYOUTS.DEFAULT; // Using the default layout
        const container = this.shadowRoot;

        const viewMapping = {
            MAIN: container.querySelector('#main-camera'),
            AUX_1: container.querySelector('#aux-camera-1'),
            AUX_2: container.querySelector('#aux-camera-2'),
        };

        layout.forEach(role => {
            const cameraId = CAMERA_CONFIG.ROLES[role];
            const viewContainer = viewMapping[role];

            if (viewContainer) {
                const cameraDisplay = document.createElement('camera-display');
                cameraDisplay.setAttribute('camera-id', cameraId);
                viewContainer.innerHTML = ''; // Clear any placeholder
                viewContainer.appendChild(cameraDisplay);
            }
        });
    }

    _getCameraIdsFromLayout() {
        const layout = CAMERA_CONFIG.LAYOUTS.DEFAULT;
        return layout.map(role => CAMERA_CONFIG.ROLES[role]).filter(id => id !== undefined);
    }

    /**
     * 捕获当前主摄像头画面
     * @returns {Promise<string>} Base64编码的图片数据
     */
    async captureCurrentFrame() {
        try {
            const mainCameraView = this.shadowRoot.querySelector('#main-camera camera-display');
            if (!mainCameraView) {
                throw new Error('主摄像头视图未找到');
            }

            // 获取摄像头显示组件的截图
            const screenshot = await mainCameraView.captureFrame();
            if (!screenshot) {
                throw new Error('无法从摄像头获取画面');
            }

            logger.info('成功捕获摄像头画面');
            return screenshot;

        } catch (error) {
            logger.error('捕获摄像头画面失败:', error);
            throw error;
        }
    }

    /**
     * 切换摄像头布局
     */
    toggleLayout() {
        // 简单的布局切换实现
        const currentStyle = this.shadowRoot.host.style.gridTemplateAreas;
        
        if (currentStyle.includes('"main main aux1"')) {
            // 切换到单摄像头布局
            this.shadowRoot.host.style.gridTemplateAreas = '"main main main" "main main main"';
            this.shadowRoot.querySelector('#aux-camera-1').style.display = 'none';
            this.shadowRoot.querySelector('#aux-camera-2').style.display = 'none';
        } else {
            // 切换回多摄像头布局
            this.shadowRoot.host.style.gridTemplateAreas = '"main main aux1" "main main aux2"';
            this.shadowRoot.querySelector('#aux-camera-1').style.display = 'block';
            this.shadowRoot.querySelector('#aux-camera-2').style.display = 'block';
        }
        
        logger.info('摄像头布局已切换');
    }

    /**
     * 获取指定摄像头的画面
     * @param {string} cameraRole - 摄像头角色 (MAIN, AUX_1, AUX_2)
     * @returns {Promise<string>} Base64编码的图片数据
     */
    async captureCameraFrame(cameraRole = 'MAIN') {
        try {
            const viewMapping = {
                MAIN: '#main-camera',
                AUX_1: '#aux-camera-1',
                AUX_2: '#aux-camera-2'
            };

            const selector = viewMapping[cameraRole];
            if (!selector) {
                throw new Error(`无效的摄像头角色: ${cameraRole}`);
            }

            const cameraView = this.shadowRoot.querySelector(`${selector} camera-display`);
            if (!cameraView) {
                throw new Error(`摄像头视图未找到: ${cameraRole}`);
            }

            const screenshot = await cameraView.captureFrame();
            if (!screenshot) {
                throw new Error(`无法从摄像头获取画面: ${cameraRole}`);
            }

            return screenshot;

        } catch (error) {
            logger.error(`捕获摄像头画面失败 (${cameraRole}):`, error);
            throw error;
        }
    }
}

customElements.define('multi-camera-monitor', MultiCameraMonitor);
