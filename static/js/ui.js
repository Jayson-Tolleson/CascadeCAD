import { Telemetry } from './telemetry.js';
import { State } from './state.js';
import { UniversalImportUI } from './importUI.js';

export class UI {
    constructor(app) {
        this.app = app;
        try {
            this.importUI = new UniversalImportUI(this.app);
        } catch (err) {
            console.error('[MagicXBF UI] ImportUI init deferred:', err);
        }
        this.bindEvents();
        this.update();
        console.log('[MagicXBF UI] Initialized successfully.');
        Telemetry.log('UI', 'UI Initialized');
    }

    bindEvents() {
        document.addEventListener('click', (e) => {
            // 1. Top Toolbar Drawer Handle Toggle
            const topHandle = e.target.closest('#top-toolbar-handle');
            if (topHandle) {
                e.stopPropagation();
                const system = document.getElementById('top-toolbar-system') || document.getElementById('top-toolbar');
                if (system) {
                    system.classList.toggle('open');
                    Telemetry.log('UI', 'Top Toolbar Toggled', { open: system.classList.contains('open') });
                }
                return;
            }

            // 2. Left Panel Handle Toggle
            const leftHandle = e.target.closest('#left-panel-handle');
            if (leftHandle) {
                e.stopPropagation();
                const panel = document.getElementById('left-panel');
                if (panel) panel.classList.toggle('open');
                return;
            }

            // 3. Right Panel Handle Toggle
            const rightHandle = e.target.closest('#right-panel-handle');
            if (rightHandle) {
                e.stopPropagation();
                const panel = document.getElementById('right-panel');
                if (panel) panel.classList.toggle('open');
                return;
            }

            // 4. Right Panel Tab Controls
            const tabBtn = e.target.closest('.tab-button');
            if (tabBtn && tabBtn.dataset.tab) {
                this.activateTab(tabBtn.dataset.tab);
                return;
            }

            // 5. Catch ANY Toolbar Button (Flexible Container Selector)
            const btn = e.target.closest('button');
            if (btn && (btn.closest('#top-toolbar-system') || btn.closest('#top-toolbar') || btn.closest('.toolbar-row') || btn.closest('header'))) {
                e.preventDefault();
                console.log('[MagicXBF UI] Toolbar Button Click Caught:', btn.textContent.trim(), btn);
                this.handleToolbarClick(btn);
                return;
            }
        });

        // Assistant & Viewport Controls
        document.getElementById('assistant-execute')?.addEventListener('click', () => this.app.assistant?.execute());
        document.getElementById('assistant-input')?.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') this.app.assistant?.execute();
        });
        document.getElementById('assistant-expand')?.addEventListener('click', () => this.expandAssistant());
        document.getElementById('view-cube')?.addEventListener('click', () => this.app.viewport?.fitToView());

        document.addEventListener('state:change', (e) => this.handleStateChange(e.detail));
    }

    async handleToolbarClick(btn) {
        const id = (btn.id || '').toLowerCase();
        const text = btn.textContent.trim().toLowerCase();
        const actionKey = id || text;

        console.log(`[MagicXBF UI] Processing action key: "${actionKey}"`);

        // Apply active class highlighting inside the group
        const parentGroup = btn.closest('div') || btn.parentElement;
        if (parentGroup) {
            parentGroup.querySelectorAll('button').forEach(b => b.classList.remove('active'));
        }
        btn.classList.add('active');

        // Transform tools
        const transformTools = ['select', 'move', 'rotate', 'scale', 'clone', 'array', 'mirror', 'osnap'];
        const matchedTransform = transformTools.find(t => actionKey.includes(t));
        if (matchedTransform) {
            State.set('activeTool', matchedTransform);
            this.setStatus(`Tool Active: ${matchedTransform.toUpperCase()}`);
            if (this.app.viewport?.setTransformMode) {
                const modeMap = { select: 'select', move: 'translate', rotate: 'rotate', scale: 'scale' };
                if (modeMap[matchedTransform]) this.app.viewport.setTransformMode(modeMap[matchedTransform]);
            }
            return;
        }

        // Solids & Primitives
        const primitives = ['box', 'cylinder', 'sphere', 'cone', 'torus', 'helix'];
        const matchedPrimitive = primitives.find(p => actionKey.includes(p));
        if (matchedPrimitive) {
            await this.createPrimitive(matchedPrimitive);
            return;
        }

        // Modify Operations
        const modifyOps = ['fuse', 'subtract', 'split', 'fillet', 'chamfer', 'measure', 'info', 'repair', 'tessellate'];
        const matchedOp = modifyOps.find(o => actionKey.includes(o));
        if (matchedOp) {
            await this.executeOperation(matchedOp);
            return;
        }

        // Utility actions
        if (actionKey.includes('import')) {
            if (this.importUI) {
                this.importUI.open();
            } else {
                document.getElementById('cad-file-input-hidden')?.click() || document.getElementById('cad-file-input')?.click();
            }
        } else if (actionKey.includes('export')) {
            const format = prompt("Enter export format (step, iges, stl, obj)", "step");
            if (format && this.app.api) await this.app.api.export(format);
        } else if (actionKey.includes('fit')) {
            this.app.viewport?.fitToView();
        } else if (actionKey.includes('reload')) {
            window.location.reload();
        } else {
            this.setStatus(`Action triggered: ${btn.textContent.trim()}`);
        }
    }

    async createPrimitive(type) {
        this.setStatus(`Creating ${type.toUpperCase()}...`);
        Telemetry.log('CAD', 'Create Primitive', { type });

        try {
            if (this.app.api?.createPrimitive) {
                await this.app.api.createPrimitive(type);
            } else {
                const res = await fetch('/api/primitive', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ type })
                });
                if (res.ok) {
                    const data = await res.json();
                    Telemetry.log('CAD', 'Primitive Created', data);
                }
            }
        } catch (e) {
            console.warn('[MagicXBF UI] Primitive backend endpoint offline/pending:', e.message);
        }

        if (this.app.viewport?.addPrimitiveMesh) {
            this.app.viewport.addPrimitiveMesh(type);
        }

        this.setStatus(`Created ${type.toUpperCase()}`);
    }

    async executeOperation(opName) {
        const selection = State.get('selection', new Set());
        this.setStatus(`Executing ${opName.toUpperCase()} on ${selection.size} item(s)...`);
        Telemetry.log('CAD', 'Execute Operation', { op: opName, count: selection.size });

        try {
            if (this.app.api?.executeOp) {
                await this.app.api.executeOp(opName, Array.from(selection));
            } else {
                await fetch('/api/operation', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ op: opName, selection: Array.from(selection) })
                });
            }
        } catch (e) {
            console.warn('[MagicXBF UI] Operation backend endpoint offline/pending:', e.message);
        }
    }

    activateTab(tabName) {
        document.querySelectorAll('.tab-button').forEach(tab => tab.classList.toggle('active', tab.dataset.tab === tabName));
        document.querySelectorAll('.tab-content').forEach(content => content.classList.toggle('active', content.dataset.tabContent === tabName));
        Telemetry.log('UI', 'Tab Activated', { tab: tabName });
    }

    expandAssistant() {
        const rightPanel = document.getElementById('right-panel');
        if (rightPanel && !rightPanel.classList.contains('open')) {
            rightPanel.classList.add('open');
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
        const selElem = document.getElementById('status-selection');
        const triElem = document.getElementById('status-triangles');
        const engElem = document.getElementById('status-engine');

        if (selElem) selElem.textContent = `Sel: ${State.get('selection', new Set()).size}`;
        if (triElem) triElem.textContent = `Tris: ${State.get('triangleCount', 0).toLocaleString()}`;
        if (engElem) engElem.textContent = `Engine: ${State.get('engineStatus', 'IDLE')}`;
    }

    updateSelectionInfo() {
        const content = document.getElementById('selection-info-content');
        if (!content) return;
        const selection = State.get('selection');
        if (!selection || selection.size === 0) {
            content.innerHTML = `<p class="placeholder">Nothing selected.</p>`;
            return;
        }

        let html = `<p>${selection.size} item(s) selected.</p><button id="clear-selection">Clear Selection</button>`;
        content.innerHTML = html;

        document.getElementById('clear-selection')?.addEventListener('click', () => {
            State.set('selection', new Set());
        });
    }

    setStatus(message, isError = false, duration = 5000) {
        Telemetry.log(isError ? 'ERROR' : 'UI', 'Status Update', { message });
        const msgElem = document.getElementById('status-message');
        if (!msgElem) return;
        msgElem.textContent = message;
        msgElem.style.color = isError ? 'var(--accent-red)' : 'var(--text-primary)';
        if (duration > 0) {
            setTimeout(() => {
                if (msgElem.textContent === message) {
                    msgElem.textContent = 'Ready';
                    msgElem.style.color = 'var(--text-secondary)';
                }
            }, duration);
        }
    }
}
