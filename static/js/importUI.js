import { Telemetry } from './telemetry.js';

export class UniversalImportUI {
    constructor(app) {
        this.app = app;
        this.supportedFormats = ['.step', '.stp', '.iges', '.igs', '.stl', '.obj', '.brep', '.dxf', '.xbf'];
        this.initDOM();
        this.bindEvents();
    }

    initDOM() {
        if (document.getElementById('universal-import-modal')) return;

        const modalHtml = `
        <div id="universal-import-modal" class="import-modal-overlay hidden">
            <div class="import-modal-card">
                <div class="import-modal-header">
                    <h3>Universal CAD Ingestion</h3>
                    <button id="import-modal-close" class="close-btn">&times;</button>
                </div>
                <div class="import-modal-body">
                    <div id="drop-zone" class="drop-zone">
                        <div class="drop-zone-icon">&#128194;</div>
                        <p class="drop-title">Drag & Drop CAD Files Here</p>
                        <p class="drop-sub">Supported formats: STEP, IGES, STL, OBJ, BREP, DXF</p>
                        <button id="browse-files-btn" class="action-btn">Browse Local Files</button>
                        <input type="file" id="cad-file-input-hidden" accept=".step,.stp,.iges,.igs,.stl,.obj,.brep,.dxf,.xbf" style="display:none;">
                    </div>
                    
                    <div id="import-options" class="import-options hidden">
                        <h4>Import Settings</h4>
                        <div class="option-row">
                            <label for="import-unit">Source Unit Override:</label>
                            <select id="import-unit">
                                <option value="auto">Auto-Detect (Header)</option>
                                <option value="mm">Millimeters (mm)</option>
                                <option value="in">Inches (in)</option>
                                <option value="m">Meters (m)</option>
                            </select>
                        </div>
                        <div class="option-row">
                            <label for="tessellation-deflection">Tessellation Quality:</label>
                            <select id="tessellation-deflection">
                                <option value="0.01">Fine (High Detail)</option>
                                <option value="0.1" selected>Standard (Balanced)</option>
                                <option value="0.5">Coarse (Fast Ingest)</option>
                            </select>
                        </div>
                        <div class="option-row checkbox-row">
                            <input type="checkbox" id="auto-repair-mesh" checked>
                            <label for="auto-repair-mesh">Auto-repair manifold errors on ingest</label>
                        </div>
                    </div>
                </div>
                <div class="import-modal-footer">
                    <button id="import-cancel-btn" class="secondary-btn">Cancel</button>
                    <button id="import-process-btn" class="primary-btn hidden">Process & Ingest</button>
                </div>
            </div>
        </div>
        `;

        document.body.insertAdjacentHTML('beforeend', modalHtml);
    }

    bindEvents() {
        const modal = document.getElementById('universal-import-modal');
        const closeBtn = document.getElementById('import-modal-close');
        const cancelBtn = document.getElementById('import-cancel-btn');
        const browseBtn = document.getElementById('browse-files-btn');
        const fileInput = document.getElementById('cad-file-input-hidden');
        const dropZone = document.getElementById('drop-zone');
        const processBtn = document.getElementById('import-process-btn');

        // Close handlers
        const closeModal = () => modal.classList.add('hidden');
        closeBtn?.addEventListener('click', closeModal);
        cancelBtn?.addEventListener('click', closeModal);

        // Browse trigger
        browseBtn?.addEventListener('click', () => fileInput.click());
        fileInput?.addEventListener('change', (e) => {
            if (e.target.files.length > 0) this.handleSelectedFile(e.target.files[0]);
        });

        // Drag and Drop
        ['dragenter', 'dragover'].forEach(eventName => {
            window.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
                modal.classList.remove('hidden');
                dropZone.classList.add('drag-active');
            }, false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropZone?.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropZone.classList.remove('drag-active');
            }, false);
        });

        dropZone?.addEventListener('drop', (e) => {
            const files = e.dataTransfer.files;
            if (files.length > 0) this.handleSelectedFile(files[0]);
        });

        processBtn?.addEventListener('click', () => this.executeIngest());
    }

    open() {
        document.getElementById('universal-import-modal')?.classList.remove('hidden');
    }

    handleSelectedFile(file) {
        this.currentFile = file;
        const ext = '.' + file.name.split('.').pop().toLowerCase();
        
        if (!this.supportedFormats.includes(ext)) {
            alert(`Unsupported format "${ext}". Please select a valid CAD file.`);
            return;
        }

        Telemetry.log('IMPORT', 'File Selected', { name: file.name, size: file.size });
        
        // Show options
        document.getElementById('import-options')?.classList.remove('hidden');
        const processBtn = document.getElementById('import-process-btn');
        if (processBtn) {
            processBtn.classList.remove('hidden');
            processBtn.textContent = `Ingest ${file.name}`;
        }
    }

    async executeIngest() {
        if (!this.currentFile) return;

        const formData = new FormData();
        formData.append('file', this.currentFile);
        formData.append('unit', document.getElementById('import-unit').value);
        formData.append('deflection', document.getElementById('tessellation-deflection').value);
        formData.append('auto_repair', document.getElementById('auto-repair-mesh').checked);

        Telemetry.log('IMPORT', 'Uploading CAD Model', { file: this.currentFile.name });

        try {
            const response = await fetch('/api/import', {
                method: 'POST',
                body: formData
            });

            if (response.ok) {
                const data = await response.json();
                Telemetry.log('IMPORT', 'Ingest Successful', data);
                document.getElementById('universal-import-modal')?.classList.add('hidden');
                if (this.app.ui) this.app.ui.setStatus(`Successfully imported ${this.currentFile.name}`);
            } else {
                throw new Error(`Server returned ${response.status}`);
            }
        } catch (err) {
            Telemetry.log('ERROR', 'Import Failed', { error: err.message });
            if (this.app.ui) this.app.ui.setStatus(`Import failed: ${err.message}`, true);
        }
    }
}
