export class UI {
    constructor(app) {
        this.app = app;
        this.dom = {
            topToolbar: document.getElementById('top-toolbar-system'),
            leftPanel: document.getElementById('left-panel'),
            rightPanel: document.getElementById('right-panel'),
            assemblyTree: document.getElementById('assembly-tree'),
            propertiesContent: document.getElementById('properties-content'),
            selectionInfoContent: document.getElementById('selection-info-content'),
            statusMessage: document.getElementById('status-message'),
            statusSelection: document.getElementById('status-selection'),
            statusTriangles: document.getElementById('status-triangles'),
            statusEngine: document.getElementById('status-engine'),
            importFileInput: document.getElementById('import-file-input'),
        };
    }

    initialize() {
        this.bindEvents();
        this.updateAssemblyTree([]);
        this.updatePropertiesPanel(null);
        this.updateSelectionInfo();
        this.app.Telemetry.log('UI', 'UI Initialized');
    }

    bindEvents() {
        // Panel & Toolbar Toggles
        document.addEventListener('click', (e) => {
            const topHandle = e.target.closest('#top-toolbar-handle');
            if (topHandle) this.togglePanel(this.dom.topToolbar);

            const leftHandle = e.target.closest('#left-panel-handle');
            if (leftHandle) this.togglePanel(this.dom.leftPanel);

            const rightHandle = e.target.closest('#right-panel-handle');
            if (rightHandle) this.togglePanel(this.dom.rightPanel);
        });

        // Right Panel Tabs
        this.dom.rightPanel.addEventListener('click', (e) => {
            const tabBtn = e.target.closest('.tab-button[data-tab]');
            if (tabBtn) this.activateTab(tabBtn.dataset.tab);
        });

        // Toolbar Buttons
        this.dom.topToolbar.addEventListener('click', (e) => {
            const button = e.target.closest('button');
            if (button) this.handleToolbarClick(button);
        });

        // Assembly Tree Selection
        this.dom.assemblyTree.addEventListener('click', (e) => {
            const item = e.target.closest('li[data-part-id]');
            if (item) {
                const partId = item.dataset.partId;
                const selection = new Set(this.app.State.get('selection'));
                if (e.ctrlKey || e.metaKey) {
                    selection.has(partId) ? selection.delete(partId) : selection.add(partId);
                } else {
                    selection.clear();
                    selection.add(partId);
                }
                this.app.State.set('selection', selection);
            }
        });

        // State Changes
        document.addEventListener('state:change', (e) => this.handleStateChange(e.detail));
        
        // File Input
        this.dom.importFileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                this.handleFileImport(e.target.files[0]);
            }
        });
    }

    handleStateChange({ key, value }) {
        switch (key) {
            case 'selection':
                this.updateAssemblyTree(this.app.State.get('parts'));
                this.updateSelectionInfo();
                this.updatePropertiesPanel();
                this.app.Viewport.updateSelectionHighlight(value);
                break;
            case 'parts':
                this.updateAssemblyTree(value);
                break;
            case 'triangleCount':
                this.dom.statusTriangles.textContent = `Tris: ${value.toLocaleString()}`;
                break;
        }
    }

    togglePanel(panelElement) {
        panelElement.classList.toggle('open');
        this.app.Telemetry.log('UI', 'Panel Toggled', { id: panelElement.id, open: panelElement.classList.contains('open') });
        // Inform viewport of potential resize
        setTimeout(() => window.dispatchEvent(new Event('resize')), 300);
    }

    activateTab(tabName) {
        const parent = this.dom.rightPanel;
        parent.querySelectorAll('.tab-button').forEach(tab => tab.classList.toggle('active', tab.dataset.tab === tabName));
        parent.querySelectorAll('.tab-content').forEach(content => content.classList.toggle('active', content.dataset.tabContent === tabName));
        this.app.Telemetry.log('UI', 'Tab Activated', { tab: tabName });
    }

    expandAssistant() {
        if (!this.dom.rightPanel.classList.contains('open')) {
            this.togglePanel(this.dom.rightPanel);
        }
        this.activateTab('assistant');
    }

    async handleToolbarClick(button) {
        const { API, State, Telemetry } = this.app;
        if (button.disabled) return;

        const id = button.id;
        const primitive = button.dataset.primitive;
        const operation = button.dataset.operation;

        Telemetry.log('CMD', 'Toolbar command', { id, primitive, operation });

        if (primitive) {
            const response = await API.sendCommand(`create_${primitive}`);
            this.app.handleApiResponse(response);
        } else if (operation) {
            const selection = Array.from(State.get('selection'));
            if (selection.length < 2) {
                this.setStatus('Boolean operations require at least 2 parts selected.', true);
                return;
            }
            const response = await API.sendCommand(operation, {}, selection);
            this.app.handleApiResponse(response);
        } else {
            // Handle by ID
            switch (id) {
                case 'import-model-btn':
                    this.dom.importFileInput.click();
                    break;
                case 'export-button':
                    const format = prompt("Enter export format (step, stl, xbf):", "step");
                    if (format) await API.exportFile(format);
                    break;
                case 'fit-view':
                    this.app.Viewport.fitToView();
                    break;
                case 'reload-master':
                    window.location.reload();
                    break;
                case 'tessellate-model':
                    this.app.handleApiResponse({status: 'success', message: 'Forcing retessellation...'});
                    break;
                default:
                    this.setStatus(`Command '${button.textContent}' is pending backend implementation.`, false, 'info');
                    Telemetry.log('WARN', 'Pending command clicked', { id });
            }
        }
    }
    
    async handleFileImport(file) {
        this.setStatus(`Importing ${file.name}...`, false, 'info');
        const response = await this.app.API.uploadFile(file);
        this.app.handleApiResponse(response);
        // Clear the input value to allow re-importing the same file
        this.dom.importFileInput.value = '';
    }

    updateAssemblyTree(parts = []) {
        if (parts.length === 0) {
            this.dom.assemblyTree.innerHTML = `<li class="placeholder">No parts in document</li>`;
            return;
        }

        const selection = this.app.State.get('selection');
        let html = '';
        parts.forEach(part => {
            const isSelected = selection.has(part.id);
            html += `<li data-part-id="${part.id}" class="${isSelected ? 'selected' : ''}">${part.name}</li>`;
        });
        this.dom.assemblyTree.innerHTML = html;
    }

    updateSelectionInfo() {
        const selection = this.app.State.get('selection');
        this.dom.statusSelection.textContent = `Sel: ${selection.size}`;

        if (selection.size === 0) {
            this.dom.selectionInfoContent.innerHTML = `<p class="placeholder">Nothing selected.</p>`;
        } else {
            this.dom.selectionInfoContent.innerHTML = `<p>${selection.size} part(s) selected.</p>`;
        }
    }

    updatePropertiesPanel() {
        const selection = this.app.State.get('selection');
        const parts = this.app.State.get('parts');
        
        if (selection.size !== 1) {
            this.dom.propertiesContent.innerHTML = `<p class="placeholder">${selection.size > 1 ? 'Multiple parts selected.' : 'Select a single part to see properties.'}</p>`;
            return;
        }

        const selectedId = selection.values().next().value;
        const part = parts.find(p => p.id === selectedId);

        if (!part) {
            this.dom.propertiesContent.innerHTML = `<p class="placeholder">Selected part not found.</p>`;
            return;
        }

        this.dom.propertiesContent.innerHTML = `
            <div><strong>Name:</strong> <input type="text" value="${part.name}"></div>
            <div><strong>ID:</strong> <span style="font-family: var(--font-mono); font-size: 11px;">${part.id}</span></div>
            <br>
            <p class="placeholder">More properties (transform, material, etc.) are pending implementation.</p>
        `;
    }

    setStatus(message, isError = false, type = 'info', duration = 5000) {
        if (!this.dom.statusMessage) return;
        this.dom.statusMessage.textContent = message;
        this.dom.statusMessage.className = isError ? 'error' : type;

        if (this._statusTimeout) clearTimeout(this._statusTimeout);
        if (duration > 0) {
            this._statusTimeout = setTimeout(() => {
                if (this.dom.statusMessage.textContent === message) {
                    this.dom.statusMessage.textContent = 'Ready';
                    this.dom.statusMessage.className = '';
                }
            }, duration);
        }
    }

    setEngineStatus(status) { // IDLE, BUSY
        this.dom.statusEngine.textContent = `Engine: ${status}`;
        this.dom.statusEngine.style.color = status === 'BUSY' ? 'var(--accent-amber)' : 'var(--text-secondary)';
    }
}