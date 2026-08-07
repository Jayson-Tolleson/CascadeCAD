import os

html_path = "webcad_xbf/templates/project.html"
with open(html_path, "r", encoding="utf-8") as f:
    content = f.read()

script_tag = '<script src="/static/js/collaboration.js"></script>'
if "collaboration.js" not in content:
    if "</body>" in content:
        content = content.replace("</body>", f"    {script_tag}\n</body>")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(content)
        print("[+] Added collaboration.js script tag to project.html")
    else:
        print("[!] Could not find </body> tag.")
else:
    print("[*] collaboration.js is already included.")

