# LPU Cavite inspired theme

The October 29, 2026 interface update follows the supplied university website reference: deep red masthead and primary actions, gold accents, white surfaces, and light gray navigation and page backgrounds. The masthead uses the exact university crest supplied by the project owner, preserving its proportions and transparency. The original image is included as `static/lpu-logo.png` and embedded in the interface for compatibility with existing local servers.

The sign-in screen has a university masthead, a formal serif headline, clearer segmented account tabs, and a white sign-in card. The administrator and user workspaces share the same palette, with improved cards, navigation states, typography, and spacing. Semantic status colors still distinguish pending, rejected, and completed records.

## Apply to an existing installation

The working project in this workspace has already been updated. Refresh the browser with **Ctrl+F5**.

If running a separately extracted copy, extract the updated archive into a separate folder and copy its **static** folder into the existing application's folder, replacing the previous static files. Refresh with **Ctrl+F5**. Keep the existing **data** folder to retain database records and uploads. No database migration or reset is required.

## Verification

JavaScript syntax validation passed. The updated login and administrator dashboard were inspected in the running local application. A narrow desktop panel issue found during review was corrected and checked again. Login and dashboard previews are saved as `lpu-login.jpg` and `lpu-dashboard.jpg`.

This update changes presentation. Microsoft sign-in and email configuration requirements remain as documented in the setup guide. The existing functional test results describe the underlying application; no new backend behavior was introduced by this theme update.
