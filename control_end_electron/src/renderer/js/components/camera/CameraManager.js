/**
 * @file CameraManager.js
 * @description Manages all camera-related interactions in the renderer process.
 *
 * This class acts as a singleton to provide a centralized interface for:
 * - Communicating with the main process for camera operations (via IPC).
 * - Managing the state of available and subscribed cameras.
 * - Distributing incoming camera frames to the appropriate UI components.
 * - Handling subscriptions and unsubscriptions.
 */

import EventEmitter from '../../utils/EventEmitter.js';
import logger from '../../utils/logger.js';

class CameraManager extends EventEmitter {
    constructor() {
        super();
        this.cameraList = [];
        this.subscribedCameras = new Set();
        this.isInitialized = false;

        this._initIpcListeners();
    }

    /**
     * Initializes listeners for IPC events from the main process.
     * @private
     */
    _initIpcListeners() {
        if (window.api) {
            // Corrected listener: The callback receives the payload directly, not an event object first.
            window.api.onCameraList((cameras) => {
                logger.info('Received camera list:', cameras);
                // Ensure cameras is always an array before assigning
                this.cameraList = Array.isArray(cameras) ? cameras : [];
                this.emit('camera-list-updated', this.cameraList);
            });

            window.api.onCameraFrame((frame) => {
                // Add a guard to ensure frame and frame.cameraId exist
                if (frame && typeof frame.cameraId !== 'undefined') {
                    // Emit an event for the specific camera ID
                    this.emit(`frame-for-camera-${frame.cameraId}`, frame);
                } else {
                    logger.warn('Received invalid or incomplete frame data:', frame);
                }
            });

            window.api.onSubscriptionChange((subscribedIds) => {
                logger.info('Subscription changed:', subscribedIds);
                this.subscribedCameras = new Set(Array.isArray(subscribedIds) ? subscribedIds : []);
                this.emit('subscription-updated', Array.from(this.subscribedCameras));
            });
        } else {
            logger.error('window.api is not available. IPC listeners cannot be set up.');
        }
    }

    /**
     * Initializes the connection to the camera gateway and fetches the camera list.
     */
    async initialize() {
        if (this.isInitialized) return;
        logger.info('Initializing CameraManager...');
        if (window.api) {
            await window.api.connectCameraGateway();
            this.isInitialized = true;
            logger.info('CameraManager initialized.');
        } else {
            logger.error('Initialization failed: window.api not found.');
        }
    }

    /**
     * Fetches the list of available cameras from the main process.
     * @returns {Promise<Array>} A promise that resolves with the list of cameras.
     */
    async getCameraList() {
        if (!this.isInitialized) await this.initialize();
        return this.cameraList;
    }

    /**
     * Subscribes to a list of camera IDs.
     * @param {number[]} cameraIds - An array of camera IDs to subscribe to.
     */
    subscribe(cameraIds) {
        if (!window.api) return;
        const idsToSubscribe = cameraIds.filter(id => !this.subscribedCameras.has(id));
        if (idsToSubscribe.length > 0) {
            logger.info(`Subscribing to cameras: ${idsToSubscribe.join(', ')}`);
            window.api.subscribeToCameras(idsToSubscribe);
        }
    }

    /**
     * Unsubscribes from a list of camera IDs.
     * @param {number[]} cameraIds - An array of camera IDs to unsubscribe from.
     */
    unsubscribe(cameraIds) {
        if (!window.api) return;
        const idsToUnsubscribe = cameraIds.filter(id => this.subscribedCameras.has(id));
        if (idsToUnsubscribe.length > 0) {
            logger.info(`Unsubscribing from cameras: ${idsToUnsubscribe.join(', ')}`);
            window.api.unsubscribeFromCameras(idsToUnsubscribe);
        }
    }

    /**
     * Unsubscribes from all currently subscribed cameras.
     */
    unsubscribeAll() {
        if (!window.api) return;
        const allSubscribed = Array.from(this.subscribedCameras);
        if (allSubscribed.length > 0) {
            this.unsubscribe(allSubscribed);
        }
    }

    /**
     * Closes the connection to the camera gateway.
     */
    disconnect() {
        if (!window.api) return;
        logger.info('Disconnecting from camera gateway...');
        this.unsubscribeAll();
        window.api.disconnectCameraGateway();
        this.isInitialized = false;
    }
}

// Export a singleton instance of the CameraManager
export const cameraManager = new CameraManager();
