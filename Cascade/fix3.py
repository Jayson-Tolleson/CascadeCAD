import os
import hashlib

MANIFEST_FILE = "PACKAGE-MANIFEST.sha256"
DIRECTORIES = ["static", "templates", "scripts"]

def generate_manifest():
    print(f"Generating new hashes for {MANIFEST_FILE}...")
    manifest_lines = []
    
    for directory in DIRECTORIES:
        if not os.path.exists(directory):
            continue
        for root, _, files in os.walk(directory):
            for file in files:
                file_path = os.path.join(root, file)
                # Skip hidden files or the manifest itself
                if file.startswith('.'):
                    continue
                
                sha256_hash = hashlib.sha256()
                with open(file_path, "rb") as f:
                    for byte_block in iter(lambda: f.read(4096), b""):
                        sha256_hash.update(byte_block)
                
                rel_path = os.path.relpath(file_path, ".")
                manifest_lines.append(f"{sha256_hash.hexdigest()}  {rel_path}")

    with open(MANIFEST_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(manifest_lines) + "\n")
    
    print(f"Manifest successfully updated with {len(manifest_lines)} file entries.")

if __name__ == "__main__":
    generate_manifest()
