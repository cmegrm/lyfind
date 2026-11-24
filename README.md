# LyFind

LyFind includes the 2.0 public homepage, guided forms, account profiles, separate name fields, optional phone numbers, and student numbers derived from supported school-email formats. The modular backend lives in `lyfind/`, with individual workflows for reports, inventory, matches, claims, accounts, and dashboard views.

## Open LyFind

Extract the whole ZIP. On Windows, double-click **START_CSA.bat**. On Mac, open **Reunite.app** from **Reunite_Mac.zip**. The Mac package includes Python. The launcher opens the live workspace, reopens its running server, and saves your records in `data/csa.sqlite3`.

On a first installation, choose **Login → Set up the first CSA administrator** from the desktop launcher's page. Existing administrators use the email-and-password form. Students and professors use `@lpunetwork.edu.ph` emails. CSA can manage eligible school addresses under **Administration → Records → Allowed emails**, including a CSV preview before import.

## Guest access

Choose **Guest · send an email code** from Login, or **Sign up → Guest**. Enter a personal email and verify its six-digit code. A guest password is unnecessary. After entering the full code, you can choose **Remember this browser** for 30 days. Your reports stay linked to the verified email. Guests can submit lost reports and follow claims. Found items should be brought directly to CSA.

## Staff and student tools

- Students and professors can open **Found items** to browse CSA-published category and found-week summaries. Photos, exact locations, and identifying details remain private. CSA chooses whether each received item is listed.
- Signed-in users can open **Contact CSA**. Administrators open the shared **CSA inbox** and reply to the same conversations.
- **Administration → Maintenance** creates a backup of records and registered images. In the isolated testing workspace, **Reset demo** saves a backup first, restores samples, and ends demo sessions.
- Matching uses the five proposal weights. Description 30%, photo 30%, color 15%, brand 15%, and place/date 10%. Strong starts at 60 with additional agreement checks, Possible at 40. Typed-only scoring is capped below Strong. Similar candidates receive a staff warning.

## Testing and local AI

Lost and found reports now save unfinished text as an account-specific draft on this browser for seven days. The Dashboard offers Resume draft; the report also offers Discard draft. Photos are not saved as local draft image data: choose them again after reopening unless they were already uploaded during an interrupted save. Guest found reports remain disabled. CSA desk reports for visitors have a review step but do not store visitor details as browser drafts.

Choose Review report, check the summary, use Edit details if needed, then confirm submission. If a reply is lost, Try again safely returns the original lost/found report using a saved submission key. A changed payload using an already-saved key is refused so an interrupted save cannot silently become a different report. If saving succeeds but the dashboard cannot reload, use Refresh dashboard; do not resubmit. Your next step highlights invitations, office visits, found-item handoff, or waiting for CSA.

The testing Help page includes a classmate exercise. The observer worksheet is `docs/CLASSMATE_USABILITY_TEST.md`. Actual classmate testing still needs the group; automated checks are not claimed as human feedback.

Three quiet controls stay in the lower-right corner: the sun/moon switches light and dark mode, the person icon opens Accessibility, and the three dots open testing when using the local desktop launcher. Accessibility offers normal or larger text, higher contrast, and reduced motion. Motion follows the device by default. Preferences are remembered on this browser; forms and CSA conversations include the same controls without losing drafts. Keyboard focus, inline field guidance, and save/error announcements work automatically. Reset accessibility settings restores reading preferences and leaves the chosen light/dark theme in place.

Testing opens in a separate tab with one-click access to two students, one professor, one guest, and one CSA staff sample. The same three-dot button switches between samples without typing passwords. The testing workspace uses `data/demo.sqlite3` and `data/test-uploads`; sample access remains disabled in live mode. The public Help page keeps its testing shortcut and account list. Sample passwords are `DemoOnly!2026` if manual sign-in is preferred.

Run **SETUP_AI.bat** on Windows or **Reunite Controls → Set up local AI** on Mac to prepare local CLIP and DINOv2. The existing local model folders are reused. Until AI is ready, the interface identifies typed-detail matching.

### Google AI Studio (Gemini) and Publishing Online

LyFind also supports **Google AI Studio (Gemini)** for multimodal text, owner-only mark, and photo matching—ideal when publishing the site online or avoiding heavy local PyTorch installs:

1. Install lightweight web dependencies: `pip install -r requirements-web.txt`
2. Add your private API key to `.env` (see `.env.example`):
   - `AI_PROVIDER=gemini` (or `auto`, which uses Gemini whenever `GEMINI_API_KEY` is set and falls back to local AI or typed details)
   - `GEMINI_API_KEY=<your-key>`
   - `GEMINI_MODEL=gemini-4-hydrogen`
3. Match results are cached in the `ai_match_cache` SQLite table so unchanged report/item pairs do not repeat API calls, and AI runs outside database write locks.
4. For free or paid online hosting (**PythonAnywhere**, **Render**, or **Railway**), use `wsgi.py` and follow [docs/PUBLISH_ONLINE.md](docs/PUBLISH_ONLINE.md).

### Codebase Layout (`lyfind/` vs. root `.py` files)

- **Live v2 application:** `main.py`, `wsgi.py`, `static/`, and the modular `lyfind/` package (`lyfind/web.py`, `lyfind/workflows/`, `lyfind/gemini_matching.py`, `lyfind/ai_runtime.py`, `lyfind/auth.py`, `lyfind/database.py`, `lyfind/schema.sql`).
- **Root compatibility modules:** Top-level files like `matching.py`, `web.py`, `services.py`, and `schema.sql` remain in the root folder for backward compatibility with older scripts and proposal checks (`matching.py` still holds the shared five-clue base scoring engine used by `lyfind/proposal_matching.py`).

## Email and saved records

The sender is loaded from the private Windows profile settings or the project's private `.env`. Email settings and real data are excluded from the shared ZIP. Real email requires a configured sender. The local testing workspace shows a demonstration code when no sender is configured.

Starting this version upgrades older databases in place and saves a database snapshot under `data/backups/schema_migrations` before normalizing names and ownership answers. IDs, reports, claims, uploaded-image references, audit history, and CSA conversations are preserved.

For a demonstration of the complete claim and physical-handover workflow, run `python scripts/demo.py`. For the integration regression checks, run `python -m unittest discover -s tests -p test_current_integration.py`.
