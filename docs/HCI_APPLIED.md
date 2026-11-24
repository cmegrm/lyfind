# HCI changes for the report

Use one slide per row. Screenshot the live site at `http://127.0.0.1:8765` for the “after” column. The class demo accounts are Student, Guest, Professor, and CSA staff.

| Principle | Problem in the old design | What changed | Where to show it |
| --- | --- | --- | --- |
| Norman: affordances | Primary, quiet, and disabled actions looked similar. Later steps were hidden instead of explained. | One burgundy primary button. Every other action is an outline, and Reject and Dismiss use a maroon outline. Tabs are one light segmented control with a white, maroon-outlined active tab. A disabled button stays visible and says why, for example “Get consent first.” | Staff claim card, before consent is recorded. |
| Norman: feedback | A slow match and a saved form both felt the same. Release ended on a small toast. | Buttons say “Saving…” or “Finding…”. A top progress bar shows while the server works. Release ends on a Done screen: who received the item and the date. | Find matches. Hand over. |
| Norman: constraints | Place, color, and category were free text. A future lost date could be typed. | Category, place, and color are dropdowns. Lost and found dates cannot be in the future. Photos accept PNG, JPEG, or WebP only. | Report lost, steps 1 and 2. |
| Norman: mapping | Staff actions were easy to lose among menus. | Approve, reject, confirm, and dismiss sit on the item card they affect. | Claims → Matches. |
| Norman: conceptual model | Status codes such as `step1_pending` described the database, not the person’s task. | Every owner screen shows Reported, Matched, Verified, Released. The database codes stay internal. | Student home, My reports, My claims, Updates. |
| Norman: error recovery | Some errors named fields or codes. Approve and release were easy to hit by accident. | Errors say what happened and what to do next. Invite, approve, reject, and handover stay disabled until the staff member checks a confirmation box. | Invite owner dialog. Submit an empty place. |
| Shneiderman: closure | Finishing a handover returned to the same list. | The Done screen names the item, the person, and the date, and says the report is closed. | After Hand over. |
| Shneiderman: shortcuts for expert users | Staff crossed seven menus for daily work, and a large shortcut card took room on To do. | The four To do cards are buttons. Waiting, Matches, In the office and Done this week each open the matching list with a filter chip (with a Clear button) and a heading that names it. Lists are ordered so the most urgent item is first, so no “next” button is needed. Keyboard shortcuts were removed so every action stays on a visible button. | Staff Dashboard, Claims, and Help. |
| Hick’s law | Overview, inventory, found queue, matching, claims, staff, and audit were separate choices. | Those jobs are grouped into four. Claim filters are Needs you, Matches, Lost reports, and Finished. | Staff sidebar. |
| Miller’s law | Report and receive forms were one long dialog. Tables could grow without a stop. | Forms are three steps: What, Where, Details. Lists show six rows at a time. | Report a lost item. Items, when the list is long. |
| Fitts’s law | Some demo roles and row actions were small text links. | Main buttons are at least 48px tall. The four To do cards are large buttons (a whole card is the target) with a visible focus ring and a small arrow on hover. | Welcome page and any phone width. |
| Recognition over recall | A claim could read as a number. | Cards show the category icon, the item words, the person, and the place. Staff also see the photo. | Claims → Matches. |
| Gestalt and hierarchy | Decorative lines, captions, and repeated summaries competed with the task. | One heading and one main action per screen. Related fields sit together. Same action types share one style. | Student home and staff Today. |
| WCAG contrast and plain language | Muted gray body text was hard to read. Codes leaked into labels. | Body text is near-black on white or `#fafafa`, at least 4.5:1. Status uses an icon plus words such as “Still looking,” never a code. | Any screen. Browser zoom and a 390px-wide window. |
| Consistency and standards (Nielsen) | A dark side bar and dark tabs looked heavy and different from the pages next to them. Boxes used yellow, pink, and green fills, so color did not mean anything. | White side bar, top bar, and drawer with a thin gray line. The active item is maroon text, a maroon left bar, and a light gray fill. Tabs are a gray track with a white active tab. Every box is the same white card: 1px gray border, 12px corners, 24px padding. Color is kept for the main button, small status badges, and the current tracker step. | Side bar and tabs on any signed-in page. Compare two cards. |
| Visibility of system status | Home was nearly empty, so people could not tell where their report stood. | Home shows a greeting, two big actions, counts for Your reports and Your claims with badges, a four-step “How it works” strip, and a CSA office card with hours. Staff Today shows Waiting, Matches, In the office, and Done this week, then a task list with Next. | Student Home and staff Today. |
| Recognition over recall (browse) | A person had to remember what was already found. | “Recently found on campus” lists up to six items with category, place, date, and status. The server sends nothing else to non-staff, so descriptions, photos, and private details stay hidden. | Student, Professor, and Guest Home. |
| Help and empty states | Empty lists were blank. | Empty states have an icon, one sentence, and a button for the next step. The welcome page adds a stats strip, who it is for, a five-question FAQ, contact and hours, and a footer. | My reports with no reports. Welcome page. |
| Keyboard access | Focus was present, and it still is. | Visible burgundy focus, a skip link, labels on every field, and dialogs that can be closed from the keyboard. | Tab from the top of the welcome page. |
| Error prevention and clear errors | A bad sign-up only said "Something went wrong." | Sign up shows a live checklist (10+ characters, not your name or email, a letter, a number or symbol), a strength bar, Show/Hide and a match check. Each problem appears under its own field in plain words, and the server enforces the same rules. | Sign up with a short password, a taken email, a school email, or a different confirm. |
| Help and documentation | People did not know how their role signs in. | One compact guide (Student, Professor, Guest, CSA staff tabs with numbered steps and "After you sign in") on the welcome page, the sign-in page and Help. Demo accounts only appear in Help. | Sign-in page, welcome page, Help in the nav. |
| Visibility of status for staff | Staff rows showed many buttons. | Every staff screen has one H1, one sentence, and the five-step bar Report > Match > Verify > Hand over > Done on each row. A row has one main button (Approve, Start check or Hand over); Reject and View item sit under "...". Each confirmation says what happens next. | To do, Matches, Claims, Found items. |
| Trust in AI | Scores looked like facts. | "Strong match 87%", an AI-assisted badge, a Why this match? list and an AI is on / off card. The fallback says it is not an AI score. | Matches screen. |
| Type scale | Headings were close in size. | H1 28-32px bold, H2 20px semibold, H3 17px, body 15-16px, muted 13-14px. One H1 per page, headings in order. The welcome hero keeps a larger marketing size. | Any page, DevTools. |

## What stayed in the backend on purpose

The claim state machine, SQL guards, and tests still use codes such as `step1_pending`. People never see those codes. `lyfind/language.py` turns them into sentences, and the dashboard adds `status_label` and `stage` for the screen. Permission errors now say “Your account cannot hand an item over” instead of naming an internal action.

## Roles to demo

- Student Maria Santos: home tracker, three-step lost report, found report.
- Guest Alex Rivera: lost report only. Found items are taken to the office, not filed online.
- Professor Daniel Cruz: can report a found item.
- CSA staff: clickable To do cards, match cards, Admin staff list and activity log.

## Checks already run

`python3 -m unittest discover -s tests` passes (90 tests; the 2 CLIP tests run with `.venv/bin/python`). Browser checks covered the welcome, sign-in, sign-up, Help, student, professor, guest and staff screens, the whole claim lifecycle, photo upload errors, and 1280px and 390px layouts with no horizontal scrolling.

## Sign-in by school email and anti-prank controls

| Principle | Problem | Change |
| --- | --- | --- |
| Recognition over recall | A brand-new account should not invent a login. | **Open an LPU account**: the school email is checked once with a 6-digit code, then the person chooses a password and uses that on later visits. |
| Error prevention | Pranks and fake reports wasted staff time. | Guest reports and claims are flagged and checked first; staff can hide and block with a reason; found items show only category and date. |
| Visibility of system status | A refused address looked like a bug. | One neutral message names the next step: contact the CSA office. |
| Match user language | A score alone did not say why. | Strong and Possible tiers, and **Why this match?** with each signal and its points. |
| Honesty | People may hope an item is handed over without checks. | The ID rule is stated in plain English on the claim and handover screens. |

## One icon set

| Principle | Problem | Change |
| --- | --- | --- |
| Consistency and standards | Icons mixed drawings, sizes and meanings (the same magnifier meant Lost reports and Matches; a grid meant both To do and Home), and a few had no size rule. | One inline SVG helper in `app.js`: 24px grid, 2px round line, `currentColor`. Each place has one size: 16px in badges, 20px in the menu and buttons, 24px in cards, 32px in empty states. Each menu item has its own meaningful icon (Home, To do, Matches, Lost reports, Found items, Claims, Admin, Updates, Help, Sign out). |
| Recognition over recall | Text glyphs ("!", the word Show) stood in for icons. | Alert and eye icons replace them. |
| Accessibility | Icon-only buttons lacked tooltips or were small. | Menu, Sign out, More, Close and the password eye have an `aria-label`, a tooltip and a 44px hit area. Decorative icons are `aria-hidden`. The selected menu icon is burgundy; the others are dark gray (contrast above 5:1). |


## Urgent first
Waiting claims are ordered: ready to hand over, then ready to approve, then office checks, then new online checks. The oldest claim comes first inside each group. Matches show the strongest score first. In the office lists items with an open claim first, then the oldest.
