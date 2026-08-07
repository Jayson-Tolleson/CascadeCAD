import re

project_path = "webcad_xbf/static/js/project.js"
with open(project_path, "r", encoding="utf-8") as f:
    content = f.read()

# Look for the raw WebSocket creation line and wrap it with a safe check/fallback
old_ws_pattern = r"(const|let|var)\s+([a-zA-Z0-9_]+)\s*=\s*new\s+WebSocket\((.*?)\);"

replacement = r"""let \2 = null;
try {
    // Safely attempt WebSocket connection with error handling to prevent console spam
    \2 = new WebSocket(\3);
    \2.onerror = () => { /* Suppress noisy connection refusal logs */ };
} catch (e) {
    console.warn("WebSocket connection skipped.");
}"""

new_content = re.sub(old_ws_pattern, replacement, content, count=1)

with open(project_path, "w", encoding="utf-8", newline='\n') as f:
    f.write(new_content)

print("[+] project.js WebSocket initialization wrapped safely.")
