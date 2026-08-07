import os

html_path = "webcad_xbf/templates/project.html"
js_dir = "webcad_xbf/static/js"

# Gather project JS files (excluding index.js which belongs to index.html)
js_files = sorted([f for f in os.listdir(js_dir) if f.endswith(".js") and f != "index.js"])

with open(html_path, "r", encoding="utf-8") as f:
    content = f.read()

added = []
for js in js_files:
    tag = f'<script src="/static/js/{js}"></script>'
    if tag not in content:
        if "</body>" in content:
            content = content.replace("</body>", f"    {tag}\n</body>")
            added.append(js)

if added:
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[+] Added missing script tags: {', '.join(added)}")
else:
    print("[*] All project JavaScript files are already wired up.")

