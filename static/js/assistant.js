export class Assistant {
    constructor(app) {
        this.app = app;
        this.dom = {
            barInput: document.getElementById('assistant-input'),
            barExecute: document.getElementById('assistant-execute'),
            barExpand: document.getElementById('assistant-expand'),
            workspaceLog: document.getElementById('assistant-output-log'),
            workspaceInput: document.getElementById('assistant-workspace-input'),
            workspaceExecute: document.getElementById('assistant-workspace-execute'),
        };
        this.bindEvents();
        this.app.Telemetry.log('ASSISTANT', 'Assistant initialized');
    }

    bindEvents() {
        this.dom.barExecute.addEventListener('click', () => this.executeFromBar());
        this.dom.barInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.executeFromBar();
            }
        });

        this.dom.workspaceExecute.addEventListener('click', () => this.executeFromWorkspace());
        this.dom.barExpand.addEventListener('click', () => this.app.UI.expandAssistant());
    }

    async executeFromBar() {
        const prompt = this.dom.barInput.value;
        if (!prompt) return;
        
        this.dom.barInput.value = '';
        await this.execute(prompt);
    }

    async executeFromWorkspace() {
        const prompt = this.dom.workspaceInput.value;
        if (!prompt) return;

        this.dom.workspaceInput.value = '';
        await this.execute(prompt);
    }

    async execute(prompt) {
        const { Telemetry, API, UI } = this.app;
        Telemetry.log('ASSISTANT', 'Executing prompt', { prompt });
        this.logToWorkspace(`> ${prompt}`);

        UI.setStatus('Assistant is thinking...', false, 'info');
        const result = await API.sendAssistantPrompt(prompt);
        
        if (result.status === 'success') {
            UI.setStatus(`Assistant: ${result.message}`, false, 'success');
            this.logToWorkspace(`✔ ${result.message}`);
            // If the command resulted in a change, the API response should indicate it.
            // We'll trigger a tessellation to refresh the view.
            if (result.object_ids && result.object_ids.length > 0) {
                this.app.handleApiResponse(result);
            }
        } else {
            UI.setStatus(`Assistant Error: ${result.message}`, true);
            this.logToWorkspace(`✖ Error: ${result.message}`);
        }
    }

    logToWorkspace(message) {
        if (this.dom.workspaceLog) {
            this.dom.workspaceLog.textContent += `\n${message}`;
            this.dom.workspaceLog.scrollTop = this.dom.workspaceLog.scrollHeight;
        }
    }
}