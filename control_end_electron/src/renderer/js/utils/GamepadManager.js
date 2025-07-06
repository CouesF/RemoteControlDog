import Logger from './logger.js';

export default class GamepadManager {
    constructor() {
        this.gamepad = null;
        this.isPolling = false;
        this.state = {
            axes: [0, 0, 0, 0],
            buttons: []
        };
        this.init();
    }

    init() {
        window.addEventListener('gamepadconnected', (e) => {
            Logger.info(`Gamepad connected: ${e.gamepad.id}`);
            this.gamepad = e.gamepad;
            this.startPolling();
        });

        window.addEventListener('gamepaddisconnected', (e) => {
            Logger.info(`Gamepad disconnected: ${e.gamepad.id}`);
            this.stopPolling();
            this.gamepad = null;
        });
    }

    startPolling() {
        if (this.isPolling) return;
        this.isPolling = true;
        this.poll();
    }

    stopPolling() {
        this.isPolling = false;
    }

    poll() {
        if (!this.isPolling) return;

        const gamepads = navigator.getGamepads();
        if (gamepads && gamepads[0]) {
            this.gamepad = gamepads[0];
            this.state.axes = this.gamepad.axes.map(axis => (Math.abs(axis) > 0.1 ? axis : 0));
            this.state.buttons = this.gamepad.buttons.map(button => button.pressed);
        }

        requestAnimationFrame(() => this.poll());
    }

    getState() {
        return this.state;
    }
}
