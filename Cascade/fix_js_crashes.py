import os

# 1. Patch ui_core.js to use window.CascadeCAD to prevent redeclaration crashes
ui_path = "webcad_xbf/static/js/ui_core.js"
if os.path.exists(ui_path):
    with open(ui_path, "r", encoding="utf-8") as f:
        content = f.read()
    if "const CascadeCAD =" in content:
        content = content.replace("const CascadeCAD =", "window.CascadeCAD =")
        with open(ui_path, "w", encoding="utf-8") as f:
            f.write(content)
        print("[+] Patched ui_core.js: CascadeCAD safely assigned to window namespace.")

# 2. Patch project.js logDebug to gracefully handle missing debug-terminal
proj_path = "webcad_xbf/static/js/project.js"
if os.path.exists(proj_path):
    with open(proj_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    old_log = """function logDebug(msg, type = 'normal') {
    const term = document.getElementById('debug-terminal');
    const div = document.createElement('div');"""
    
    new_log = """function logDebug(msg, type = 'normal') {
    const term = document.getElementById('debug-terminal');
    if (!term) {
        console.log(`[Debug] ${msg}`);
        return;
    }
    const div = document.createElement('div');"""
    
    if old_log in content:
        content = content.replace(old_log, new_log)
        with open(proj_path, "w", encoding="utf-8") as f:
            f.write(content)
        print("[+] Patched project.js: logDebug handles missing terminal safely.")

