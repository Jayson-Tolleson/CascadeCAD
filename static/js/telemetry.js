export class Telemetry {
    constructor(app) {
        this.app = app;
        this.logElement = null;
        this.autoscroll = true;
        this.logHistory = [];
        this.init();
    }

    init() {
        this.logElement = document.getElementById('telemetry-log');
        const autoscrollCheckbox = document.getElementById('telemetry-autoscroll');
        if (autoscrollCheckbox) {
            autoscrollCheckbox.addEventListener('change', (e) => {
                this.autoscroll = e.target.checked;
            });
        }
        const clearButton = document.getElementById('telemetry-clear');
        if (clearButton) {
            clearButton.addEventListener('click', () => this.clear());
        }
        this.log('TELEMETRY', 'Telemetry system initialized.');
    }

    log(category, message, data = {}) {
        const timestamp = new Date().toLocaleTimeString();
        const logEntry = { timestamp, category, message, data };
        this.logHistory.push(logEntry);

        if (this.logElement) {
            const entryDiv = document.createElement('div');
            entryDiv.className = category;
            
            let dataString = Object.keys(data).length > 0 
                ? ` | ${JSON.stringify(data, (key, value) => value instanceof Set ? [...value] : value)}` 
                : '';
            
            entryDiv.textContent = `${timestamp} [${category}] ${message}${dataString}`;
            
            this.logElement.appendChild(entryDiv);

            if (this.autoscroll) {
                this.logElement.scrollTop = this.logElement.scrollHeight;
            }
        }
        
        // Also log to console for easier debugging
        console.log(`[${category}] ${message}`, data);
    }

    clear() {
        this.logHistory = [];
        if (this.logElement) {
            this.logElement.innerHTML = '';
        }
        this.log('TELEMETRY', 'Log cleared.');
    }
}