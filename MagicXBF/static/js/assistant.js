import { Telemetry } from './telemetry.js';

export class Assistant {
    constructor(api) {
        this.api = api;
        this.dom = {
            input: document.getElementById('assistant-input'),
            outputLog: document.getElementById('assistant-output-log'),
            workspaceInput: document.getElementById('assistant-workspace-input'),
            workspaceExecute: document.getElementById('assistant-workspace-execute'),
        };
        this.bindEvents();
        Telemetry.log('ASSISTANT', 'Assistant initialized');
    }

    bindEvents() {
        this.dom.workspaceExecute.addEventListener('click', () => this.executeWorkspace());
    }

    async execute() {
        const prompt = this.dom.input.value;
        if (!prompt) return;

        Telemetry.log('ASSISTANT', 'Executing bar prompt', { prompt });
        this.logToWorkspace(`> ${prompt}`);
        this.dom.input.value = '';

        const result = await this.api.assistantGenerate(prompt);
        if (result && result.status === 'success') {
            this.logToWorkspace(result.terminal_logs);
            // Potentially trigger a scene update if the assistant implies a change
            if (result.executable_script && !result.executable_script.startsWith('#')) {
                document.dispatchEvent(new CustomEvent('ui:status', { detail: { message: 'Assistant created geometry, tessellating...' } }));
                await this.api.tessellate();
            }
        } else {
            this.logToWorkspace(`Error: ${result ? result.message : 'Unknown error'}`);
        }
    }

    async executeWorkspace() {
        const prompt = this.dom.workspaceInput.value;
        if (!prompt) return;
        
        Telemetry.log('ASSISTANT', 'Executing workspace prompt');
        this.logToWorkspace(`> (Workspace) ${prompt}`);
        this.dom.workspaceInput.value = '';

        const result = await this.api.assistantGenerate(prompt);
        if (result && result.status === 'success') {
            this.logToWorkspace(result.terminal_logs);
        } else {
            this.logToWorkspace(`Error: ${result ? result.message : 'Unknown error'}`);
        }
    }

    logToWorkspace(message) {
        this.dom.outputLog.textContent += `\n${message}`;
        this.dom.outputLog.scrollTop = this.dom.outputLog.scrollHeight;
    }
}