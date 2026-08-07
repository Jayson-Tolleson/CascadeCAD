import os

js_dir = "webcad_xbf/static/js"
count = 0
for root, dirs, files in os.walk(js_dir):
    for file in files:
        if file.endswith(".js"):
            path = os.path.join(root, file)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            if "export " in content:
                new_content = content.replace("export ", "")
                with open(path, "w", encoding="utf-8") as f:
                    f.write(new_content)
                print(f"[+] Stripped 'export' from {file}")
                count += 1

print(f"Total files patched: {count}")
