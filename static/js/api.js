// MagicXBF API Client

class ApiClient {
    constructor(app) {
        this.app = app;
        this.baseUrl = ''; // Assuming same origin
    }

    async _fetch(endpoint, options = {}) {
        const { Telemetry, UI } = this.app;
        const url = `${this.baseUrl}${endpoint}`;
        
        const defaultHeaders = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        };

        const config = {
            ...options,
            headers: {
                ...defaultHeaders,
                ...options.headers,
            },
        };

        try {
            Telemetry.log('API', `Request: ${config.method || 'GET'} ${endpoint}`, options.body ? JSON.parse(options.body) : {});
            UI.setEngineStatus('BUSY');
            const response = await fetch(url, config);
            UI.setEngineStatus('IDLE');

            if (!response.ok) {
                let errorData;
                try {
                    errorData = await response.json();
                } catch (e) {
                    errorData = { message: `Server returned status ${response.status}` };
                }
                const errorMessage = errorData.message || 'An unknown server error occurred.';
                Telemetry.log('ERROR', `API Error on ${endpoint}: ${errorMessage}`, errorData);
                UI.setStatus(errorMessage, true);
                return { status: 'error', message: errorMessage, data: errorData };
            }

            // Handle file downloads
            if (response.headers.get('content-disposition')?.includes('attachment')) {
                return this._handleFileDownload(response);
            }

            const result = await response.json();
            Telemetry.log('API', `Response for ${endpoint}`, result);
            return result;

        } catch (error) {
            UI.setEngineStatus('IDLE');
            const errorMessage = `Network error or server is down. (${error.message})`;
            Telemetry.log('ERROR', `Fatal API Error on ${endpoint}: ${errorMessage}`);
            UI.setStatus(errorMessage, true);
            return { status: 'error', message: errorMessage };
        }
    }

    async _handleFileDownload(response) {
        const { Telemetry, UI } = this.app;
        const blob = await response.blob();
        const contentDisposition = response.headers.get('content-disposition');
        let filename = 'export.bin';
        if (contentDisposition) {
            const filenameMatch = contentDisposition.match(/filename="?(.+)"?/);
            if (filenameMatch && filenameMatch.length > 1) {
                filename = filenameMatch[1];
            }
        }

        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);

        const successMessage = `File ${filename} downloaded.`;
        Telemetry.log('API', successMessage);
        UI.setStatus(successMessage, false, 'success');
        return { status: 'success', message: successMessage };
    }

    getCapabilities() {
        return this._fetch('/api/capabilities');
    }

    newDocument() {
        return this._fetch('/api/document/new', { method: 'POST' });
    }

    sendCommand(command, params = {}, selection = []) {
        return this._fetch('/api/command', {
            method: 'POST',
            body: JSON.stringify({ command, params, selection }),
        });
    }

    tessellate() {
        return this._fetch('/api/tessellate', { method: 'POST' });
    }

    uploadFile(file) {
        const formData = new FormData();
        formData.append('file', file);
        // We don't use the JSON helper for FormData
        return this._fetch('/api/import', {
            method: 'POST',
            body: formData,
            headers: { 'Content-Type': undefined }, // Let browser set it
        }).then(response => {
            // Remove Content-Type header for subsequent requests
            delete this._fetch.defaults?.headers?.['Content-Type'];
            return response;
        });
    }

    exportFile(format) {
        return this._fetch('/api/export', {
            method: 'POST',
            body: JSON.stringify({ format }),
        });
    }

    sendAssistantPrompt(prompt) {
        return this._fetch('/api/assistant', {
            method: 'POST',
            body: JSON.stringify({ prompt }),
        });
    }
}

export { ApiClient };