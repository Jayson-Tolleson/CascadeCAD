document.addEventListener('DOMContentLoaded', () => {
    const app = new MagicXBFApp();
    app.init();
});

class MagicXBFApp {
    constructor() {
        this.state = {
            docId: null,
            capabilities: {},
            selection: [],
            isBusy: false,
            objects: [], // list of object names in the scene
        };

        this.ui = {
            toolbarContainer: document.getElementById('toolbar-container'),
            toolbarHandle: document.getElementById('toolbar-handle'),
            cadFileInput: document.getElementById('cad-file-input'),
            statusBar: {
                message: document.getElementById('status-message'),
                indicator: document.getElementById('status-indicator'),
            },
            assistant: {
                input: document.getElementById('assistant-input'),
                output: document.getElementById('assistant-output'),
            },
            sceneGraph: document.getElementById('scene-graph'),
            viewportContainer: document.getElementById('viewport-container'),
        };

        this.viewport = new Viewport(this.ui.viewportContainer, this.handleSelectionChange.bind(this));
        this.commandRegistry = new CommandRegistry(this);
    }

    async init() {
        this.showStatus('Initializing...', 'BUSY');
        this.setupEventListeners();
        
        try {
            const caps = await this.api.getCapabilities();
            this.state.capabilities = caps;
            
            const newDoc = await this.api.newDocument();
            this.state.docId = newDoc.docId;

            this.viewport.init();
            this.updateUI();
            this.showStatus('Ready. New document created.', 'READY');
        } catch (error) {
            this.showStatus(`Initialization failed: ${error.message}`, 'FAILED');
            console.error(error);
        }
    }

    setupEventListeners() {
        this.ui.toolbarHandle.addEventListener('click', () => {
            this.ui.toolbarContainer.classList.toggle('open');
        });

        document.body.addEventListener('click', (e) => {
            const commandTarget = e.target.closest('[data-command]');
            if (commandTarget) {
                const command = commandTarget.dataset.command;
                this.commandRegistry.execute(command);
            }
        });
        
        this.ui.cadFileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                this.commandRegistry.get('import_project')._handleFile(e.target.files[0]);
            }
        });

        this.ui.assistant.input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                this.commandRegistry.execute('run_assistant');
            }
        });
    }

    showStatus(message, status = 'INFO') {
        this.ui.statusBar.message.textContent = message;
        this.ui.statusBar.indicator.textContent = status;
        this.ui.statusBar.indicator.className = status;

        if (status === 'BUSY') {
            this.state.isBusy = true;
        } else {
            this.state.isBusy = false;
        }
        this.updateUI();
    }

    handleApiResponse(response) {
        if (response.tessellation) {
            this.viewport.updateScene(response.tessellation);
            this.state.objects = response.tessellation.nodes.map(n => n.name);
        }
        if (response.selection) {
            this.state.selection = response.selection;
        }
        this.updateSceneGraph();
        this.showStatus(response.message || 'Operation successful.', 'SUCCESS');
    }

    handleApiError(error) {
        this.showStatus(error.message || 'An unknown error occurred.', 'FAILED');
        console.error(error);
    }

    handleSelectionChange(selectedObjects, multiSelect) {
        // From viewport to app state
        const selectedNames = selectedObjects.map(obj => obj.name);
        if (multiSelect) {
            selectedNames.forEach(name => {
                if (!this.state.selection.includes(name)) {
                    this.state.selection.push(name);
                }
            });
        } else {
            this.state.selection = selectedNames;
        }
        this.updateSceneGraph();
    }

    updateUI() {
        document.querySelectorAll('[data-command]').forEach(el => {
            const commandName = el.dataset.command;
            const command = this.commandRegistry.get(commandName);
            let isAvailable = command ? command.isAvailable() : false;
            
            // Global busy state overrides availability
            if (this.state.isBusy && commandName !== 'fit_view') {
                isAvailable = false;
            }

            el.disabled = !isAvailable;
        });
    }

    updateSceneGraph() {
        this.ui.sceneGraph.innerHTML = '';
        this.state.objects.forEach(name => {
            const item = document.createElement('div');
            item.className = 'scene-graph-item';
            item.textContent = name;
            item.dataset.objectName = name;
            if (this.state.selection.includes(name)) {
                item.classList.add('selected');
            }
            item.addEventListener('click', (e) => {
                const objectName = e.currentTarget.dataset.objectName;
                if (e.ctrlKey || e.metaKey) {
                    // Toggle selection
                    const index = this.state.selection.indexOf(objectName);
                    if (index > -1) {
                        this.state.selection.splice(index, 1);
                    } else {
                        this.state.selection.push(objectName);
                    }
                } else {
                    this.state.selection = [objectName];
                }
                this.viewport.setSelection(this.state.selection);
                this.updateSceneGraph();
            });
            this.ui.sceneGraph.appendChild(item);
        });
        this.viewport.setSelection(this.state.selection);
        this.updateUI(); // Update command availability based on selection
    }

    api = {
        getCapabilities: async () => {
            const response = await fetch('/api/engine/capabilities');
            if (!response.ok) throw new Error('Failed to fetch capabilities');
            return response.json();
        },
        newDocument: async () => {
            const response = await fetch('/api/document/new', { method: 'POST' });
            if (!response.ok) throw new Error('Failed to create new document');
            return response.json();
        },
        runCommand: async (docId, command, params = {}) => {
            const response = await fetch(`/api/document/${docId}/command`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ command, params: {...params, selection: this.state.selection} }),
            });
            const result = await response.json();
            if (!response.ok) throw new Error(result.error || 'Command failed');
            return result;
        },
        uploadFile: async (docId, file) => {
            const formData = new FormData();
            formData.append('cad-file', file);
            const response = await fetch(`/api/document/${docId}/import`, {
                method: 'POST',
                body: formData,
            });
            const result = await response.json();
            if (!response.ok) throw new Error(result.error || 'Import failed');
            return result;
        }
    };
}

class CommandRegistry {
    constructor(app) {
        this.app = app;
        this.commands = {
            // PROJECT
            import_project: new Command(app, {
                execute: () => this.app.ui.cadFileInput.click(),
                _handleFile: async (file) => {
                    this.app.showStatus(`Importing ${file.name}...`, 'BUSY');
                    try {
                        const res = await this.app.api.uploadFile(this.app.state.docId, file);
                        this.app.handleApiResponse(res);
                        this.app.commandRegistry.execute('fit_view');
                    } catch (e) { this.app.handleApiError(e); }
                },
                isAvailable: () => this.app.state.capabilities.commands
            }),
            export_project: new Command(app, {
                execute: () => {
                    const formats = this.app.state.capabilities.export_formats || [];
                    if (formats.length === 0) {
                        this.app.showStatus('No export formats available.', 'FAILED');
                        return;
                    }
                    const options = formats.map(f => `<option value="${f.toLowerCase()}">${f}</option>`).join('');
                    const xbfSupported = formats.includes('STEP'); // Our alias for STEP
                    const xbfOption = xbfSupported ? `<option value="xbf">MagicXBF (.xbf)</option>` : '';

                    const body = `
                        <div class="form-group">
                            <label for="export-format">Format</label>
                            <select id="export-format">
                                ${xbfOption}
                                ${options}
                            </select>
                        </div>
                        <div class="modal-footer">
                            <button id="export-confirm-btn" class="primary">Export</button>
                        </div>
                    `;
                    Modal.show('Export Document', body, (modalRoot) => {
                        modalRoot.querySelector('#export-confirm-btn').onclick = () => {
                            const format = modalRoot.querySelector('#export-format').value;
                            const url = `/api/document/${this.app.state.docId}/export?format=${format}`;
                            window.location.href = url; // Trigger download
                            Modal.hide();
                        };
                    });
                },
                isAvailable: () => this.app.state.objects.length > 0
            }),
            fit_view: new Command(app, { execute: () => this.app.viewport.fitToScene() }),
            
            // TRANSFORM
            select_all: new Command(app, {
                execute: () => {
                    this.app.state.selection = [...this.app.state.objects];
                    this.app.updateSceneGraph();
                },
                isAvailable: () => this.app.state.objects.length > 0
            }),
            clear_selection: new Command(app, {
                execute: () => {
                    this.app.state.selection = [];
                    this.app.updateSceneGraph();
                },
                isAvailable: () => this.app.state.selection.length > 0
            }),

            // SOLIDS
            ...this._createPrimitiveCommands(['box', 'cylinder', 'sphere', 'cone', 'torus']),

            // MODIFY
            modify_fuse: new Command(app, {
                execute: () => this._runApiCommand('modify_fuse'),
                isAvailable: () => this.app.state.capabilities.commands?.modify_fuse && this.app.state.selection.length >= 2
            }),
            modify_subtract: new Command(app, {
                execute: () => this._runApiCommand('modify_subtract'),
                isAvailable: () => this.app.state.capabilities.commands?.modify_subtract && this.app.state.selection.length >= 2
            }),
            get_info: new Command(app, {
                execute: async () => {
                    this.app.showStatus('Getting info...', 'BUSY');
                    try {
                        const res = await this.app.api.runCommand(this.app.state.docId, 'get_info');
                        Modal.show('Object Information', `<pre>${res.message}</pre>`);
                        this.app.showStatus('Info retrieved.', 'SUCCESS');
                    } catch (e) { this.app.handleApiError(e); }
                },
                isAvailable: () => this.app.state.capabilities.commands?.get_info && this.app.state.selection.length === 1
            }),
            tessellate: new Command(app, { execute: () => this._runApiCommand('tessellate') }),

            // ASSISTANT
            run_assistant: new Command(app, {
                execute: async () => {
                    const text = this.app.ui.assistant.input.value;
                    if (!text) return;
                    this.app.ui.assistant.output.innerHTML += `> ${text}\n`;
                    this.app.ui.assistant.input.value = '';
                    this.app.showStatus('Assistant processing...', 'BUSY');
                    try {
                        const res = await this.app.api.runCommand(this.app.state.docId, 'assistant_command', { text });
                        this.app.handleApiResponse(res);
                        this.app.ui.assistant.output.innerHTML += `<span style="color: var(--success-color);">${res.message}</span>\n`;
                    } catch (e) {
                        this.app.handleApiError(e);
                        this.app.ui.assistant.output.innerHTML += `<span style="color: var(--error-color);">${e.message}</span>\n`;
                    }
                    this.app.ui.assistant.output.scrollTop = this.app.ui.assistant.output.scrollHeight;
                },
                isAvailable: () => this.app.state.capabilities.commands?.assistant
            }),
        };
    }

    get(name) { return this.commands[name]; }

    async execute(name) {
        const command = this.get(name);
        if (command && command.isAvailable() && !this.app.state.isBusy) {
            try {
                await command.execute();
            } catch (e) {
                this.app.handleApiError(e);
            }
        } else {
            console.warn(`Command "${name}" not available or app is busy.`);
        }
    }

    _createPrimitiveCommands(types) {
        const commands = {};
        types.forEach(type => {
            const commandName = `create_${type}`;
            commands[commandName] = new Command(this.app, {
                execute: () => this._runApiCommand(commandName, {}), // Using default params for now
                isAvailable: () => this.app.state.capabilities.commands?.[commandName]
            });
        });
        return commands;
    }

    async _runApiCommand(command, params = {}) {
        this.app.showStatus(`Executing ${command}...`, 'BUSY');
        try {
            const res = await this.app.api.runCommand(this.app.state.docId, command, params);
            this.app.handleApiResponse(res);
        } catch (e) {
            this.app.handleApiError(e);
        }
    }
}

class Command {
    constructor(app, { execute, isAvailable, _handleFile }) {
        this.app = app;
        this.execute = execute || (() => console.warn('Execute not implemented.'));
        this._isAvailable = isAvailable;
        this._handleFile = _handleFile; // For import command
    }
    isAvailable() {
        if (this._isAvailable) {
            return this._isAvailable();
        }
        return true; // Default to available if no check is provided
    }
}

class Viewport {
    constructor(container, selectionCallback) {
        this.container = container;
        this.selectionCallback = selectionCallback;
        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.controls = null;
        this.raycaster = new THREE.Raycaster();
        this.mouse = new THREE.Vector2();
        this.outlinePass = null;
        this.selectedObjects = [];
    }

    init() {
        // Scene
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0x282c34);

        // Camera
        this.camera = new THREE.PerspectiveCamera(75, this.container.clientWidth / this.container.clientHeight, 0.1, 1000);
        this.camera.position.set(30, 30, 30);

        // Renderer
        this.renderer = new THREE.WebGLRenderer({ antialias: true });
        this.renderer.setSize(this.container.clientWidth, this.container.clientHeight);
        this.container.appendChild(this.renderer.domElement);

        // Lights
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
        this.scene.add(ambientLight);
        const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
        directionalLight.position.set(50, 50, 50);
        this.scene.add(directionalLight);

        // Controls
        this.controls = new THREE.OrbitControls(this.camera, this.renderer.domElement);

        // Grid
        const gridHelper = new THREE.GridHelper(100, 10);
        this.scene.add(gridHelper);

        // Event Listeners
        window.addEventListener('resize', this.onWindowResize.bind(this), false);
        this.renderer.domElement.addEventListener('pointerdown', this.onPointerDown.bind(this), false);

        this.animate();
    }

    animate() {
        requestAnimationFrame(this.animate.bind(this));
        this.controls.update();
        this.renderer.render(this.scene, this.camera);
    }

    onWindowResize() {
        this.camera.aspect = this.container.clientWidth / this.container.clientHeight;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(this.container.clientWidth, this.container.clientHeight);
    }

    updateScene({ nodes }) {
        // Clear existing objects
        const objectsToRemove = this.scene.children.filter(child => child.isMesh);
        objectsToRemove.forEach(child => {
            this.scene.remove(child);
            child.geometry.dispose();
            child.material.dispose();
        });
        this.selectedObjects = [];

        // Add new objects
        const material = new THREE.MeshStandardMaterial({ color: 0xcccccc, metalness: 0.3, roughness: 0.5 });
        nodes.forEach(node => {
            const geometry = new THREE.BufferGeometry();
            geometry.setAttribute('position', new THREE.Float32BufferAttribute(node.vertices, 3));
            geometry.setIndex(node.faces);
            geometry.computeVertexNormals();
            const mesh = new THREE.Mesh(geometry, material.clone());
            mesh.name = node.name;
            this.scene.add(mesh);
        });
    }
    
    setSelection(objectNames) {
        // From app state to viewport
        this.selectedObjects.forEach(obj => obj.material.color.set(0xcccccc));
        this.selectedObjects = [];

        objectNames.forEach(name => {
            const obj = this.scene.getObjectByName(name);
            if (obj) {
                this.selectedObjects.push(obj);
                obj.material.color.set(0x61afef); // Highlight color
            }
        });
    }

    onPointerDown(event) {
        event.preventDefault();
        const rect = this.renderer.domElement.getBoundingClientRect();
        this.mouse.x = ((event.clientX - rect.left) / this.container.clientWidth) * 2 - 1;
        this.mouse.y = -((event.clientY - rect.top) / this.container.clientHeight) * 2 + 1;

        this.raycaster.setFromCamera(this.mouse, this.camera);
        const intersects = this.raycaster.intersectObjects(this.scene.children.filter(c => c.isMesh));

        if (intersects.length > 0) {
            const firstIntersected = intersects[0].object;
            this.selectionCallback([firstIntersected], event.ctrlKey || event.metaKey);
        } else {
            if (!event.ctrlKey && !event.metaKey) {
                this.selectionCallback([], false);
            }
        }
    }

    fitToScene() {
        const box = new THREE.Box3();
        const meshes = this.scene.children.filter(c => c.isMesh);
        if (meshes.length === 0) return;

        meshes.forEach(mesh => box.expandByObject(mesh));

        const size = box.getSize(new THREE.Vector3());
        const center = box.getCenter(new THREE.Vector3());
        const maxSize = Math.max(size.x, size.y, size.z);
        const fitHeightDistance = maxSize / (2 * Math.atan(Math.PI * this.camera.fov / 360));
        const fitWidthDistance = fitHeightDistance / this.camera.aspect;
        const distance = 1.5 * Math.max(fitHeightDistance, fitWidthDistance);

        const direction = this.controls.target.clone().sub(this.camera.position).normalize().multiplyScalar(distance);

        this.controls.maxDistance = distance * 10;
        this.controls.target.copy(center);
        this.camera.near = distance / 100;
        this.camera.far = distance * 100;
        this.camera.updateProjectionMatrix();
        this.camera.position.copy(this.controls.target).sub(direction);
        this.controls.update();
    }
}

const Modal = {
    show: (title, body, setupCallback) => {
        document.getElementById('modal-title').textContent = title;
        const modalBody = document.getElementById('modal-body');
        modalBody.innerHTML = body;
        document.getElementById('modal-backdrop').classList.remove('hidden');
        const modal = document.getElementById('generic-modal');
        modal.classList.remove('hidden');
        if (setupCallback) {
            setupCallback(modal);
        }
        document.getElementById('modal-close-btn').onclick = Modal.hide;
    },
    hide: () => {
        document.getElementById('modal-backdrop').classList.add('hidden');
        document.getElementById('generic-modal').classList.add('hidden');
    }
};