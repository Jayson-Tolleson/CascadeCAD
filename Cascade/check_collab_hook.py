import os

html_path = "webcad_xbf/templates/project.html"
with open(html_path, "r", encoding="utf-8") as f:
    content = f.read()

checks = {
    "Profile Dialog Markup": 'id="collaboration-profile-dialog"',
    "Collaboration JS Link": 'collaboration.js'
}

print("[*] Verifying project.html wiring...")
for name, token in checks.items():
    if token in content:
        print(f"[✓] {name}: Found")
    else:
        print(f"[!] {name}: MISSING ({token})")

