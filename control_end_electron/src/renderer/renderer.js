// control_end_electron/src/renderer/renderer.js
console.log("CE_Renderer: Script loaded.");

// Helper to update text content safely
function updateText(elementId, value, defaultValue = 'N/A') {
    const element = document.getElementById(elementId);
    if (element) {
        element.textContent = value !== undefined && value !== null ? value : defaultValue;
    } else {
        // console.warn(`Element with ID '${elementId}' not found.`);
    }
}

function round(value, decimals = 2) {
    if (typeof value !== 'number') return value;
    return Number(Math.round(value + 'e' + decimals) + 'e-' + decimals);
}

window.electronAPI.onRobotStatus((status) => {
    // console.log('CE_Renderer: Received robot-status:', status);
    updateText('status-battery', round(status.batteryPercent, 1));
    if (status.currentWorldPose && status.currentWorldPose.position) {
        updateText('status-pos-x', round(status.currentWorldPose.position.x));
        updateText('status-pos-y', round(status.currentWorldPose.position.y));
        updateText('status-pos-z', round(status.currentWorldPose.position.z));
    }
    updateText('status-nav', status.navigationState); // This will be the string name from enum
    if (status.humanDetection) {
        updateText('status-human', status.humanDetection.isPresent ? `Present (${round(status.humanDetection.distanceM)}m)` : 'Not Present');
    }
    updateText('status-health', status.overallSystemHealth); // String name from enum
    // If you had raw data display:
    // updateText('raw-status-data', JSON.stringify(status, null, 2));
});

window.electronAPI.onVideoStream((base64Frame) => {
    // console.log('CE_Renderer: Received video-stream');
    const videoElement = document.getElementById('video-stream');
    if (videoElement) {
        videoElement.src = base64Frame;
    }
});

// Example: Send a control command (e.g., on a button click or key press)
// This is just a placeholder. You'd integrate this with your UI controls.
// document.getElementById('some-forward-button').addEventListener('click', () => {
//    window.electronAPI.sendControlCommand({ linearX: 0.5, linearY: 0.0, angularZ: 0.0 });
// });
// document.getElementById('some-stop-button').addEventListener('click', () => {
//    window.electronAPI.sendControlCommand({ linearX: 0.0, linearY: 0.0, angularZ: 0.0 });
// });

console.log("CE_Renderer: Event listeners set up.");