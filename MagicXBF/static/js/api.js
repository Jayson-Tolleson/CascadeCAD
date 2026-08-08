// MagicXBF API Client
// Minor modifications to handle structured responses and new endpoints.

const api = {
    async getStatus() {
        try {
            const response = await fetch('/api/status');
            return await response.json();
        } catch (error) {
            console.error('API Error: getStatus failed', error);
            return { status: 'error', message: 'Could not connect to the server.' };
        }
    },

    async getCapabilities() {
        try {
            const response = await fetch('/api/capabilities');
            return await response.json();
        } catch (error) {
            console.error('API Error: getCapabilities failed', error);
            return { status: 'error', message: 'Could not fetch server capabilities.' };
        }
    },

    async newDocument() {
        try {
            const response = await fetch('/api/document/new', {
                method: 'POST',
            });
            return await response.json();
        } catch (error) {
            console.error('API Error: newDocument failed', error);
            return { status: 'error', message: 'Failed to create a new document.' };
        }
    },

    async sendCommand(command, params = {}, selection = []) {
        try {
            const response = await fetch('/api/command', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ command, params, selection }),
            });
            return await response.json();
        } catch (error) {
            console.error(`API Error: sendCommand(${command}) failed`, error);
            return { status: 'error', operation: command, message: 'The command could not be sent to the server.' };
        }
    },

    async getTessellation() {
        try {
            const response = await fetch('/api/tessellate');
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.message || 'Server returned an error.');
            }
            return await response.json();
        } catch (error) {
            console.error('API Error: getTessellation failed', error);
            return { status: 'error', message: 'Failed to retrieve geometry from the server.' };
        }
    },

    async uploadFile(file) {
        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await fetch('/api/import', {
                method: 'POST',
                body: formData,
            });
            return await response.json();
        } catch (error) {
            console.error('API Error: uploadFile failed', error);
            return { status: 'error', message: 'File upload failed due to a network or server error.' };
        }
    },

    async exportFile(format) {
        try {
            const response = await fetch('/api/export', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ format }),
            });

            if (!response.ok) {
                const errorResult = await response.json();
                console.error('API Error: exportFile failed', errorResult);
                return { status: 'error', message: errorResult.message || `Export to ${format.toUpperCase()} failed.` };
            }

            const blob = await response.blob();
            const contentDisposition = response.headers.get('content-disposition');
            let filename = `export.${format}`;
            if (contentDisposition) {
                const filenameMatch = contentDisposition.match(/filename="?(.+)"?/);
                if (filenameMatch.length > 1) {
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

            return { status: 'success', message: `File ${filename} downloaded.` };

        } catch (error) {
            console.error('API Error: exportFile failed', error);
            return { status: 'error', message: `Export to ${format.toUpperCase()} failed.` };
        }
    }
};

// ES module export used by main.js
export const API = api;

// Legacy/global compatibility
window.magicApi = api;