const batteryEl = document.getElementById('status-battery');
const posXEl = document.getElementById('status-pos-x');
const posYEl = document.getElementById('status-pos-y');
const posZEl = document.getElementById('status-pos-z');
const navStateEl = document.getElementById('status-nav');
const humanPresentEl = document.getElementById('status-human');
const healthEl = document.getElementById('status-health');
// const rawStatusEl = document.getElementById('raw-status-data');
const videoStreamEl = document.getElementById('video-stream');

// Enum string lookups (from your .proto)
const NavigationStateMap = {
  0: "UNSPECIFIED", 1: "IDLE", 2: "NAVIGATING", 3: "SUCCEEDED",
  4: "FAILED", 5: "WAITING_FOR_HUMAN", 6: "OBSTACLE_DETECTED_PAUSED"
};

const SystemEventSeverityMap = {
  0: "UNSPECIFIED", 1: "INFO", 2: "WARNING", 3: "ERROR", 4: "CRITICAL"
};


window.api.receive('robot-status', (data) => {
    // console.log('Renderer received robot-status:', data);
    // rawStatusEl.textContent = JSON.stringify(data, null, 2);

    if (data.battery_percent !== undefined) batteryEl.textContent = data.battery_percent.toFixed(1);
    if (data.current_world_pose && data.current_world_pose.position) {
        posXEl.textContent = data.current_world_pose.position.x.toFixed(2);
        posYEl.textContent = data.current_world_pose.position.y.toFixed(2);
        posZEl.textContent = data.current_world_pose.position.z.toFixed(2);
    }
    if (data.navigation_state !== undefined) {
        navStateEl.textContent = NavigationStateMap[data.navigation_state] || "UNKNOWN";
    }
    if (data.human_detection && data.human_detection.is_present !== undefined) {
        humanPresentEl.textContent = data.human_detection.is_present ? `Yes (${data.human_detection.distance_m.toFixed(1)}m)` : "No";
    }
     if (data.overall_system_health !== undefined) {
        healthEl.textContent = SystemEventSeverityMap[data.overall_system_health] || "UNKNOWN";
    }
});

window.api.receive('video-stream', (base64FrameData) => {
    // console.log('Renderer received video-stream');
    videoStreamEl.src = base64FrameData;
});

// Initial state
batteryEl.textContent = "Waiting...";
// ... and for other elements