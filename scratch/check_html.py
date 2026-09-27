import os
import glob
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

for path in glob.glob('app/**/*.py', recursive=True):
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    # Search for st.markdown(f""" or st.markdown("""
    matches = re.finditer(r'st\.markdown\s*\(\s*(f?["\']{3}.*?["\']{3})\s*,\s*unsafe_allow_html\s*=\s*True\s*\)', content, re.DOTALL)
    for m in matches:
        start_pos = m.start()
        line_no = content[:start_pos].count('\n') + 1
        snippet = m.group(1)[:60].replace('\n', '\\n')
        print(f"MULTILINE INLINE: {path}:{line_no} -> {snippet}")

print("Scan complete.")
