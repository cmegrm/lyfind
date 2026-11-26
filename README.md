# LyFind — Campus Lost & Found (LPU Cavite CSA)

A clean, modern web app for reporting, matching, and returning lost items at **LPU Cavite (Center for Student Affairs)**.  
For visual slides of every screen and the AI flow, open **[LyFind_Website_Showcase.pdf](LyFind_Website_Showcase.pdf)**.

---

## Key Features

- **Clean Editorial Design + Pure Black Dark Mode:** Light Mode (`#FFFFFF`) and matching Pure Black Dark Mode (`#0B0B0C`), responsive across desktop and mobile, with blended logos and quick theme/accessibility controls in the bottom-right corner.
- **Google Gemini AI Matching & Photo Auto-Fill:** Compares photos, descriptions, and private clues using Google Gemini (`store=False` so Google does not save student photos or clues), with automatic offline backup matching if there is no internet.
  - **Fill details with AI:** Upload a photo first to auto-fill Kind, Color, Brand, and Description.
  - **Match Score Weights:** Description `30%`, Photo `30%`, Color `15%`, Brand `15%`, Place & Date `10%` (`60%+` Strong, `40%–59%` Possible; CSA staff always make the final call).
- **Digital Claim Pass & Handover Receipt:** Printable `LYF-CLM-...` pass with owner details, ID reminder, and CSA office hours.
- **CSA Staff Desk & Campus Hotspots:** Unified *Needs attention* queue, top 5 campus hotspot buildings with recovery rate, shared **Contact CSA / CSA inbox**, and a **Start Fresh (0 reports)** button in Demo Administration.
- **Demo & Live Modes:** Sample accounts (`•••` quick switcher) run in an isolated demo database (`data/demo.sqlite3`) without touching real records.

---

## Quick Start (Run Locally)

1. Install **Python 3.10+**, open a terminal in this folder, and install dependencies:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements-web.txt
   ```
2. *(Optional for Gemini AI)* Copy `.env.example` to `.env` and add your `GEMINI_API_KEY` from [Google AI Studio](https://aistudio.google.com/apikey).
3. Start Demo mode:
   ```bash
   python main.py --demo
   ```
   *(Or double-click `START_CSA.bat` on Windows for live desktop launch.)*

---

## Publish Online 24/7 (Render Blueprint)

1. Push this repo to GitHub (`.env`, `.venv/`, `data/`, and `*.log` stay excluded via `.gitignore`).
2. In **Render → New Blueprint Instance**, select your GitHub repo (`render.yaml` configures Python, Gunicorn, Demo mode, and security headers automatically).
3. Paste your `GEMINI_API_KEY` in Render Environment Variables and deploy. Full details are in [docs/PUBLISH_ONLINE.md](docs/PUBLISH_ONLINE.md).

---

## Categorized Project Map

| Category | Key Files & Folders | What They Do |
| --- | --- | --- |
| **Frontend / Website UI** | `static/app.js`, `static/style.css`, `static/support.css`, `static/index.html`, `static/boot.js`, `static/assets/` | Renders all screens, Light/Dark themes, slideshows, report forms, support chat, and real campus photos. |
| **Backend & AI Engine** | `lyfind/web.py`, `lyfind/gemini_matching.py`, `lyfind/ai_runtime.py`, `lyfind/auth.py`, `lyfind/workflows/`, `lyfind/workspace_maintenance.py`, `lyfind/database.py` | Handles web routes, Gemini multimodal matching & photo auto-fill, sign-in/security, SQLite storage, and backups/resets. |
| **Launch & Hosting** | `main.py`, `wsgi.py`, `render.yaml`, `requirements-web.txt`, `START_CSA.bat`, `.env.example` | Starts the app locally (`--demo` or live) or online via Gunicorn/Render. |
| **Presentation & Docs** | `LyFind_Website_Showcase.pdf`, `docs/PUBLISH_ONLINE.md`, `docs/` | 7-page team showcase deck, hosting instructions, architecture notes, and user guides. |
| **Automated Tests & Tools** | `tests/`, `scripts/`, `Tools/` | 61+ automated unit/static/integration tests, demo runner scripts, and Windows helper shortcuts. |

> **Compatibility Note:** Top-level root Python/SQL files (`matching.py`, `web.py`, `services.py`, `schema.sql`, etc.) stay at the project root so older scripts and automated test imports continue working seamlessly alongside `lyfind/`.

---

## Verification

Run the frontend, Gemini/online, and integration suites:

```bash
python -m unittest discover -s tests -p "test_frontend_static.py"
python -m unittest discover -s tests -p "test_gemini_and_online.py"
python -m unittest discover -s tests -p "test_current_integration.py"
```
