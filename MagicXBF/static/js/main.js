import { Viewport } from './viewport.js';
import { UI } from './ui.js';
import { API } from './api.js';
import { Telemetry } from './telemetry.js';
import { State } from './state.js';
import { Assistant } from './assistant.js';

class MagicXBFApp {
    constructor() {
        this.initialize();
    }

    async initialize() {
        // Initialize core systems
        Telemetry.init();
        State.init();
        
        Telemetry.log('APP', 'Core systems initialized');

        this.viewport = new Viewport(
            document.getElementById('three-canvas'),
            document.getElementById('viewport-container')
        );
        
        this.api = new API();
        this.assistant = new Assistant(this.api);

        // Initialize UI last, as it depends on other systems
        this.ui = new UI(this);

        Telemetry.log('APP', 'MagicXBF application initialized successfully');
        
        // Load a default model
        this.ui.setStatus('Loading initial model...');
        await this.api.tessellate();
        this.ui.setStatus('Ready');
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.app = new MagicXBFApp();
});