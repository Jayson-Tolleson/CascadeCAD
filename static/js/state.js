export class State {
    constructor(app) {
        this.app = app;
        this._state = {};
        this.init();
    }

    init() {
        this._state = {
            selection: new Set(),
            parts: [],
            triangleCount: 0,
            engineStatus: 'IDLE',
            units: 'mm',
            activeTool: 'tool-select',
            capabilities: {},
        };
        this.app.Telemetry.log('STATE', 'State manager initialized', this._state);
    }

    get(key, defaultValue = null) {
        return this._state.hasOwnProperty(key) ? this._state[key] : defaultValue;
    }

    set(key, value) {
        const oldValue = this._state[key];
        this._state[key] = value;
        
        const valueForLog = value instanceof Set ? Array.from(value) : value;
        this.app.Telemetry.log('STATE', `State changed: ${key}`, { from: oldValue, to: valueForLog });
        
        // Dispatch a custom event for other modules to listen to
        document.dispatchEvent(new CustomEvent('state:change', { 
            detail: { key, value, oldValue } 
        }));
    }
}