/**
 * @file CameraDisplay.js
 * @description A reusable web component for displaying a single camera stream.
 *
 * This component encapsulates the logic for rendering video frames onto a canvas.
 * It subscribes to a specific camera feed via the CameraManager and updates
 * the canvas whenever a new frame is received.
 */

import { cameraManager } from './CameraManager.js';
import logger from '../../utils/logger.js';

class CameraDisplay extends HTMLElement {
    constructor() {
        super();
        this.attachShadow({ mode: 'open' });
        this.canvas = document.createElement('canvas');
        this.ctx = this.canvas.getContext('2d');
        this.shadowRoot.innerHTML = `
            <style>
                :host {
                    display: block;
                    width: 100%;
                    height: 100%;
                    position: relative;
                }
                canvas {
                    width: 100%;
                    height: 100%;
                    object-fit: contain;
                }
                .placeholder {
                    position: absolute;
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 100%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    background-color: #222;
                    color: #888;
                    font-family: sans-serif;
                }
                .status-indicator {
                    position: absolute;
                    top: 10px;
                    left: 10px;
                    display: flex;
                    align-items: center;
                    padding: 5px 10px;
                    background-color: rgba(0, 0, 0, 0.6);
                    color: white;
                    border-radius: 12px;
                    font-family: sans-serif;
                    font-size: 12px;
                }
                .status-dot {
                    width: 10px;
                    height: 10px;
                    border-radius: 50%;
                    margin-right: 8px;
                }
                .status-dot.disconnected { background-color: #f44336; } /* red */
                .status-dot.connecting { background-color: #ff9800; } /* orange */
                .status-dot.connected { background-color: #4caf50; } /* green */
            </style>
            <div class="placeholder">No Signal</div>
            <div class="status-indicator">
                <div class="status-dot disconnected"></div>
                <span class="status-text">Disconnected</span>
            </div>
        `;
        this.shadowRoot.appendChild(this.canvas);

        this.cameraId = null;
        this.frameHandler = this._handleFrame.bind(this);
        this.connectionStateHandler = this._updateConnectionStatus.bind(this);
        this.frameRequestInterval = null; // Interval for requesting frames
    }

    connectedCallback() {
        this.cameraId = parseInt(this.getAttribute('camera-id'), 10);
        if (isNaN(this.cameraId)) {
            logger.error('CameraDisplay: Invalid or missing camera-id attribute.');
            return;
        }

        logger.info(`CameraDisplay for camera ${this.cameraId} connected.`);
        cameraManager.on(`frame-for-camera-${this.cameraId}`, this.frameHandler);
        cameraManager.on('connection-state-updated', this.connectionStateHandler);
        
        // Start requesting frames periodically
        this.frameRequestInterval = setInterval(() => this.requestFrame(), 1000 / 30); // 30 FPS

        // Set initial state
        this._updateConnectionStatus(cameraManager.connectionState);
    }

    disconnectedCallback() {
        if (this.cameraId !== null) {
            logger.info(`CameraDisplay for camera ${this.cameraId} disconnected.`);
            cameraManager.off(`frame-for-camera-${this.cameraId}`, this.frameHandler);
            cameraManager.off('connection-state-updated', this.connectionStateHandler);
            
            // Stop requesting frames
            if (this.frameRequestInterval) {
                clearInterval(this.frameRequestInterval);
                this.frameRequestInterval = null;
            }
        }
    }

    /**
     * Handles incoming frame data from the CameraManager.
     * @param {object} frame - The frame data object.
     * @private
     */
    _handleFrame(frame) {
        logger.info(`[CameraDisplay ${this.cameraId}] _handleFrame called.`);

        if (!frame || !frame.frameData) {
            logger.warn(`[CameraDisplay ${this.cameraId}] Received empty or invalid frame object.`, frame);
            return;
        }

        logger.info(`[CameraDisplay ${this.cameraId}] Received frame with Base64 data length: ${frame.frameData.length}`);

        const image = new Image();
        
        // Clean the Base64 string by removing any characters not part of the Base64 alphabet.
        // This can help prevent errors if the string is malformed (e.g., contains newlines).
        const cleanFrameData = frame.frameData.replace(/[^A-Za-z0-9+/=]/g, '');
        image.src = `data:image/jpeg;base64,${cleanFrameData}`;

        image.onload = () => {
            logger.info(`[CameraDisplay ${this.cameraId}] Image loaded successfully (${image.width}x${image.height}). Drawing to canvas.`);
            const placeholder = this.shadowRoot.querySelector('.placeholder');
            if (placeholder.style.display !== 'none') {
                placeholder.style.display = 'none';
                logger.info(`[CameraDisplay ${this.cameraId}] Placeholder hidden.`);
            }

            if (this.canvas.width !== image.width || this.canvas.height !== image.height) {
                this.canvas.width = image.width;
                this.canvas.height = image.height;
                logger.info(`[CameraDisplay ${this.cameraId}] Canvas resized to ${image.width}x${image.height}.`);
            }
            this.ctx.drawImage(image, 0, 0);
        };

        image.onerror = (err) => {
            logger.error(`[CameraDisplay ${this.cameraId}] Image.onerror triggered. Failed to load image from Base64 data.`, err);
        };
    }

    /**
     * Request a new frame from the CameraManager.
     */
    requestFrame() {
        if (this.cameraId !== null) {
            cameraManager.requestFrame(this.cameraId);
        }
    }

    /**
     * Updates the UI to reflect the current connection state.
     * @param {string} state - The new connection state ('disconnected', 'connecting', 'connected').
     * @private
     */
    _updateConnectionStatus(state) {
        const dot = this.shadowRoot.querySelector('.status-dot');
        const text = this.shadowRoot.querySelector('.status-text');
        const placeholder = this.shadowRoot.querySelector('.placeholder');

        dot.className = `status-dot ${state}`;
        text.textContent = state.charAt(0).toUpperCase() + state.slice(1);

        if (state === 'connected') {
            placeholder.textContent = 'Waiting for signal...';
        } else {
            placeholder.textContent = 'Disconnected';
            placeholder.style.display = 'flex'; // Show placeholder when not connected
        }
    }

    /**
     * 捕获当前画面并返回Base64编码的图片数据
     * @returns {Promise<string>} Base64编码的图片数据
     */
    async captureFrame() {
        return new Promise((resolve, reject) => {
            try {
                if (!this.canvas || this.canvas.width === 0 || this.canvas.height === 0) {
                    reject(new Error('画布未初始化或无有效内容'));
                    return;
                }

                // 检查画布是否有内容
                const imageData = this.ctx.getImageData(0, 0, this.canvas.width, this.canvas.height);
                const data = imageData.data;
                let hasContent = false;
                
                // 检查是否有非黑色像素
                for (let i = 0; i < data.length; i += 4) {
                    if (data[i] > 0 || data[i + 1] > 0 || data[i + 2] > 0) {
                        hasContent = true;
                        break;
                    }
                }

                if (!hasContent) {
                    reject(new Error('摄像头画面为空或无信号'));
                    return;
                }

                // 将画布内容转换为Base64
                const dataURL = this.canvas.toDataURL('image/png');
                
                if (!dataURL || dataURL === 'data:,') {
                    reject(new Error('无法生成图片数据'));
                    return;
                }

                logger.info(`[CameraDisplay ${this.cameraId}] 成功捕获画面 (${this.canvas.width}x${this.canvas.height})`);
                resolve(dataURL);

            } catch (error) {
                logger.error(`[CameraDisplay ${this.cameraId}] 捕获画面失败:`, error);
                reject(error);
            }
        });
    }

    /**
     * 获取当前画布的尺寸信息
     * @returns {object} 包含width和height的对象
     */
    getCanvasSize() {
        return {
            width: this.canvas.width,
            height: this.canvas.height
        };
    }

    /**
     * 检查是否有有效的视频内容
     * @returns {boolean} 是否有有效内容
     */
    hasValidContent() {
        if (!this.canvas || this.canvas.width === 0 || this.canvas.height === 0) {
            return false;
        }

        try {
            const imageData = this.ctx.getImageData(0, 0, this.canvas.width, this.canvas.height);
            const data = imageData.data;
            
            // 检查是否有非黑色像素
            for (let i = 0; i < data.length; i += 4) {
                if (data[i] > 0 || data[i + 1] > 0 || data[i + 2] > 0) {
                    return true;
                }
            }
            return false;
        } catch (error) {
            logger.error(`[CameraDisplay ${this.cameraId}] 检查内容失败:`, error);
            return false;
        }
    }
}

// Define the custom element
customElements.define('camera-display', CameraDisplay);
