# Publishing LyFind Online (with Google AI Studio)

LyFind can run on a free or low-cost online host using **Google AI Studio (Gemini)** so you do not need a heavy server for PyTorch/CLIP/DINOv2.

## Before you publish: Get a free Gemini API key
1. Open [Google AI Studio](https://aistudio.google.com/apikey) and sign in with a Google account.
2. Click **Create API key** and copy it.
3. Keep it private—never paste it into GitHub or public files.

---

## Option 1: PythonAnywhere (Free \$0 plan — keeps SQLite & photos saved)

1. Push your `CSA_LostFound` project to GitHub (make sure `.env` and `data/` are ignored by `.gitignore`).
2. Create a free account at [pythonanywhere.com](https://www.pythonanywhere.com/).
3. Open a **Bash** console on PythonAnywhere and clone your repo:
   ```bash
   git clone <your-github-repo-url> lyfind
   cd lyfind
   python3.11 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements-web.txt
   ```
4. Create your private `.env` file inside `/home/<your-username>/lyfind/.env`:
   ```env
   AI_PROVIDER=gemini
   GEMINI_API_KEY=paste-your-key-here
   GEMINI_MODEL=gemini-4-hydrogen
   ALLOWED_HOSTS=<your-username>.pythonanywhere.com
   TRUST_PROXY=1
   COOKIE_SECURE=1
   LYFIND_DEMO=0
   ```
   *(For a class demo with sample accounts enabled, set `LYFIND_DEMO=1`; for live school use, keep `LYFIND_DEMO=0` and run `python main.py --create-admin` once.)*
5. Go to the **Web** tab → **Add a new web app** → choose **Manual configuration** → **Python 3.11**.
6. Set **Virtualenv** to `/home/<your-username>/lyfind/.venv`.
7. Open the **WSGI configuration file** link and replace its contents with:
   ```python
   import sys
   path = "/home/<your-username>/lyfind"
   if path not in sys.path:
       sys.path.insert(0, path)

   from wsgi import application
   ```
8. Click the green **Reload** button and visit `https://<your-username>.pythonanywhere.com`.

### Updating your live site later
Push your changes from your laptop to GitHub, then in PythonAnywhere Bash run:
```bash
cd ~/lyfind && git pull
```
and click **Reload** on the Web tab. Your database and uploaded photos stay untouched.

---

## Option 2: Render / Railway (Auto-updates on every GitHub push)

- **Build command:** `pip install -r requirements-web.txt`
- **Start command:** `gunicorn wsgi:application --workers 1 --threads 4 --bind 0.0.0.0:$PORT`
- **Environment variables:**
  - `AI_PROVIDER=gemini`
  - `GEMINI_API_KEY=<your-key>`
  - `TRUST_PROXY=1`
  - `COOKIE_SECURE=1`
  - `ALLOWED_HOSTS=<your-app>.onrender.com` *(Render also sets `RENDER_EXTERNAL_HOSTNAME` automatically)*
- **Storage note:** On Render's free plan, local files reset on restart—attach a Persistent Disk mounted at `/var/data` and set `LYFIND_DB_PATH=/var/data/csa.sqlite3` and `LYFIND_UPLOAD_DIR=/var/data/uploads` if you need permanent live storage.
