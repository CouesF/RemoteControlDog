/**
 * @file camera-config.js
 * @description Defines configuration for the camera system.
 *
 * This file centralizes settings for camera layouts, resolutions, and identifiers.
 * By modifying this file, you can easily change which cameras are displayed,
 * their properties, and how they are arranged in the UI.
 */

const CAMERA_CONFIG = {
    // Defines the roles of each camera ID.
    // This allows the application to know which camera is primary vs. auxiliary.
    ROLES: {
        MAIN: 2,       // The primary camera, typically shown in a larger view.
        AUX_1: 0,      // Auxiliary camera 1.
        AUX_2: 1,      // Auxiliary camera 2.
    },

    // Pre-defined resolution settings for camera streams.
    // Using presets allows for consistent quality and performance.
    RESOLUTIONS: {
        DEFAULT: { width: 640, height: 480 },
        HIGH: { width: 1280, height: 720 },
        LOW: { width: 320, height: 240 },
    },

    // Defines the layout for the multi-camera monitoring view.
    // This specifies which camera roles are displayed.
    LAYOUTS: {
        DEFAULT: ['MAIN', 'AUX_1', 'AUX_2'], // Shows the main camera and two auxiliary cameras.
        MAIN_ONLY: ['MAIN'],                 // Shows only the main camera.
    },

    // Maps camera roles to their display properties.
    // This can be used to apply specific styles or settings to each camera view.
    VIEW_SETTINGS: {
        MAIN: {
            id: 'main-camera-view',
            resolution: 'DEFAULT', // Use the default resolution for the main camera.
        },
        AUX_1: {
            id: 'aux-camera-view-1',
            resolution: 'LOW',     // Use low resolution for auxiliary cameras to save bandwidth.
        },
        AUX_2: {
            id: 'aux-camera-view-2',
            resolution: 'LOW',
        },
    },
};

// Export the configuration to be used by other modules.
// Using Object.freeze to prevent accidental modification at runtime.
export default Object.freeze(CAMERA_CONFIG);
