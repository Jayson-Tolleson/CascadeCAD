import { Telemetry } from './telemetry.js';
import { State } from './state.js';

export class UI {
    constructor(app) {
        this.app = app;
        this.dom = {
            // Panels & Toolbar
            topToolbarSystem: document.getElementById('top-toolbar-system'),
            topToolbarHandle: document.getElementById('top-toolbar-handle'),
            leftPanel: document.getElementById('left-panel'),
            leftPanelHandle: document.getElementById('left-panel-handle'),
            rightPanel: document.getElementById('right-panel'),
            rightPanelHandle: document.getElementById('right-panel-handle'),
            
            // Status Bar
            statusBarMessage: document.getElementById('status-message'),
            statusBarSelection: document.getElementById('status-selection'),
            statusBarTriangles: document.getElementById('status-triangles'),
            statusBarEngine: document.getElementById('status-engine'),

            // Right Panel Tabs
            rightPanelTabs: document.querySelectorAll('.tab-button'),
            rightPanelTabContents: document.querySelectorAll('.tab-content'),
            telemetryLog: document.getElementById('telemetry-log'),
            telemetryClear: document.getElementById('telemetry-clear'),
            telemetryAutoscroll: document.getElementById('telemetry-autoscroll'),
            selectionInfoContent: document.getElementById('selection-info-content'),

            // Assistant
            assistantBarInput: document.getElementById('assistant-input'),
            assistantBarExecute: document.getElementById('assistant-execute'),
            assistantBarExpand: document.getElementById('assistant-expand'),

            // View Cube (placeholder for now)
            viewCube: document.getElementById('view-cube'),
        };

        this.bindEvents();
        this.update(); // Initial UI update
        Telemetry.log('UI', 'UI Initialized');
    }
    bindEvents() {
        // Sliding Panels / Top Toolbar
    //
    // Hover opens the toolbar.
    // Leaving closes it unless it has been pinned.
    // Clicking the handle pins/unpins it.

    this.dom.topToolbarSystem.dataset.toolbarPinned = 'false';

    this.dom.topToolbarHandle.addEventListener('click', () => {
        const system = this.dom.topToolbarSystem;
        const pinned = system.dataset.toolbarPinned === 'true';

        system.dataset.toolbarPinned = pinned ? 'false' : 'true';

        this.setToolbarOpen(!pinned);
    });

    this.dom.topToolbarSystem.addEventListener('mouseenter', () => {
        this.setToolbarOpen(true);
    });

    this.dom.topToolbarSystem.addEventListener('mouseleave', () => {
        if (this.dom.topToolbarSystem.dataset.toolbarPinned !== 'true') {
            this.setToolbarOpen(false);
        }
    });

    this.dom.leftPanelHandle.addEventListener('click', () => this.togglePanel('left'));
    this.dom.rightPanelHandle.addEventListener('click', () => this.togglePanel('right'));

    // Right Panel Tabs
        this.dom.rightPanelTabs.forEach(tab => {
            tab.addEventListener('click', () => this.activateTab(tab.dataset.tab));
        });

        // Telemetry Controls
        this.dom.telemetryClear.addEventListener('click', () => Telemetry.clear());
        
        // Toolbar Buttons
        this.bindToolbarEvents();

        // Assistant
        this.dom.assistantBarExecute.addEventListener('click', () => this.app.assistant.execute());
        this.dom.assistantBarInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') this.app.assistant.execute();
        });
        this.dom.assistantBarExpand.addEventListener('click', () => this.expandAssistant());

        // View Cube
        this.dom.viewCube.addEventListener('click', () => this.app.viewport.fitToView());

        // State change listener
        document.addEventListener('state:change', (e) => this.handleStateChange(e.detail));
    }

    bindToolbarEvents() {
        const buttons = document.querySelectorAll('#top-toolbar-content button');
        buttons.forEach(btn => {
            btn.addEventListener('click', (e) => this.handleToolbarClick(e.currentTarget));
        });
    }

    async handleToolbarClick(btn) {
        const id = btn.id;
        Telemetry.log('UI', 'Button Click', { id: id, title: btn.title });

        switch (id) {
            // --- IMPLEMENTED ---
            case 'import-model-btn':
                document.getElementById('cad-file-input').click();
                break;
            case 'export-button':
                const format = prompt("Enter export format (step, iges, stl)", "step");
                if (format) await this.app.api.export(format);
                break;
            case 'fit-view':
                this.app.viewport.fitToView();
                break;
            case 'tessellate-model':
                await this.app.api.tessellate();
                break;
            case 'repair-mesh':
                await this.app.api.repair();
                break;

            // --- PENDING BACKEND / FRONTEND ONLY ---
            case 'tool-select':
            case 'tool-move':
            case 'tool-rotate':
            case 'tool-scale':
                this.setActiveTool(id);
                break;
            
            default:
                if (btn.dataset.primitive) {
                    Telemetry.log('UI', 'Primitive Creation (PENDING BACKEND)', { type: btn.dataset.primitive });
                    this.setStatus(`Action: Create ${btn.dataset.primitive} (Pending Backend)`);
                } else if (btn.dataset.operation) {
                    Telemetry.log('UI', 'Boolean Operation (PENDING BACKEND)', { op: btn.dataset.operation });
                    this.setStatus(`Action: ${btn.dataset.operation} (Pending Backend)`);
                } else {
                    Telemetry.log('UI', 'Action (PENDING BACKEND)', { id: id });
                    this.setStatus(`Action: ${btn.title} (Pending Backend)`);
                }
                break;
        }
    }

    setActiveTool(toolId) {
        document.querySelectorAll('.toolbar-row button[id^="tool-"]').forEach(b => b.classList.remove('active'));
        document.getElementById(toolId)?.classList.add('active');
        State.set('activeTool', toolId);
        this.setStatus(`Tool changed: ${toolId.replace('tool-', '')}`);
    }

    setToolbarOpen(open) {
    const system = this.dom.topToolbarSystem;
    if (!system) return;

    system.classList.toggle('open', open);

    Telemetry.log('UI', 'Toolbar State', {
        open: open,
        pinned: system.dataset.toolbarPinned === 'true'
    });
}

toggleToolbar() {
    const system = this.dom.topToolbarSystem;
    this.setToolbarOpen(!system.classList.contains('open'));
}

    togglePanel(side) {
        const panel = (side === 'left') ? this.dom.leftPanel : this.dom.rightPanel;
        panel.classList.toggle('open');
        Telemetry.log('UI', 'Panel Toggled', { side, open: panel.classList.contains('open') });
    }

    activateTab(tabName) {
        this.dom.rightPanelTabs.forEach(tab => tab.classList.toggle('active', tab.dataset.tab === tabName));
        this.dom.rightPanelTabContents.forEach(content => content.classList.toggle('active', content.dataset.tabContent === tabName));
        Telemetry.log('UI', 'Tab Activated', { tab: tabName });
    }

    expandAssistant() {
        if (!this.dom.rightPanel.classList.contains('open')) {
            this.togglePanel('right');
        }
        this.activateTab('assistant');
    }

    handleStateChange(detail) {
        if (detail.key === 'selection') {
            this.updateSelectionInfo();
        }
        this.update();
    }

    update() {
        // Status Bar
        this.dom.statusBarSelection.textContent = `Sel: ${State.get('selection', new Set()).size}`;
        this.dom.statusBarTriangles.textContent = `Tris: ${State.get('triangleCount', 0).toLocaleString()}`;
        this.dom.statusBarEngine.textContent = `Engine: ${State.get('engineStatus', 'IDLE')}`;
    }

    updateSelectionInfo() {
        const selection = State.get('selection');
        if (!selection || selection.size === 0) {
            this.dom.selectionInfoContent.innerHTML = `<p class="placeholder">Nothing selected.</p>`;
            return;
        }

        let html = '';
        if (selection.size === 1) {
            const selectedId = selection.values().next().value;
            html = `
                <p>1 item selected: <strong>${selectedId}</strong></p>
                <div class="prop-group">
                    <label>Position (X, Y, Z)</label>
                    <input type="text" value="0.0, 0.0, 0.0" readonly>
                </div>
                <div class="prop-group">
                    <label>Material</label>
                    <input type="text" value="Steel (default)" readonly>
                </div>
            `;
        } else {
            html = `<p>${selection.size} items selected.</p>`;
        }
        html += `<button id="clear-selection">Clear Selection</button>`;
        this.dom.selectionInfoContent.innerHTML = html;

        document.getElementById('clear-selection')?.addEventListener('click', () => {
            State.set('selection', new Set());
        });
    }

    setStatus(message, isError = false, duration = 5000) {
        Telemetry.log(isError ? 'ERROR' : 'UI', 'Status Update', { message });
        this.dom.statusBarMessage.textContent = message;
        this.dom.statusBarMessage.style.color = isError ? 'var(--highlight-red)' : 'var(--text-primary)';
        if (duration > 0) {
            setTimeout(() => {
                if (this.dom.statusBarMessage.textContent === message) {
                    this.dom.statusBarMessage.textContent = 'Ready';
                    this.dom.statusBarMessage.style.color = 'var(--text-secondary)';
                }
            }, duration);
        }
    }
}



// MAGICXBF FINAL ORIENTATION GIZMO

const magicXbfOrientationGizmo =
    document.getElementById('view-cube');

if (magicXbfOrientationGizmo) {

    magicXbfOrientationGizmo.addEventListener('click', (event) => {

        const button = event.target.closest('[data-view]');

        if (!button) {
            return;
        }

        const view = button.dataset.view;

        Telemetry.log('UI', 'Orientation View', {
            view: view
        });

        const viewport = window.app?.viewport;

        if (!viewport) {
            return;
        }

        /*
         * Prefer the renderer's real camera API
         * when it exists.
         */
        if (typeof viewport.setView === 'function') {
            viewport.setView(view);
            return;
        }

        if (typeof viewport.setCameraView === 'function') {
            viewport.setCameraView(view);
            return;
        }

        /*
         * Until the renderer exposes named camera views,
         * keep ISO/Home useful.
         */
        if (
            view === 'iso' &&
            typeof viewport.fitToView === 'function'
        ) {
            viewport.fitToView();
            return;
        }

        /*
         * Future renderer hook.
         */
        document.dispatchEvent(
            new CustomEvent('magicxbf:view-request', {
                detail: {
                    view: view
                }
            })
        );
    });
}
