import sys
import os
import py_compile

with open('app/main.py', 'r', encoding='utf-8') as f:
    orig_code = f.read()

# Make a backup
with open('app/main.py.bak', 'w', encoding='utf-8') as f:
    f.write(orig_code)

lines = orig_code.splitlines(True)

# 1. Insert open_floating_ai_chatbot_dialog
chatbot_dialog_code = '''
@st.dialog("✨ Indian Railways AI Co-Pilot & Assistant (Groq RAG)", width="large")
def open_floating_ai_chatbot_dialog(page_context="General Dashboard", department="All"):
    """
    Renders the official Indian Railways AI Co-Pilot Assistant inside a modal dialog.
    Ensures zero permanent screen real-estate usage across Department and Controller pages.
    """
    render_persistent_ai_chatbot_panel(page_context=page_context, department=department)


'''

idx_chat_def = next(i for i, l in enumerate(lines) if l.startswith("def render_persistent_ai_chatbot_panel"))
lines.insert(idx_chat_def, chatbot_dialog_code)

# 2. Modify sidebar to include floating AI launcher
idx_logout = next(i for i, l in enumerate(lines) if "if st.sidebar.button(\"🚪 Sign Out\"" in l)
sidebar_ai_code = '''
st.sidebar.markdown("---")
if st.sidebar.button("💬 Open AI Assistant", key="sidebar_floating_ai_btn", use_container_width=True, help="Open Floating AI Assistant Modal"):
    open_floating_ai_chatbot_dialog(
        page_context=f"Department Portal ({my_dept}) > {dept_menu}" if is_dept_user else f"Central Controller > {admin_menu}",
        department=my_dept if is_dept_user else "All"
    )
'''
lines.insert(idx_logout, sidebar_ai_code)

# Re-index lines
full_text = "".join(lines)
lines = full_text.splitlines(True)

# 3. Update top header columns for Department & Controller
idx_top_col = next(i for i, l in enumerate(lines) if "top_col1, top_col2 = st.columns([5, 1.8])" in l)
lines[idx_top_col] = "top_col1, top_col2 = st.columns([4.2, 2.8])\n"

full_text = "".join(lines)

# Dept header buttons
old_dept_part = '''    if is_dept_user:
        badge_label = f"🔔 Alerts ({unread_count})" if unread_count > 0 else "🔔 Alerts (0)"
        with st.popover(badge_label, use_container_width=True):
            render_alerts_popover_content(notif_rows, unread_count, key_prefix="dept")'''

new_dept_part = '''    if is_dept_user:
        d_c1, d_c2 = st.columns([1.1, 1.2])
        with d_c1:
            badge_label = f"🔔 Alerts ({unread_count})" if unread_count > 0 else "🔔 Alerts (0)"
            with st.popover(badge_label, use_container_width=True):
                render_alerts_popover_content(notif_rows, unread_count, key_prefix="dept")
        with d_c2:
            if st.button("💬 AI Assistant", key="dept_hdr_ai_btn", use_container_width=True, help="Open Indian Railways AI Assistant"):
                open_floating_ai_chatbot_dialog(page_context=f"Department Portal ({my_dept}) > {dept_menu}", department=my_dept)'''

assert old_dept_part in full_text, "old_dept_part not found"
full_text = full_text.replace(old_dept_part, new_dept_part, 1)

# Controller header columns: 2 to 3
old_ctrl_hdr_cols = "        h_c1, h_c2 = st.columns([1.1, 1.0])"
new_ctrl_hdr_cols = "        h_c1, h_c2, h_c3 = st.columns([1.1, 1.0, 1.2])"
assert old_ctrl_hdr_cols in full_text, "old_ctrl_hdr_cols not found"
full_text = full_text.replace(old_ctrl_hdr_cols, new_ctrl_hdr_cols, 1)

# Controller header alerts + AI Assistant button
old_h_c2_block = '''        with h_c2:
            badge_label = f"🔔 Alerts ({unread_count})" if unread_count > 0 else "🔔 Alerts (0)"
            with st.popover(badge_label, use_container_width=True):
                render_alerts_popover_content(notif_rows, unread_count, key_prefix="ctrl")'''

new_h_c2_block = '''        with h_c2:
            badge_label = f"🔔 Alerts ({unread_count})" if unread_count > 0 else "🔔 Alerts (0)"
            with st.popover(badge_label, use_container_width=True):
                render_alerts_popover_content(notif_rows, unread_count, key_prefix="ctrl")
        with h_c3:
            if st.button("💬 AI Assistant", key="ctrl_hdr_ai_btn", use_container_width=True, help="Open Indian Railways AI Assistant"):
                open_floating_ai_chatbot_dialog(page_context=f"Central Controller > {admin_menu}", department="All")'''

assert old_h_c2_block in full_text, "old_h_c2_block not found"
full_text = full_text.replace(old_h_c2_block, new_h_c2_block, 1)

lines = full_text.splitlines(True)

# 4. Department Portal Full Width (remove col_left, col_right)
idx_dept_split = next(i for i, l in enumerate(lines) if "col_left, col_right = st.columns([2.2, 1.0], gap=\"medium\")" in l)
idx_dept_right = next(i for i, l in enumerate(lines[idx_dept_split:]) if "with col_right:" in l) + idx_dept_split
idx_dept_right_end = idx_dept_right + 2

dept_content = []
for line in lines[idx_dept_split + 2:idx_dept_right]:
    if line.startswith("        "):
        dept_content.append(line[4:])
    elif line.startswith("    "):
        dept_content.append(line[4:])
    else:
        dept_content.append(line)

lines[idx_dept_split:idx_dept_right_end] = dept_content

full_text = "".join(lines)
lines = full_text.splitlines(True)

# 5. Locopilot Speed expander replaced with button
loco_exp_old = '''        with st.expander("💬 AI Assistant & Operational Co-Pilot", expanded=False):
            render_persistent_ai_chatbot_panel(page_context=f"Central Controller > {admin_menu}", department="All")'''

loco_exp_new = '''        if st.button("💬 Open AI Assistant & Operational Co-Pilot", key="loco_open_ai_assistant_btn"):
            open_floating_ai_chatbot_dialog(page_context=f"Central Controller > {admin_menu}", department="All")'''

if loco_exp_old in full_text:
    full_text = full_text.replace(loco_exp_old, loco_exp_new)
    lines = full_text.splitlines(True)

# 6. Controller Pages Full Width (remove col_left, col_right)
idx_admin_split = next(i for i, l in enumerate(lines) if "col_left, col_right = st.columns([2.3, 1.0], gap=\"medium\")" in l)
idx_admin_right = None
for i in range(len(lines) - 1, idx_admin_split, -1):
    if "with col_right:" in lines[i]:
        idx_admin_right = i
        break

assert idx_admin_right is not None, "Admin col_right not found at end"

admin_content = []
for line in lines[idx_admin_split + 2:idx_admin_right]:
    if line.startswith("            "):
        admin_content.append(line[4:])
    elif line.startswith("        "):
        admin_content.append(line[4:])
    else:
        admin_content.append(line)

lines[idx_admin_split:] = admin_content

new_full_text = "".join(lines)

with open('scratch/test_main.py', 'w', encoding='utf-8') as f:
    f.write(new_full_text)

print("Saved scratch/test_main.py. Testing py_compile...")
py_compile.compile('scratch/test_main.py', doraise=True)
print("SUCCESS: scratch/test_main.py compiled with ZERO syntax/indentation errors!")
