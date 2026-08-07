import sys

def fix_trailing_whitespace(filepath):
    print(f"🧹 Cleaning trailing whitespace in {filepath}...\n")
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"❌ Error: Could not find {filepath}")
        return

    cleaned_lines = []
    fixed_count = 0
    
    for line in lines:
        # Check if the line has trailing whitespace before the newline
        if line.rstrip('\n') != line.rstrip():
            fixed_count += 1
        # Strip right-side whitespace while preserving the proper newline character
        cleaned_lines.append(line.rstrip() + '\n')

    with open(filepath, 'w', encoding='utf-8') as f:
        f.writelines(cleaned_lines)

    print("-" * 40)
    print(f"✨ Success! Stripped trailing whitespace from {fixed_count} lines.")

if __name__ == "__main__":
    target_file = "webcad_xbf/static/js/ui_core.js"
    fix_trailing_whitespace(target_file)
