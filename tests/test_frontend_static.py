"""Static checks on the browser code: one icon set, clickable To do cards, shortcuts, Help, password help, and the photo panel."""
import re
import unittest
from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "static"
JS = (STATIC / "app.js").read_text(encoding="utf-8")
CSS = (STATIC / "style.css").read_text(encoding="utf-8")
HTML = (STATIC / "index.html").read_text(encoding="utf-8")


def icon_names():
    block = JS[JS.index("const ICONS = {"):JS.index("const OFFICE")]
    names = set(re.findall(r"^\s{2}(\w+): '<", block, re.M))
    names |= set(re.findall(r"^ICONS\.(\w+) =", block, re.M))
    return names


class IconTests(unittest.TestCase):
    def test_every_named_icon_exists(self):
        names = icon_names()
        used = set(re.findall(r"svg\('(\w+)'\)", JS))
        used |= set(re.findall(r"\['(\w+)', '[^']+', '[^']*'\]", JS)) & names  # list entries that name icons
        self.assertFalse({name for name in re.findall(r"svg\('(\w+)'\)", JS)} - names)
        for icon in ("home", "tasks", "match", "search", "inventory", "shield", "settings", "help", "notices", "logout", "menu", "close", "more", "eye", "eyeoff", "sun", "moon"):
            self.assertIn(icon, names)
        self.assertTrue(used)

    def test_one_helper_with_the_shared_line_style(self):
        self.assertEqual(JS.count("function svg("), 1)
        self.assertIn('viewBox="0 0 24 24"', JS)
        self.assertIn('stroke-width="2"', JS)
        self.assertIn('stroke-linecap="round"', JS)
        self.assertIn('aria-hidden="true"', JS)
        self.assertNotIn("<svg", JS.replace(JS[JS.index("const LOGO"):JS.index("function svg(")], "").replace(JS[JS.index("function svg("):JS.index("function svg(") + 400], ""))

    def test_no_emoji_or_text_glyph_icons(self):
        self.assertIsNone(re.search("[\u2713\u2714\u2715\u2717\u00d7\u25b8\u25be\u2605\u26a0\U0001F300-\U0001FAFF]", JS))
        self.assertNotIn("'!'", JS)

    def test_icon_only_buttons_have_label_and_tooltip(self):
        for marker in ('data-action="close-modal" aria-label="Close" title="Close"', 'aria-label="Open menu" title="Open menu"',
                       'aria-label="Sign out" title="Sign out"', 'title="More actions" aria-label="More actions"', 'class="pw-toggle"'):
            self.assertIn(marker, JS)
        self.assertRegex(CSS, r"\.pw-toggle \{[^}]*width: 44px; height: 44px")
        self.assertRegex(CSS, r"\.icon-button \{[^}]*width: 44px; height: 44px")

    def test_default_icon_size_and_nav_colors(self):
        self.assertRegex(CSS, r"\.ui-icon \{[^}]*width: 20px; height: 20px")
        self.assertIn(".nav-item.active svg { color: var(--maroon); }", CSS)
        self.assertIn(".nav-item svg { color: var(--gray-600); }", CSS)


class StaffShortcutTests(unittest.TestCase):
    def test_next_task_is_gone_everywhere(self):
        for text in ("Open next task", "next-task", "nextTaskButton", "taskQueue", "goNextTask", "task-badge", "sidebar-shortcut"):
            self.assertNotIn(text, JS + CSS)
        self.assertNotIn("next-claim", JS)
        self.assertNotIn("'Next', 'next-", JS)
        self.assertNotIn("key === 'n'", JS)
        self.assertNotIn("[['N']", JS)

    def test_todo_cards_are_real_buttons_with_a_label_and_a_calm_empty_state(self):
        self.assertNotIn("Your desk at a glance.", JS)
        self.assertIn("function kpi(", JS)
        self.assertIn("Nothing is waiting", JS)
        self.assertIn("Report for a guest", JS)
        self.assertIn("watchDeskHold", JS)
        self.assertIn("/api/reports/desk-hold", JS)
        self.assertIn("queue-line desk-step", JS)
        self.assertIn("function deskSteps(", JS)
        for kind in ("waiting", "matches", "office", "done"):
            self.assertRegex(JS, rf"data-quick|{kind}: {{ view:")
        self.assertRegex(CSS, r"\.stat-link:hover[^{]*\{[^}]*border-color: var\(--maroon\)")
        self.assertIn(".stat-link:focus-visible", CSS)
        self.assertRegex(CSS, r"button\.stat \{[^}]*cursor: pointer")

    def test_each_destination_has_a_chip_a_clear_button_and_a_matching_heading(self):
        for title in ("Waiting claims", "Matches to review", "In the office", "Done this week"):
            self.assertIn(f"title: '{title}'", JS)
        self.assertIn('data-action="clear-quick"', JS)
        self.assertIn("Clear</span>", JS)
        self.assertIn("filterChip(", JS)
        self.assertIn("URGENCY", JS)  # most urgent first, so no 'next' button is needed

    def test_sidebar_count_badges_stay(self):
        self.assertIn('class="nav-count"', JS)
        groups = JS[JS.index("function navGroups()"):JS.index("function navItems()")]
        for item in ("['matches', 'Matches', 'match']", "['updates', 'Notifications', 'notices']", "['account', 'Account', 'user']"):
            self.assertIn(item, groups)
        self.assertNotIn("topbar-bell", JS)

    def test_wizard_next_is_unchanged(self):
        self.assertIn('data-wizard="next">Next</button>', JS)

    def test_shortcut_list_and_hint(self):
        for text in ("Go to Dashboard", "Go to Matches", "Show shortcuts", "Keyboard shortcuts", "for shortcuts</p>", "GO_KEYS", "decideByKey", "showShortcuts", 'id="help-keys"', "shortcut-list"):
            self.assertNotIn(text, JS)
            self.assertNotIn(text, CSS)

    def test_handler_guards(self):
        handler = JS[JS.index("document.addEventListener('keydown', event => {\n  if (event.key !== 'Escape') return;"):JS.index("function finishRender()")]
        self.assertIn("closeMenu()", handler)
        self.assertNotIn("GO_KEYS", handler)
        self.assertNotIn("key === 'a'", handler)
        self.assertNotIn("key === '?'", handler)

    def test_approve_and_reject_open_the_confirmation_dialog_only(self):
        self.assertNotIn("function decideByKey(", JS)
        self.assertNotIn("key === 'a'", JS)
        self.assertNotIn("key === 'r'", JS)

    def test_assets_are_versioned_together(self):
        versions = set(re.findall(r"\?v=(\d+)", HTML))
        self.assertEqual(len(versions), 1)


class PasswordHelpTests(unittest.TestCase):
    def test_one_short_line_and_no_dropdown(self):
        body = JS[JS.index("function passwordSet("):JS.index("function updatePasswordHelper(")]
        self.assertNotIn("<details", body)
        self.assertNotIn("pw-guide", JS + CSS)
        self.assertIn("A few words with a number works well, like Blue-Tree-Rain-42.", body)
        for part in ("pw-checklist", "pw-bar", "data-match", "toggle-pw"):
            self.assertIn(part, JS)
        self.assertLessEqual(len(re.findall(r"\['(?:length|identity|letter|mix)',", JS)), 4)


class AuthAndWelcomeLookTests(unittest.TestCase):
    def test_photo_panel_is_fixed_size_and_only_the_opening_reveal_animates(self):
        frames = re.findall(r"@keyframes\s+([\w-]+)", CSS)
        self.assertEqual(frames, ["lyfind-open-in", "lyfind-open-out"])
        self.assertNotIn("infinite", CSS)
        self.assertNotRegex(CSS, r"scale\(")
        without_frames = re.sub(r"@keyframes\s+[\w-]+\s*\{(?:[^{}]|\{[^{}]*\})*\}", "", CSS)
        animated = []
        for selector, body in re.findall(r"([^{}]+)\{([^{}]*)\}", without_frames):
            for value in re.findall(r"animation\s*:\s*([^;]+)", body):
                value = value.strip()
                if re.fullmatch(r"none(?:\s*!important)?", value):
                    continue
                self.assertIn(".opening", selector)
                self.assertRegex(value, r"^lyfind-open-(?:in|out)\b")
                times = [float(token[:-1]) for token in re.findall(r"[\d.]+s", value)]
                self.assertLessEqual(sum(times), 1.2)
                animated.append(value)
        self.assertEqual(len(animated), 3)
        self.assertNotRegex(HTML, r"animation\s*:")
        self.assertIn('id="opening"', HTML)
        self.assertIn("sessionStorage.getItem('lyfind-opened')", JS)
        self.assertLess(JS.index("lyfind-opened"), JS.index("const app = document.querySelector('#app')"))
        self.assertIn("prefers-reduced-motion: reduce", JS)
        self.assertIn("setAttribute('data-open'", JS)
        self.assertRegex(CSS, r"@media \(prefers-reduced-motion: reduce\)[\s\S]*\.opening[^{]*\{[^}]*animation:\s*none")
        self.assertRegex(CSS, r"\.auth-art \{[^}]*height: 100vh")
        self.assertRegex(CSS, r"\.auth-art > img \{[^}]*object-fit: cover; object-position: center 35%")
        self.assertNotRegex(CSS, r"(img|\.hero-visual|\.auth-art)[^{]*:hover[^{]*\{[^}]*scale")
        self.assertIn("@media (prefers-reduced-motion: reduce)", CSS)

    def test_no_sample_figures_label_and_no_yellow_headline_underline(self):
        for text in ("Sample figures", "sample figures", "stats-note"):
            self.assertNotIn(text, JS + CSS)
        self.assertNotIn('class="hl"', JS)
        self.assertNotIn(".hl ", CSS)
        self.assertNotRegex(CSS, r"(h1|h2|h3|\.big-title|\.accent)[^{]*\{[^}]*(linear-gradient|text-decoration[^;}]*underline|border-bottom[^;}]*yellow)")
        self.assertIn("stats-strip", JS)
        self.assertNotIn("1,200+", JS)
        self.assertIn("ID required", JS)
        self.assertIn("hero-note", JS)


class HelpPageTests(unittest.TestCase):
    def test_sections_are_all_there(self):
        body = JS[JS.index("function helpContent()"):JS.index("function renderPublicHelp()")]
        for part in ("Get started", "How matching works", "What the statuses mean", "Common questions", "Contact the CSA office", 'id="help-search"', "help-tracker"):
            self.assertIn(part, body)
        self.assertNotIn("Keyboard shortcuts", body)
        self.assertIn("staff ?", body.replace("const staff = admin();", "staff ?"))  # shortcuts only for staff
        guide = JS[JS.index("const ROLE_GUIDE"):JS.index("const FAQS")]
        for name in ("Students and professors", "Guest"):
            self.assertIn(f"'{name}'", guide)
        self.assertNotIn("'CSA staff'", guide)
        self.assertNotIn("['staff'", guide)
        faqs = JS[JS.index("const FAQS"):JS.index("const STATUS_HELP")]
        self.assertEqual(faqs.count("\n  ['"), 9)
        self.assertIn("real local AI", faqs)
        banner = JS[JS.index("function aiStatus()"):JS.index("function renderToday()")]
        self.assertIn("AI is ${on ? 'on' : 'off'}", banner)
        self.assertIn("Matching runs on this computer with DINOv2 and CLIP", banner)
        self.assertIn("Photos never leave the server.", banner)
        self.assertNotIn("ChatGPT", banner)
        self.assertNotIn("OpenAI", banner)
        self.assertNotIn("This is real local AI", banner)
        self.assertNotIn("ChatGPT", faqs)
        for status in ("Reported", "Matched", "Verified", "Released"):
            self.assertIn(f"['{status}',", JS)
        self.assertIn("function filterHelp(", JS)

    def test_four_steps_per_role_and_help_links(self):
        block = JS[JS.index("const ROLE_GUIDE"):JS.index("const FAQS")]
        for role in ("lpu", "guest"):
            row = block[block.index(f"['{role}'"):]
            self.assertGreaterEqual(row[:row.index("]]")].count("', '") + 1, 3)
        self.assertIn('class="auth-foot"', JS)
        self.assertIn('class="empty-help"', JS)


class StudentEmailHintTests(unittest.TestCase):
    def test_example_and_helper_text(self):
        self.assertIn("const STUDENT_EXAMPLE = '@lpunetwork.edu.ph'", JS)
        self.assertIn("placeholder: 'Enter your ' + STUDENT_EXAMPLE", JS)
        self.assertIn("placeholder: 'Enter your email'", JS)
        self.assertIn("'Enter your password'", JS)
        self.assertIn("For LPU students and professors. Use your ${STUDENT_EXAMPLE} email.", JS)
        self.assertNotIn("name@${domain}", JS)

    def test_demo_code_notice_uses_the_demo_only_response_field(self):
        self.assertNotIn("Email is not connected on this computer", JS)
        self.assertNotIn("shown here", JS)
        self.assertIn("pending.demo_code?", JS)
        self.assertIn("We sent a 6-digit code to your Outlook inbox.", JS)


class LogoTests(unittest.TestCase):
    def test_logo_files_are_flat_and_used_everywhere(self):
        color = (STATIC / "lyfind-logo.svg").read_text(encoding="utf-8")
        white = (STATIC / "lyfind-logo-white.svg").read_text(encoding="utf-8")
        for text in (color, white):
            self.assertNotRegex(text, r"(?i)gradient|filter|<image|<text")
            self.assertIn("#f2b705", text)
        self.assertIn("#7a2438", color)
        self.assertNotIn("#7a2438", white)
        self.assertTrue((STATIC / "favicon-32.png").exists() and (STATIC / "apple-touch-icon.png").exists())
        for link in ('rel="icon" type="image/svg+xml" href="/lyfind-logo.svg', 'rel="apple-touch-icon"', 'sizes="32x32"'):
            self.assertIn(link, HTML)
        self.assertIn('src="/lyfind-logo.svg', JS)
        self.assertGreaterEqual(JS.count("class=\"logo-mark\">${LOGO}"), 4)
        self.assertNotIn("M24 12h-6a7 7 0 0 0 0 14h3", JS + HTML)


class ConfirmAndSaveTests(unittest.TestCase):
    def test_find_matches_confirms_and_does_not_rewrite_the_button(self):
        self.assertIn("Find matches now?", JS)
        self.assertNotIn("Finding…", JS)
        self.assertIn("kind === 'run-matching'", JS)
        self.assertIn("function confirmAction(", JS)

    def test_account_save_shows_a_saved_message(self):
        self.assertIn("Saved. Your account details were updated.", JS)
        self.assertIn("class=\"save-banner\"", JS)
        self.assertIn(".toast.ok", CSS)

    def test_risky_one_clicks_need_a_second_step(self):
        for text in ("Sign out of LyFind.", "Mark this guest report as checked?", "Switch this email off?", "Show this report again?"):
            self.assertIn(text, JS)
        self.assertIn("kind === 'logout'", JS)
        self.assertIn("kind === 'confirm-action'", JS)


class CampusPlacesAndDatesTests(unittest.TestCase):
    def test_places_are_lpu_cavite(self):
        for place in ("Jose P. Laurel (JPL) Building", "Sotero H. Laurel (SHL) Building", "Freedom Park",
                      "Academic Resource Center (Library)", "Chapel of the Sacred Heart of Jesus",
                      "Gate 1", "Gate 2", "CSA Office", "Other"):
            self.assertIn(f"'{place}'", JS)
        for old in ("Main Library", "Student Center", "Science Building", "Classroom building"):
            self.assertNotIn(f"'{old}'", JS)

    def test_office_uses_published_csa_contacts(self):
        self.assertIn("cav-csa@lpu.edu.ph", JS)
        self.assertIn("(046) 481-1414", JS)
        self.assertNotIn("csa.office@example.test", JS)
        self.assertNotIn("(02) 555-0142", JS)

    def test_dates_show_weekday_and_relative_labels(self):
        self.assertIn("function dateLine(", JS)
        self.assertIn("class=\"date-line\"", JS)
        self.assertIn("Date lost", JS)
        self.assertIn("Date found", JS)
        self.assertIn("'Today'", JS)
        self.assertIn("'Yesterday'", JS)

    def test_my_reports_hides_empty_chrome(self):
        body = JS[JS.index("function renderReports()"):JS.index("function foundCard(")]
        self.assertIn("showKindTabs", body)
        self.assertIn("showStatusTabs", body)
        self.assertIn("source.length >= 3", body)
        self.assertIn("total === 0", body)
        self.assertNotIn("tabs('mine'", body.replace("(showStatusTabs ? tabs('mine'", ""))


class LayoutStabilityTests(unittest.TestCase):
    def test_tabs_do_not_use_overflow_scroll_or_selected_shadow(self):
        self.assertRegex(CSS, r"\.tabs \{[^}]*overflow: hidden")
        self.assertRegex(CSS, r"\.tabs \{[^}]*flex-wrap: wrap")
        self.assertRegex(CSS, r"\.tab\[aria-selected=\"true\"\] \{[^}]*box-shadow: none")
        self.assertNotRegex(CSS, r"\.tab\[aria-selected=\"true\"\] \{[^}]*box-shadow: var\(--shadow\)")

    def test_page_head_reserves_action_space(self):
        self.assertIn('<div class="page-actions">${actions || \'\'}</div>', JS)
        self.assertIn("class=\"page-copy\"", JS)
        self.assertRegex(CSS, r"\.page-head \{[^}]*grid-template-columns")
        self.assertRegex(CSS, r"\.page-actions:empty::before \{[^}]*height: 48px")

    def test_tab_and_search_updates_reuse_the_app_shell(self):
        self.assertIn("function paintChrome(", JS)
        self.assertIn("function pageBody(", JS)
        self.assertIn("content.innerHTML = pageBody()", JS)
        self.assertIn("overflow-anchor: none", CSS)
        self.assertIn("scrollbar-gutter: stable", CSS)

    def test_long_lists_use_work_queues_and_category_filters(self):
        self.assertIn("Action needed", JS)
        self.assertIn("function lostWork(", JS)
        self.assertIn("function categorySelect(", JS)
        self.assertIn('data-list-filter="category"', JS)
        self.assertIn("function listSummary(", JS)
        self.assertIn("lost: 'need'", JS)
        self.assertIn("mine: 'open'", JS)
        self.assertIn(".tab-count", CSS)
        self.assertIn(".list-summary", CSS)


class DarkModeTests(unittest.TestCase):
    def test_theme_toggle_and_tokens(self):
        self.assertIn("html[data-theme=\"dark\"]", CSS)
        self.assertIn("lyfind-theme", JS + HTML)
        self.assertIn('data-action="toggle-theme"', JS)  # available throughout the site and inside dialogs
        self.assertNotIn("topbar-theme", JS + CSS)
        self.assertIn("data-action=\"set-theme\"", JS)
        self.assertIn("Appearance", JS)
        self.assertIn("color-scheme: dark", CSS)


class MobileMenuTests(unittest.TestCase):
    def test_overlay_cannot_cover_the_page_when_the_menu_is_closed(self):
        self.assertIn(".nav-overlay[hidden] { display: none !important; }", CSS)
        self.assertIn(".nav-overlay:not([hidden]) { display: block;", CSS)
        self.assertIn("max-width: 960px", CSS)
        self.assertIn("class=\"pub-drawer\"", JS)
        self.assertIn("data-nav=\"account\"", JS)
        self.assertIn("function renderAccount()", JS)
        self.assertIn("First name", JS)
        self.assertNotIn("Delete account", JS)
        self.assertLess(JS.index("if (state.view === 'account') return renderAccount();"), JS.index("if (admin()) {"))


if __name__ == "__main__":
    unittest.main()
