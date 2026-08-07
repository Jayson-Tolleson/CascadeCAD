import os
import re

def fix_framework_asset_urls():
    print("============================================================")
    print("🔍 REFACTORING FRAMEWORK STATIC URLS & TEMPLATES")
    print("============================================================")
    
    updated_count = 0
    
    for root, dirs, files in os.walk("."):
        if any(part.startswith('.') for part in root.split(os.sep)):
            continue
            
        for file in files:
            if file.endswith(('.py', '.html', '.jinja', '.jinja2')):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        
                    original_content = content
                    
                    # 1. Fix Flask/Quart url_for calls embedding query strings inside filename
                    # Example: url_for('static', filename='js/file.js?v=0.7.5') 
                    # Converts to: url_for('static', filename='js/file.js', v='0.7.5')
                    content = re.sub(
                        r"url_for\s*\(\s*['\"]static['\"]\s*,\s*filename\s*=\s*['\"]([^'\"]+)\?v=([^'\"]+)['\"]([^)]*)\)",
                        r"url_for('static', filename='\1', v='\2'\3)",
                        content
                    )
                    
                    # 2. Clean up any literal percent-encoded question marks in static paths
                    content = content.replace('%3F', '?')
                    
                    # 3. Clean duplicate version queries if present
                    content = content.replace('?v=0.7.5?v=0.7.5', '?v=0.7.5')
                    
                    if content != original_content:
                        with open(filepath, 'w', encoding='utf-8') as f:
                            f.write(content)
                        print(f"✅ Successfully refactored: {filepath}")
                        updated_count += 1
                except Exception as e:
                    print(f"⚠️ Error processing {filepath}: {e}")
                    
    print(f"\n✨ Refactoring complete! Updated {updated_count} file(s).")
    print("============================================================")

if __name__ == "__main__":
    fix_framework_asset_urls()
