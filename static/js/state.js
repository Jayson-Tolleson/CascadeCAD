import { Telemetry } from './telemetry.js';

export const State = {
    _state: {},

    init() {
        this._state = {
            selection: new Set(),
            triangleCount: 0,
            engineStatus: 'IDLE',
            units: 'mm',
            activeTool: 'tool-select',
        };
        Telemetry.log('STATE', 'State manager initialized', this._state);
    },

    get(key, defaultValue = null) {
        return this._state.hasOwnProperty(key) ? this._state[key] : defaultValue;
    },

    set(key, value) {
        this._state[key] = value;
        Telemetry.log('STATE', `State changed: ${key}`, { value: value instanceof Set ? Array.from(value) : value });
        document.dispatchEvent(new CustomEvent('state:change', { detail: { key, value } }));
    }
};