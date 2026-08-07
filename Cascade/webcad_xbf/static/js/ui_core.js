/**
 * CascadeCAD Enterprise UI Core
 * Full integration controller for viewports, tabs, solids, materials, and import pipelines.
 */
window.CascadeCAD = {
    init() {
        console.log("🚀 CascadeCAD Enterprise Core Initializing...");
        this.cacheDOM();
        this.initTabs();
        this.initToolbar();
        this.initImportPipeline();
        this.initAIBar();
        console.log("✅ CascadeCAD Enterprise Core Fully Active.");
    },

    cacheDOM() {
        this.aiInput = (document.getElementById('ai-prompt-input') || { value: '' });
        this.aiBtn = (document.getElementById('ai-generate-btn') || { addEventListener: function(){}, innerHTML: '' });
        this.fileInput = document.getElementById('cad-file-input');
        this.userModal = document.getElementById('user-modal');
        this.toast = document.getElementById('toast');
    },

    // 1. Right Pane & Sidebar Tab Synchronization
    initTabs() {
        // Find all tab buttons (e.g., Selection, Users, Project Chat, Global)
        const tabButtons = document.querySelectorAll('.project-chat-tabs button, [data-tab-target], nav button');

        tabButtons.forEach(btn => {
            btn.addEventListener('click', (e) => {
                const tabName = btn.innerText.trim();
                console.log(`📑 Tab Clicked: ${tabName}`);

                // Update active button styles
                tabButtons.forEach(b => {
                    b.classList.remove('border-blue-500', 'text-white', 'bg-zinc-800');
                    b.classList.add('text-zinc-400');
                });
                btn.classList.add('border-blue-500', 'text-white', 'bg-zinc-800');
                btn.classList.remove('text-zinc-400');

                // Toggle corresponding panels if they exist in the DOM
                const targetPaneId = btn.dataset.target || tabName.toLowerCase().replace(/\s+/g, '-');
                document.querySelectorAll('.tab-pane, .project-chat-panel').forEach(pane => {
                    if (pane.id.includes(targetPaneId)) {
                        pane.classList.remove('hidden');
                    } else {
                        // Keep hidden unless it matches
                        // pane.classList.add('hidden');
                    }
                });
            });
        });
    },

    // 2. Toolbar & Solids Command Router
    initToolbar() {
        document.body.addEventListener('click', (e) => {
            const btn = e.target.closest('button');
            if (!btn) return;

            const command = btn.dataset.command || btn.innerText.trim();
            if (!command || command === '×' || command === 'Cancel' || btn.id === 'user-modal') return;

            console.log(`⚡ Tool/Solid Triggered: [${command}]`);
            this.showToast(`Action: ${command}`);

            // Route specific CAD commands to backend or viewport actions
            this.executeCADCommand(command, btn);
        });
    },


    executeCADCommand(command, btn) {
        // Grab the dynamic project ID from the body tag
        const projectId = document.body.dataset.projectId; //
        const solidTypes = ['Box', 'Cylinder', 'Pipe', 'Sphere', 'Torus', 'Cone', 'Extrude', 'Revolve'];

        if (solidTypes.includes(command)) {
            console.log(`🧱 Generating Solid primitive: ${command}`);
            // Routed to the new Command API endpoint
            this.postBackend('/cascade-cad/api/v1/commands/execute', {
                project_id: projectId,
                action: 'create_primitive',
                type: command.toLowerCase()
            });
        } else if (command === 'Undo') {
            console.log("⏪ Triggering Undo");
            this.postBackend('/cascade-cad/api/v1/commands/undo', { project_id: projectId });
        } else if (command === 'Redo') {
            console.log("⏩ Triggering Redo");
            this.postBackend('/cascade-cad/api/v1/commands/redo', { project_id: projectId });
        } else if (command === 'Material') {
            console.log("🎨 Opening Material Properties Inspector");
            // Toggle material panel or trigger inspector
        } else if (command === 'Fit' && typeof controls !== 'undefined') {
            // Reset viewport view if viewport.js?v=0.7.5 is loaded
            console.log("🔍 Fitting view to scene");
        }
    },



    // 3. Import & Upload Pipeline
        initImportPipeline() {
        // Updated to match the ID in project.html
        const importBtn = document.getElementById('import-model-btn'); //[cite: 2, 3]
        if (importBtn && this.fileInput) {
            importBtn.addEventListener('click', () => {
                console.log("📂 Opening native file picker for import");
                this.fileInput.click();
            });
        }
        // ... rest of the existing function remains the same
        if (this.fileInput) {
            this.fileInput.addEventListener('change', (e) => {
                const files = e.target.files;
                if (!files || files.length === 0) return;

                const file = files[0];
                console.log(`📦 Staged file for import: ${file.name} (${(file.size / 1024 / 1024).toFixed(2)} MB)`);

                // Integrate with existing modular import manager if loaded
                if (window.importManager && typeof window.importManager.handleFiles === 'function') {
                    window.importManager.handleFiles(files);
                } else {
                    this.uploadFileToBackend(file);
                }
            });
        }
    },

    async uploadFileToBackend(file) {
        const formData = new FormData();
        formData.append('file', file);
        const projectId = document.body.dataset.projectId; //[cite: 3]

        this.showToast(`Uploading ${file.name}...`);
        try {
            // Routed to the XBF API blueprint for this specific project
            const response = await fetch(`/${projectId}/import`, {
                method: 'POST',
                body: formData
            });
            const result = await response.json();
            console.log("✅ Upload successful:", result);
            this.showToast(`Successfully uploaded ${file.name}`);

            // Optional: Trigger a scene refresh here using the returned XBF data

        } catch (err) {
            console.error("❌ Upload failed:", err);
            this.showToast(`Upload failed for ${file.name}`);
        }
    },

    // 4. AI Engineering Assistant Bar
    initAIBar() {
        if (!this.aiBtn || !this.aiInput) return;

        const handleAI = async () => {
            const prompt = this.aiInput.value.trim();
            if (!prompt) return;

            console.log(`🤖 Dispatching AI Prompt: "${prompt}"`);
            this.aiBtn.innerHTML = `<span class="animate-pulse">Generating...</span>`;
            this.aiBtn.disabled = true;

            try {
                const response = await fetch('/cascade-cad/api/ai/generate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ prompt })
                });
                const data = await response.json();
                console.log("✨ AI Generation Result:", data);
                this.aiInput.value = '';
            } catch (e) {
                console.error("AI Generation error:", e);
            } finally {
                this.aiBtn.innerHTML = 'Generate';
                this.aiBtn.disabled = false;
            }
        };

        this.aiBtn.addEventListener('click', handleAI);
        if (this.aiInput && typeof this.aiInput.addEventListener === 'function') this.aiInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') handleAI();
        });
    },

    async postBackend(endpoint, data) {
        try {
            const res = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            return await res.json();
        } catch (err) {
            console.error(`Backend error on ${endpoint}:`, err);
        }
    },

    showToast(message) {
        if (!this.toast) return;
        this.toast.innerText = message;
        this.toast.hidden = false;

        this.toast.style.position = 'fixed';
        this.toast.style.bottom = '100px';
        this.toast.style.left = '50%';
        this.toast.style.transform = 'translateX(-50%)';
        this.toast.style.backgroundColor = '#27272a';
        this.toast.style.color = '#fff';
        this.toast.style.padding = '8px 16px';
        this.toast.style.borderRadius = '6px';
        this.toast.style.zIndex = '9999';

        clearTimeout(this.toastTimer);
        this.toastTimer = setTimeout(() => { this.toast.hidden = true; }, 2500);
    }
};

document.addEventListener('DOMContentLoaded', () => CascadeCAD.init());
