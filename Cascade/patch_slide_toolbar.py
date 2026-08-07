import os
import subprocess

# 1. Add the slide-container CSS rules to toolbar.css
css_path = "webcad_xbf/static/css/toolbar.css"
css_addition = """
/* Toolbar Slide-Up & Hover Retraction */
.cascade-topbar {
    position: relative;
    overflow: visible;
    min-height: 40px;
}

.toolbar-slide-container {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    transform: translateY(calc(-100% + 38px)); /* Hides everything except the top project bar strip */
    transition: transform 0.35s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.3s ease;
    z-index: 1000;
    background: #090d16;
    box-shadow: 0 4px 25px rgba(0, 240, 255, 0.25);
    border-bottom: 2px solid #00f0ff;
}

.toolbar-slide-container:hover {
    transform: translateY(0); /* Slides fully down into view on hover */
}
"""

if os.path.exists(css_path):
    with open(css_path, "r") as f:
        content = f.read()
    if "toolbar-slide-container" not in content:
        with open(css_path, "a") as f:
            f.write(css_addition)
        print("[+] Added toolbar-slide-container CSS rules to toolbar.css")

# 2. Add toolbar-slide-container class to the toolbar dock in project.html
html_path = "webcad_xbf/templates/project.html"
with open(html_path, "r") as f:
    html_content = f.read()

target_str = 'id="toolbar-dock" class="toolbar-dock"'
replacement_str = 'id="toolbar-dock" class="toolbar-dock toolbar-slide-container"'

if target_str in html_content and "toolbar-slide-container" not in html_content:
    html_content = html_content.replace(target_str, replacement_str)
    with open(html_path, "w") as f:
        f.write(html_content)
    print("[+] Updated project.html to include toolbar-slide-container class.")

# 3. Check JavaScript files for syntax errors using node if available
js_files = [
    "webcad_xbf/static/js/project.js",
    "webcad_xbf/static/js/project-bootstrap.js",
    "webcad_xbf/static/js/viewport.js",
    "webcad_xbf/static/js/ui_core.js"
]

print("[*] Checking JavaScript files for syntax issues...")
for js in js_files:
    if os.path.exists(js):
        res = subprocess.run(["node", "-c", js], capture_output=True, text=True)
        if res.returncode != 0:
            print(f"[!] Syntax error detected in {js}:\n{res.stderr}")
        else:
            print(f"[✓] {js} syntax OK.")

