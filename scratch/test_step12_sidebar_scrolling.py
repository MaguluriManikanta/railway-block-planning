"""
Test Step 12: Department & Controller Side Navigation & Content Scrolling Verification
========================================================================================
Validates:
1. Persistent Sidebar: Fixed, full-height (100vh), pinned left navigation.
2. Space Reservation: Content area strictly starts AFTER sidebar (margin-left: 280px, width: calc(100% - 280px)), never behind it.
3. Independent Content Scrolling: Content area scrolls naturally with dedicated scrollbar.
4. Sidebar Back/Hide Button Removal: All collapse/hide/close buttons disabled/hidden.
5. Outside-Click Collapse Removed: No script collapsing the sidebar on page interactions.
6. Navigation Integrity: Department and Controller menu items preserved.
"""

import unittest
import os
import re

class TestSidebarAndContentScrolling(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        main_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'app', 'main.py')
        with open(main_path, 'r', encoding='utf-8') as f:
            cls.main_code = f.read()

    def test_01_persistent_sidebar_positioning(self):
        """TEST 1: Sidebar is fixed, full-height (100vh) and 280px wide."""
        self.assertIn('[data-testid="stSidebar"]', self.main_code)
        self.assertIn('position: fixed !important;', self.main_code)
        self.assertIn('width: 280px !important;', self.main_code)
        self.assertIn('height: 100vh !important;', self.main_code)

    def test_02_content_space_reservation_no_overlay(self):
        """TEST 2: Content container reserves 280px margin-left and never goes behind sidebar."""
        self.assertIn('margin-left: 280px !important;', self.main_code)
        self.assertIn('width: calc(100% - 280px) !important;', self.main_code)
        self.assertIn('max-width: calc(100% - 280px) !important;', self.main_code)

    def test_03_independent_scrolling_containers(self):
        """TEST 3: App container uses viewport height and stMain has dedicated vertical scrolling."""
        self.assertIn('[data-testid="stMain"]', self.main_code)
        self.assertIn('overflow-y: auto !important;', self.main_code)
        self.assertIn('height: 100vh !important;', self.main_code)

    def test_04_sidebar_collapse_hide_buttons_removed(self):
        """TEST 4: All sidebar collapse, hide, and back buttons are permanently hidden."""
        self.assertIn('[data-testid="stSidebarCollapseButton"]', self.main_code)
        self.assertIn('[data-testid="stSidebarCollapsedControl"]', self.main_code)
        self.assertIn('[data-testid="collapsedControl"]', self.main_code)
        self.assertIn('button[aria-label*="Close sidebar" i]', self.main_code)
        self.assertIn('display: none !important;', self.main_code)

    def test_05_no_outside_click_sidebar_collapse_script(self):
        """TEST 5: Outside-click collapse listener is completely removed."""
        self.assertNotIn('setupSidebarClickOutside', self.main_code)
        self.assertNotIn('_sidebarListenerAttached', self.main_code)

    def test_06_controller_and_department_menus_intact(self):
        """TEST 6: Both Controller and Department menu items are preserved."""
        # Department items
        self.assertIn("➕ Request Block", self.main_code)
        self.assertIn("📂 My Requests", self.main_code)
        self.assertIn("⚡ Active Work", self.main_code)
        self.assertIn("📊 Operational Overview", self.main_code)

        # Controller items
        self.assertIn("📊 Overview", self.main_code)
        self.assertIn("🚆 Locopilot Speed & Live Trains", self.main_code)
        self.assertIn("🛠️ Maintenance Status Engine", self.main_code)
        self.assertIn("📩 Department Requests", self.main_code)
        self.assertIn("📅 Maintenance Plans", self.main_code)

    def test_07_floating_ai_assistant_intact(self):
        """TEST 7: ChatMind AI single floating robot and popup remain intact."""
        self.assertIn("st-key-global_chatmind_ai_floating_btn", self.main_code)
        self.assertIn("st-key-chatmind_floating_popup_card", self.main_code)
        self.assertIn("render_floating_ai_chatbot_popup", self.main_code)


if __name__ == '__main__':
    unittest.main()
