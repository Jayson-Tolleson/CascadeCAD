document.addEventListener('DOMContentLoaded', async () => {
    const pathParts = window.location.pathname.split('/');
    const projectIndex = pathParts.indexOf('project');
    if (projectIndex !== -1 && pathParts[projectIndex + 1]) {
        const projectId = pathParts[projectIndex + 1];
        try {
            const response = await fetch(`../api/projects/${projectId}`);
            if (response.ok) {
                const projectData = await response.json();
                if (window.loadProjectState && typeof window.loadProjectState === 'function') {
                    window.loadProjectState(projectData);
                }
            }
        } catch (err) {
            console.error("Failed to hydrate project session:", err);
        }
    }
});
