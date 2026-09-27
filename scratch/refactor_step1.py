import sys
import py_compile
import os

with open('app/main.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"Total lines in app/main.py: {len(lines)}")

# 1. Add open_floating_ai_chatbot_dialog above or below render_persistent_ai_chatbot_panel
chatbot_idx = None
for i, l in enumerate(lines):
    if l.startswith("def render_persistent_ai_chatbot_panel"):
        chatbot_idx = i
        break

assert chatbot_idx is not None, "render_persistent_ai_chatbot_panel not found"
print(f"render_persistent_ai_chatbot_panel at line {chatbot_idx + 1}")

# 2. Add open_floating_ai_chatbot_dialog definition right above render_persistent_ai_chatbot_panel
dialog_code = '''
@st.dialog("✨ Indian Railways AI Co-Pilot & Assistant (Groq RAG)", width="large")
def open_floating_ai_chatbot_dialog(page_context="General Dashboard", department="All"):
    """
    Renders the official Indian Railways AI Co-Pilot Assistant inside a floating modal dialog.
    Ensures zero permanent screen real-estate usage across Department and Controller pages.
    """
    render_persistent_ai_chatbot_panel(page_context=page_context, department=department)


'''

# 3. Locate department split (around line 5167)
dept_split_start = None
dept_split_end = None
for i, l in enumerate(lines):
    if "col_left, col_right = st.columns([2.2, 1.0], gap=\"medium\")" in l:
        dept_split_start = i
        break

assert dept_split_start is not None, "Department split not found"
print(f"Department split starts at line {dept_split_start + 1}")

# Find where 'with col_right:' is for department
for i in range(dept_split_start, dept_split_start + 50):
    if "with col_right:" in lines[i]:
        dept_split_end = i
        break

assert dept_split_end is not None, "Department col_right not found"
print(f"Department col_right at line {dept_split_end + 1}")

# Locate top header buttons (around line 4625)
top_col_idx = None
for i, l in enumerate(lines):
    if "top_col1, top_col2 = st.columns([5, 1.8])" in l:
        top_col_idx = i
        break

assert top_col_idx is not None, "top_col1, top_col2 not found"
print(f"top_col at line {top_col_idx + 1}")

# Locate admin split (around line 5798)
admin_split_start = None
for i, l in enumerate(lines):
    if "col_left, col_right = st.columns([2.3, 1.0], gap=\"medium\")" in l:
        admin_split_start = i
        break

assert admin_split_start is not None, "Admin split not found"
print(f"Admin split starts at line {admin_split_start + 1}")

# Locate admin col_right at the end of the file
admin_split_end = None
for i in range(len(lines) - 1, admin_split_start, -1):
    if "with col_right:" in lines[i]:
        admin_split_end = i
        break

assert admin_split_end is not None, "Admin col_right not found"
print(f"Admin col_right at line {admin_split_end + 1}")

print("All components verified successfully!")
