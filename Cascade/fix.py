file_path = "webcad_xbf/static/js/project.js"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Remove our previous wiring block if it was added incorrectly
marker = "// --- CascadeCAD Module Wiring ---"
if marker in content:
    content = content.split(marker)[0]

content = content.strip()

# 2. Ensure the import statement is at the very first line of the file
import_statement = "import { initShareCapture } from './share-capture.js';\n"
if "initShareCapture" not in content:
    content = import_statement + content

# 3. Append the event listener wiring at the very bottom (WITHOUT the import)
wiring_block = """

// --- CascadeCAD Module Wiring ---
window.addEventListener('DOMContentLoaded', () => {
    try {
        const viewerElement = document.querySelector('.workspace') || document.body;
        initShareCapture({
            viewer: viewerElement,
            getSourceCanvas: () => document.querySelector('canvas'),
            getProjectName: () => document.querySelector('#project-name-input')?.value || 'CascadeCAD Project',
            appPath: (path) => `/cascade-cad${path}`,
            notify: (message, timeout) => console.log(`[UI Notify]: ${message}`)
        });
        console.log("[+] Share/Capture UI module successfully connected.");
    } catch (err) {
        console.error("[-] Failed to link UI modules:", err);
    }
});
"""

content += wiring_block

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("[+] Successfully restructured project.js with top-level import!")
