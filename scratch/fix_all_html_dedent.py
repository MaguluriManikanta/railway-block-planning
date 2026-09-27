import re
import os

def process_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Ensure clean_html is defined in the file if not already present
    clean_html_def = """
def clean_html(html_str: str) -> str:
    \"\"\"Removes leading indentation on all lines so markdown never renders HTML as code blocks.\"\"\"
    if not html_str:
        return ""
    return re.sub(r'^[ \\t]+', '', str(html_str), flags=re.MULTILINE)
"""
    if "def clean_html" not in content:
        # insert after imports
        if "import re" not in content:
            content = "import re\n" + content
        # find end of imports
        lines = content.splitlines(True)
        insert_idx = 0
        for i, l in enumerate(lines):
            if l.startswith("import ") or l.startswith("from "):
                insert_idx = i + 1
        lines.insert(insert_idx, "\n" + clean_html_def + "\n")
        content = "".join(lines)

    # Now replace st.markdown(..., unsafe_allow_html=True) where argument is not already clean_html
    # Handle st.markdown(f"""...""", unsafe_allow_html=True)
    # and st.markdown("""...""", unsafe_allow_html=True)
    # and st.markdown(var, unsafe_allow_html=True)
    
    def replacer(match):
        inner = match.group(1).strip()
        # If already clean_html(...), skip
        if inner.startswith("clean_html(") and inner.endswith(")"):
            return match.group(0)
        return f"st.markdown(clean_html({inner}), unsafe_allow_html=True)"

    pattern = r'st\.markdown\s*\(\s*([^,\n]+|\s*f?["\']{3}.*?["\']{3})\s*,\s*unsafe_allow_html\s*=\s*True\s*\)'
    new_content = re.sub(pattern, replacer, content, flags=re.DOTALL)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print(f"Processed: {filepath}")

for fp in [
    'app/classification_engine.py',
    'app/block_allocation_engine.py',
    'app/controller_requests.py',
    'app/department_notifications.py',
    'app/main.py'
]:
    process_file(fp)
