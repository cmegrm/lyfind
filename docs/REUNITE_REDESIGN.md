# Reunite: current interface

Reunite is the independent product identity for the CSA Automated Lost and Found System. The interface uses a burgundy, ivory and muted gold palette, with its own loop-and-return logo and a compact header. It does not display the LPU crest or university masthead. The original academic workflow and university sign-in configuration rules still apply.

## Students and guests first

- The welcome page puts **I lost something** and **Track a claim** first. After a successful local sign-in, the selected path opens the report form or My claims directly.
- Clearly labeled Student and Guest sample cards offer one-click class exploration. Professor and CSA admin sample accounts remain available as smaller links. These are fictional identities, not externally verified accounts.
- Guest email sign-in explains the one-time code and displays it locally in demonstration mode. The Student / faculty tab retains the optional Microsoft integration. Office sign in has its own shortcut.
- The personal overview shows a primary reporting action, claim tracking, actual next-step guidance, concise totals, report cards and recent updates. Guests receive direct CSA handoff guidance for found items; they do not gain found-report permissions.
- The lost-report form groups essentials and identifying details, with examples and clear optional fields. Existing validation and privacy rules remain.
- How it works is available from the header. It explains reporting, invitations, both ownership checks, consent and physical handover.

## Office workflow

Inventory, found queue, private matching, claims, staff accounts and audit history keep their established operations. The new shared styling applies to forms, tables, status badges and verification timelines. No database migration or backend business-rule change is needed for this redesign.

## Files

- `static/app.js`: rendering, original inline logo, reporting/tracking intent through sign-in, help and personal dashboard.
- `static/style.css`: new design system, responsive layout, form styles and restrained motion.
- `static/index.html`: Reunite page title, favicon and versioned assets.
- `static/reunite-logo.svg`: editable original vector logo.
- `docs/ILLUSTRATED_WEBSITE_CODE_GUIDE.*`: refreshed screenshots, current screen descriptions and source references.

Older theme and visual-update documents describe earlier iterations. This document describes the current interface.

## Verified

JavaScript syntax check passed. All 53 existing Python tests passed in 11.664 seconds after the redesign. Browser checks covered Student sign-in, public report intent, saving a fictional lost report, report cards, Guest demo claim intent, guest email-code request/verification, role-appropriate navigation, help dialog, found report form, office inventory/intake/matching/claims/consent/staff/audit screens, and phone navigation.

Phone checks used a 390-pixel viewport. Both personal overview and welcome page had no horizontal overflow. Dialogs and navigation retain keyboard support. Motion respects reduced-motion preferences. The isolated preview used temporary fictional records; the working `data` folder was not reset or edited by those browser checks.

Live Microsoft sign-in, SMTP delivery and a downloaded CLIP model remain external setup items, as agreed for the local class demonstration. Backend tests use controlled test doubles where appropriate and do not establish live external connectivity.

## Open the update

The updated complete package is `CSA_LostFound_Class_Demo.zip`. Stop the old server, keep your existing `data` folder safe, and replace the project files with the update. When extracting into a separate folder, copy `data` across if you want the same saved records. Preserve an existing `.env` if you have configured one. Restart and hard-refresh the browser (Windows: Ctrl+F5; Mac: Command+Shift+R).

Windows: `START_CSA.bat`. macOS: Terminal in the project folder, then `python3 main.py`. Open `http://127.0.0.1:8765`. Python 3.10 or newer is required.
