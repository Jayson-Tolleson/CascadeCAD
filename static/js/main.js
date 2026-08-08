import { Viewport } from './viewport.js';
import { UI } from './ui.js';
import { ApiClient } from './api.js';
import { Telemetry } from './telemetry.js';
import { State } from './state.js';
import { Assistant } from './assistant.js';

class MagicXBFApp {
    constructor() {
        // Order is important for dependency injection
        this.Telemetry = new Telemetry(this);
        this.State = new State(this);
        this.UI = new UI(this);
        this.API = new ApiClient(this);
        this.Viewport = new Viewport(this);
        this.Assistant = new Assistant(this);
        
        this.Telemetry.log('APP', 'Core systems instantiated');
    }

    async initialize() {
        this.Telemetry.log('APP', 'MagicXBF application initializing...');
        this.UI.initialize();
        this.Viewport.initialize();
        
        this.UI.setStatus('Connecting to engine...', false, 'info');
        const caps = await this.API.getCapabilities();
        if (caps.status === 'success') {
            this.State.set('capabilities', caps.data);
            this.UI.setStatus('Engine connected. Ready.', false, 'success');
        } else {
            this.UI.setStatus('Failed to connect to engine.', true);
        }
        
        this.Telemetry.log('APP', 'MagicXBF application initialized successfully');
    }

    handleApiResponse(response) {
        if (response.status === 'success') {
            this.UI.setStatus(response.message, false, 'success');
            // A successful command implies a model change, so we must retessellate.
            this.API.tessellate().then(tessResult => {
                if (tessResult.status === 'success') {
                    this.Viewport.loadMeshes(tessResult.data.mesh_buffers);
                    this.State.set('parts', tessResult.data.parts || []);
                    // Update selection if the operation provided new object IDs
                    if (response.object_ids && response.object_ids.length > 0) {
                        this.State.set('selection', new Set(response.object_ids));
                    }
                }
            });
        } else {
            this.UI.setStatus(response.message, true);
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.MagicXBF = new MagicXBFApp();
    window.MagicXBF.initialize();
});