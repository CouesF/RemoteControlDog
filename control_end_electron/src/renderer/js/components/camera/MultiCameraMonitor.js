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
                    position: relative; /* Add relative positioning */
                }
                .camera-view {
                    background-color: #000;
                    border-radius: 8px;
                    overflow: hidden;
                    position: relative; /* Ensure buttons inside are positioned relative to this */
                }
                .reconnect-btn {
                    position: absolute;
                    top: 10px;
                    right: 10px;
                    z-index: 10;
                    background-color: rgba(0, 0, 0, 0.5);
                    color: white;
                    border: none;
                    border-radius: 50%;
                    width: 40px;
                    height: 40px;
                    font-size: 20px;
                    cursor: pointer;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    transition: background-color 0.3s;
                }
                .reconnect-btn:hover {
                    background-color: rgba(0, 0, 0, 0.8);
                }
                #main-camera {
                    grid-area: main;
                    position: relative; /* Ensure indicator is positioned relative to this */
                }
                #indicator {
                    position: absolute;
                    width: 10px;
                    height: 10px;
                    background-color: red;
                    border-radius: 50%;
                    transform: translate(-50%, -50%);
                    pointer-events: none; /* So it doesn't interfere with clicks */
                    display: none; /* Initially hidden */
                }
                #aux-camera-1 {
                    grid-area: aux1;
                }
                #aux-camera-2 {
                    grid-area: aux2;
                }
            </style>
            <div id="main-camera" class="camera-view">
                <div id="indicator"></div>
            </div>
            <div id="aux-camera-1" class="camera-view"></div>
            <div id="aux-camera-2" class="camera-view"></div>
            <button id="reconnect-all-btn" class="reconnect-btn" title="Reconnect all cameras">
                <i class="fas fa-sync-alt"></i>
            </button>
        `;
        this._reconnectAllHandler = this._reconnectAllCameras.bind(this);
    }

    connectedCallback() {
        this.init();
        this.shadowRoot.querySelector('#reconnect-all-btn').addEventListener('click', this._reconnectAllHandler);
    }

    disconnectedCallback() {
        const cameraIds = this._getCameraIdsFromLayout();
        cameraManager.unsubscribe(cameraIds);
        logger.info('MultiCameraMonitor disconnected and unsubscribed from cameras.');
        this.shadowRoot.querySelector('#reconnect-all-btn').removeEventListener('click', this._reconnectAllHandler);
        
        if (this._indicatorClickHandler) {
            const mainCameraContainer = this.shadowRoot.querySelector('#main-camera');
            if (mainCameraContainer) {
                mainCameraContainer.removeEventListener('click', this._indicatorClickHandler);
            }
        }
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
        logger.info('[MultiCameraMonitor] Rendering camera layout...');
        const layout = CAMERA_CONFIG.LAYOUTS.DEFAULT;
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
                // --- MODIFICATION START ---
                // Use MJPEG stream for all cameras.
                let imgSrc = '';
                if (role === 'MAIN') {
                    // The old backend for the main camera.
                    imgSrc = 'http://121.43.134.209:58603/video_feed';
                } else if (role === 'AUX_1') {
                    // New backend for the left auxiliary camera.
                    imgSrc = 'http://118.31.58.101:58604/video_feed_left';
                } else if (role === 'AUX_2') {
                    // New backend for the right auxiliary camera.
                    imgSrc = 'http://118.31.58.101:58604/video_feed_right';
                }

                if (imgSrc) {
                    logger.info(`[MultiCameraMonitor] Creating <img> for MJPEG stream for role ${role} at ${imgSrc}.`);
                    const img = document.createElement('img');
                    img.src = imgSrc;
                    img.style.width = '100%';
                    img.style.height = '100%';
                    img.style.objectFit = 'contain'; // Use 'contain' to see the whole image
                    
                    // Low-latency optimizations
                    img.decoding = 'sync';
                    img.loading = 'eager';
                    img.setAttribute('crossorigin', 'anonymous');
                    
                    img.onerror = () => {
                        logger.error(`Failed to load MJPEG stream from ${img.src}`);
                        img.alt = "Video Stream Failed";
                    };
                    
                    // Clear container and append image
                    // Note: The indicator is already in the main-camera container from the template
                    const children = Array.from(viewContainer.children);
                    children.forEach(child => {
                        if (child.id !== 'indicator') {
                            viewContainer.removeChild(child);
                        }
                    });
                    viewContainer.appendChild(img);

                    if (role === 'MAIN') {
                        this._setupIndicatorListener(viewContainer, img);
                    }

                } else {
                    // Fallback for any other roles that might be added
                    logger.info(`[MultiCameraMonitor] Creating <camera-display> for role ${role} (Camera ID: ${cameraId}).`);
                    const cameraDisplay = document.createElement('camera-display');
                    cameraDisplay.setAttribute('camera-id', cameraId);
                    viewContainer.innerHTML = ''; // Clear previous content
                    viewContainer.appendChild(cameraDisplay);
                }
                // --- MODIFICATION END ---
            } else {
                logger.warn(`[MultiCameraMonitor] View container for role ${role} not found.`);
            }
        });
        logger.info('[MultiCameraMonitor] Camera layout rendered.');
    }

    _setupIndicatorListener(container, img) {
        const indicator = this.shadowRoot.querySelector('#indicator');
        if (!indicator) return;

        this._indicatorClickHandler = (event) => {
            const rect = img.getBoundingClientRect();
            const containerRect = container.getBoundingClientRect();

            // Image's natural dimensions
            const naturalWidth = 640;
            const naturalHeight = 480;

            // Calculate the rendered image's dimensions and position due to 'object-fit: contain'
            const ratio = Math.min(rect.width / naturalWidth, rect.height / naturalHeight);
            const renderedWidth = naturalWidth * ratio;
            const renderedHeight = naturalHeight * ratio;

            // Calculate the offset (letterboxing)
            const offsetX = (rect.width - renderedWidth) / 2;
            const offsetY = (rect.height - renderedHeight) / 2;

            // Get click coordinates relative to the container
            const clickX = event.clientX - containerRect.left;
            const clickY = event.clientY - containerRect.top;

            // Check if the click is within the actual image area
            if (clickX >= offsetX && clickX <= offsetX + renderedWidth &&
                clickY >= offsetY && clickY <= offsetY + renderedHeight) {
                
                // Calculate coordinates relative to the image (0-640, 0-480)
                const relativeX = Math.round(((clickX - offsetX) / renderedWidth) * naturalWidth);
                const relativeY = Math.round(((clickY - offsetY) / renderedHeight) * naturalHeight);

                // Map image coordinates to joystick values (-1 to 1)
                // Joystick: right is positive X, up is positive Y
                // Image: right is positive X, down is positive Y
                const joystickX = (relativeX - naturalWidth / 2) / (naturalWidth / 2);
                const joystickY = (naturalHeight / 2 - relativeY) / (naturalHeight / 2);

                logger.info(`Indicator clicked. Mapped to joystick values: { x: ${joystickX.toFixed(2)}, y: ${joystickY.toFixed(2)} }`);

                // Dispatch an event with the joystick values.
                // The parent component (e.g., experimentControl.js) will be responsible for
                // updating the joystick component and sending the command.
                this.dispatchEvent(new CustomEvent('set-head-joystick', {
                    detail: {
                        x: joystickX,
                        y: joystickY,
                        source: 'camera-click' // Indicate the source of the update
                    },
                    bubbles: true,
                    composed: true
                }));

                // Position the indicator
                indicator.style.left = `${clickX}px`;
                indicator.style.top = `${clickY}px`;
                indicator.style.display = 'block';
            }
        };
        
        container.addEventListener('click', this._indicatorClickHandler);
    }

    _reconnectAllCameras() {
        logger.info('[MultiCameraMonitor] Reconnecting all camera streams...');
        const images = this.shadowRoot.querySelectorAll('.camera-view img');
        images.forEach(img => {
            const originalSrc = img.src.split('?')[0];
            img.src = `${originalSrc}?t=${Date.now()}`;
            logger.info(`[MultiCameraMonitor] Reconnecting to ${img.src}`);
        });
    }

    /**
     * Updates the position of the indicator on the main camera feed based on joystick values.
     * This allows the joystick to control the indicator's position.
     * @param {number} joystickX - The joystick's X value (-1 to 1).
     * @param {number} joystickY - The joystick's Y value (-1 to 1).
     */
    updateIndicatorFromJoystick(joystickX, joystickY) {
        const indicator = this.shadowRoot.querySelector('#indicator');
        const img = this.shadowRoot.querySelector('#main-camera img');
        if (!indicator || !img) {
            logger.warn('Indicator or main camera image not found for joystick update.');
            return;
        }

        // Image's natural dimensions
        const naturalWidth = 640;
        const naturalHeight = 480;

        // Map joystick values back to image coordinates (relativeX, relativeY)
        const relativeX = (joystickX * (naturalWidth / 2)) + (naturalWidth / 2);
        const relativeY = (naturalHeight / 2) - (joystickY * (naturalHeight / 2));

        // Now, map image coordinates back to screen coordinates (the reverse of the click handler)
        const rect = img.getBoundingClientRect();
        const ratio = Math.min(rect.width / naturalWidth, rect.height / naturalHeight);
        const renderedWidth = naturalWidth * ratio;
        const renderedHeight = naturalHeight * ratio;
        const offsetX = (rect.width - renderedWidth) / 2;
        const offsetY = (rect.height - renderedHeight) / 2;

        const clickX = (relativeX / naturalWidth) * renderedWidth + offsetX;
        const clickY = (relativeY / naturalHeight) * renderedHeight + offsetY;

        // Position the indicator
        indicator.style.left = `${clickX}px`;
        indicator.style.top = `${clickY}px`;
        indicator.style.display = 'block';

        logger.info(`Indicator updated from joystick. Position: { x: ${clickX.toFixed(2)}, y: ${clickY.toFixed(2)} }`);
    }

    _getCameraIdsFromLayout() {
        const layout = CAMERA_CONFIG.LAYOUTS.DEFAULT;
        // MODIFIED: Filter out all roles that are now handled by MJPEG streams (img tags)
        const mjpegRoles = ['MAIN', 'AUX_1', 'AUX_2'];
        return layout
            .filter(role => !mjpegRoles.includes(role))
            .map(role => CAMERA_CONFIG.ROLES[role])
            .filter(id => id !== undefined);
    }

    /**
     * 捕获当前主摄像头画面
     * @returns {Promise<string>} Base64编码的图片数据
     */
    async captureCurrentFrame() {
        try {
            // Delegate to the more generic capture function for the main camera.
            return await this.captureCameraFrame('MAIN');
        } catch (error) {
            logger.error('捕获主摄像头画面失败:', error);
            throw error; // Re-throw the error to be handled by the caller
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

            const cameraContainer = this.shadowRoot.querySelector(selector);
            if (!cameraContainer) {
                throw new Error(`摄像头容器未找到: ${cameraRole}`);
            }

            // --- MODIFICATION START: Handle both <img> and <camera-display> ---
            const imgView = cameraContainer.querySelector('img');
            if (imgView) {
                // New MJPEG stream capture logic
                const canvas = document.createElement('canvas');
                // Use the image's natural dimensions for the best quality capture
                canvas.width = imgView.naturalWidth || 640; // Fallback to default
                canvas.height = imgView.naturalHeight || 480; // Fallback to default
                
                const ctx = canvas.getContext('2d');
                if (!ctx) {
                    throw new Error('无法获取Canvas 2D上下文');
                }
                
                // Draw the image from the <img> tag to the canvas
                ctx.drawImage(imgView, 0, 0, canvas.width, canvas.height);
                
                // Get the image data as a Base64 string
                // Using image/jpeg for smaller file size compared to png
                const screenshot = canvas.toDataURL('image/jpeg');
                logger.info(`成功从 <img> 标签捕获画面: ${cameraRole}`);
                return screenshot;

            } else {
                // Fallback to old <camera-display> logic
                const cameraDisplay = cameraContainer.querySelector('camera-display');
                if (!cameraDisplay) {
                    throw new Error(`摄像头视图 (<img> or <camera-display>) 未找到: ${cameraRole}`);
                }
                
                const screenshot = await cameraDisplay.captureFrame();
                if (!screenshot) {
                    throw new Error(`无法从 <camera-display> 获取画面: ${cameraRole}`);
                }
                logger.info(`成功从 <camera-display> 捕获画面: ${cameraRole}`);
                return screenshot;
            }
            // --- MODIFICATION END ---

        } catch (error) {
            logger.error(`捕获摄像头画面失败 (${cameraRole}):`, error);
            throw error;
        }
    }
}

customElements.define('multi-camera-monitor', MultiCameraMonitor);
