export const Telemetry = {
    logElement: null,
    autoscroll: true,
    logHistory: [],

    init() {
        this.logElement = document.getElementById('telemetry-log');
        document.getElementById('telemetry-autoscroll').addEventListener('change', (e) => {
            this.autoscroll = e.target.checked;
        });
        this.log('TELEMETRY', 'Telemetry system initialized.');
    },

    log(category, message, data = {}) {
        const timestamp = new Date().toISOString();
        const logEntry = { timestamp, category, message, data };
        this.logHistory.push(logEntry);

        if (this.logElement) {
            const entryDiv = document.createElement('div');
            entryDiv.className = category;
            
            let dataString = Object.keys(data).length > 0 ? ` | ${JSON.stringify(data)}` : '';
            entryDiv.textContent = `[${category}] ${message}${dataString}`;
            
            this.logElement.appendChild(entryDiv);

            if (this.autoscroll) {
                this.logElement.scrollTop = this.logElement.scrollHeight;
            }
        }
        
        // Also log to console for easier debugging
        console.log(`[${category}] ${message}`, data);
    },

    clear() {
        this.logHistory = [];
        if (this.logElement) {
            this.logElement.innerHTML = '';
        }
        this.log('TELEMETRY', 'Log cleared.');
    }
};