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
            </style>
            <div class="placeholder">No Signal</div>
        `;
        this.shadowRoot.appendChild(this.canvas);

        this.cameraId = null;
        this.frameHandler = this._handleFrame.bind(this);
    }

    connectedCallback() {
        this.cameraId = parseInt(this.getAttribute('camera-id'), 10);
        if (isNaN(this.cameraId)) {
            logger.error('CameraDisplay: Invalid or missing camera-id attribute.');
            return;
        }

        logger.info(`CameraDisplay for camera ${this.cameraId} connected.`);
        cameraManager.on(`frame-for-camera-${this.cameraId}`, this.frameHandler);
    }

    disconnectedCallback() {
        if (this.cameraId !== null) {
            logger.info(`CameraDisplay for camera ${this.cameraId} disconnected.`);
            cameraManager.off(`frame-for-camera-${this.cameraId}`, this.frameHandler);
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
}

// Define the custom element
customElements.define('camera-display', CameraDisplay);
