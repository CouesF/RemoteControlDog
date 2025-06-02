// control_end_electron/src/renderer/renderer.js
console.log("CE_Renderer: Script loaded.");

// Helper to update text content safely
function updateText(elementId, value, defaultValue = 'N/A') {
    const element = document.getElementById(elementId);
    if (element) {
        element.textContent = value !== undefined && value !== null ? String(value) : defaultValue;
    } else {
        // console.warn(`Element with ID '${elementId}' not found.`);
    }
}

function round(value, decimals = 2) {
    if (typeof value !== 'number') return value; // Return as is if not a number
    return Number(Math.round(parseFloat(value) + 'e' + decimals) + 'e-' + decimals);
}


window.electronAPI.onRobotStatus((status) => {
    // console.log('CE_Renderer: Received robot-status:', status);
    updateText('status-battery', round(status.batteryPercent, 1));
    if (status.currentWorldPose && status.currentWorldPose.position) {
        updateText('status-pos-x', round(status.currentWorldPose.position.x));
        updateText('status-pos-y', round(status.currentWorldPose.position.y));
        updateText('status-pos-z', round(status.currentWorldPose.position.z));
    } else {
        updateText('status-pos-x', 'N/A');
        updateText('status-pos-y', 'N/A');
        updateText('status-pos-z', 'N/A');
    }
    updateText('status-nav', status.navigationState);
    if (status.humanDetection) {
        updateText('status-human', status.humanDetection.isPresent ? `Present (${round(status.humanDetection.distanceM)}m)` : 'Not Present');
    } else {
        updateText('status-human', 'N/A');
    }
    updateText('status-health', status.overallSystemHealth);
});

window.electronAPI.onVideoStream((base64Frame) => {
    // console.log('CE_Renderer: Received video-stream');
    const videoElement = document.getElementById('video-stream');
    if (videoElement) {
        videoElement.src = base64Frame;
    }
});

document.addEventListener('DOMContentLoaded', () => {
    console.log("CE_Renderer: DOM fully loaded and parsed. Setting up control listeners.");

    const btnEStop = document.getElementById('btn-e-stop');
    const btnStand = document.getElementById('btn-stand');
    const btnLieDown = document.getElementById('btn-lie-down');

    const btnForward = document.getElementById('btn-forward');
    const btnBackward = document.getElementById('btn-backward');
    const btnLeft = document.getElementById('btn-left');
    const btnRight = document.getElementById('btn-right');
    const btnStopMove = document.getElementById('btn-stop-move');
    const btnRotateLeft = document.getElementById('btn-rotate-left');
    const btnRotateRight = document.getElementById('btn-rotate-right');

    if (btnEStop) {
        btnEStop.addEventListener('click', () => {
            console.log("CE_Renderer: E-STOP button clicked");
            if (window.electronAPI.sendSystemCommand) {
                window.electronAPI.sendSystemCommand({ action: 'EMERGENCY_STOP' });
            } else {
                console.error("CE_Renderer: window.electronAPI.sendSystemCommand not available.");
            }
        });
    } else { console.warn("CE_Renderer: btn-e-stop not found"); }

    if (btnStand) {
        btnStand.addEventListener('click', () => {
            console.log("CE_Renderer: Stand button clicked");
            if (window.electronAPI.sendPostureCommand) {
                window.electronAPI.sendPostureCommand({ posture: 'STAND' });
            } else {
                console.error("CE_Renderer: window.electronAPI.sendPostureCommand not available.");
            }
        });
    } else { console.warn("CE_Renderer: btn-stand not found"); }

    if (btnLieDown) {
        btnLieDown.addEventListener('click', () => {
            console.log("CE_Renderer: Lie Down button clicked");
            if (window.electronAPI.sendPostureCommand) {
                window.electronAPI.sendPostureCommand({ posture: 'LIE_DOWN' });
            } else {
                console.error("CE_Renderer: window.electronAPI.sendPostureCommand not available.");
            }
        });
    } else { console.warn("CE_Renderer: btn-lie-down not found"); }

    // Joystick/Movement Controls
    const movementSpeed = 0.3; // m/s for linearX (forward/backward) & linearY (strafe)
    const rotationSpeed = 0.5; // rad/s for angularZ

    const sendMoveCommand = (linearX, linearY, angularZ) => {
        console.log(`CE_Renderer: Sending move command: X=${linearX}, Y=${linearY}, Z=${angularZ}`);
        if (window.electronAPI.sendControlCommand) {
            window.electronAPI.sendControlCommand({ linearX, linearY, angularZ });
        } else {
            console.error("CE_Renderer: window.electronAPI.sendControlCommand not available.");
        }
    };

    // Ensure buttons exist before adding listeners
    if (btnForward) btnForward.addEventListener('click', () => sendMoveCommand(movementSpeed, 0, 0));
    else console.warn("CE_Renderer: btn-forward not found");

    if (btnBackward) btnBackward.addEventListener('click', () => sendMoveCommand(-movementSpeed, 0, 0));
    else console.warn("CE_Renderer: btn-backward not found");
    
    if (btnLeft) btnLeft.addEventListener('click', () => sendMoveCommand(0, movementSpeed, 0)); // X: forward, Y: left/strafe
    else console.warn("CE_Renderer: btn-left not found");

    if (btnRight) btnRight.addEventListener('click', () => sendMoveCommand(0, -movementSpeed, 0));
    else console.warn("CE_Renderer: btn-right not found");

    if (btnRotateLeft) btnRotateLeft.addEventListener('click', () => sendMoveCommand(0, 0, rotationSpeed));
    else console.warn("CE_Renderer: btn-rotate-left not found");

    if (btnRotateRight) btnRotateRight.addEventListener('click', () => sendMoveCommand(0, 0, -rotationSpeed));
    else console.warn("CE_Renderer: btn-rotate-right not found");

    if (btnStopMove) btnStopMove.addEventListener('click', () => sendMoveCommand(0, 0, 0));
    else console.warn("CE_Renderer: btn-stop-move not found");

    console.log("CE_Renderer: Control event listeners set up.");
});

console.log("CE_Renderer: Initial script execution complete. Waiting for DOMContentLoaded.");