import os

project_js_path = "webcad_xbf/static/js/project.js"
if os.path.exists(project_js_path):
    with open(project_js_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    print(f"Total lines in project.js: {len(lines)}")
    # Print lines around potential string literal issues or search for eval / JSON / username / project
    for i, line in enumerate(lines):
        if any(k in line for k in ["username", "project", "JSON", "eval", "syntax"]):
            print(f"{i+1}: {line.strip()}")
else:
    print("project.js not found.")
