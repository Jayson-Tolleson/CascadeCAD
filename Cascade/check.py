import sys
import re

def analyze_file(filepath):
    print(f"🔍 Analyzing {filepath}...\n")
    print("-" * 40)
    
    try:
        with open(filepath, 'r') as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"❌ Error: Could not find {filepath}")
        return

    issues_found = 0
    
    for i, line in enumerate(lines, 1):
        # 1. Check for mixed spaces and tabs in the leading indentation
        leading_whitespace = len(line) - len(line.lstrip())
        indent = line[:leading_whitespace]
        
        if ' ' in indent and '\t' in indent:
            print(f"⚠️ Line {i}: Mixed tabs and spaces in indentation.")
            issues_found += 1
            
        # 2. Check for pure tab usage (if you prefer strict space indentation)
        elif '\t' in indent:
            print(f"ℹ️ Line {i}: Uses tabs instead of spaces.")
            issues_found += 1
            
        # 3. Check for trailing whitespace
        if line.rstrip('\n') != line.rstrip():
            print(f"⚠️ Line {i}: Trailing whitespace detected.")
            issues_found += 1

    print("-" * 40)
    if issues_found == 0:
        print("✅ No formatting issues detected! Code is clean.")
    else:
        print(f"Total formatting quirks found: {issues_found}")

if __name__ == "__main__":
    # Point this directly at your ui_core.js file
    target_file = "webcad_xbf/static/js/ui_core.js"
    analyze_file(target_file)
