"""Backup, integrity check and demo reset. Nothing here deletes data without a backup first."""
import json
import urllib.request
from pathlib import Path

from lyfind.database import Database


def server_answering(host, port):
    """True when a LyFind server already answers on this address (the database should not be reset then)."""
    try:
        with urllib.request.urlopen(f"http://{host}:{port}/api/health", timeout=1.5) as response:
            return json.load(response).get("data", {}).get("application") == "lyfind"
    except Exception:
        return False


def backup(db_path, upload_dir, backups_dir):
    db = Database(db_path)
    if not Path(db_path).exists():
        raise FileNotFoundError("There is no database at " + str(db_path) + " to back up.")
    return db.backup(upload_dir, backups_dir)


def reset_demo(db_path, upload_dir, backups_dir):
    """Back up, remove the demo database and the uploads it owns, then seed fresh sample records."""
    from lyfind.seed import ensure_demo_passwords, ensure_demo_roster, seed_demo
    db_path, upload_dir = Path(db_path), Path(upload_dir)
    made = None
    owned = []
    if db_path.exists():
        existing = Database(db_path)
        existing.initialize()
        made = existing.backup(upload_dir, backups_dir)
        with existing.connect() as conn:
            owned = [row["path"] for row in conn.execute("SELECT path FROM uploads")]
        for suffix in ("", "-wal", "-shm"):
            Path(str(db_path) + suffix).unlink(missing_ok=True)
        for name in owned:  # only the files this database recorded, never the whole folder
            (upload_dir / Path(name).name).unlink(missing_ok=True)
    fresh = Database(db_path)
    fresh.initialize()
    seed_demo(fresh, upload_dir)
    ensure_demo_passwords(fresh)
    ensure_demo_roster(fresh)
    return made
