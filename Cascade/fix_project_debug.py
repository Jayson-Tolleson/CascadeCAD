import os

proj_path = "webcad_xbf/static/js/project.js"
if os.path.exists(proj_path):
    with open(proj_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    target = "const term = document.getElementById('debug-terminal');"
    replacement = """const term = document.getElementById('debug-terminal');
    if (!term) {
        console.log(`[Debug] ${msg}`);
        return;
    }"""
    
    if target in content and "if (!term)" not in content:
        content = content.replace(target, replacement, 1)
        with open(proj_path, "w", encoding="utf-8") as f:
            f.write(content)
        print("[+] Patched project.js logDebug null check successfully.")
    else:
        print("[*] project.js already patched or target not found.")

