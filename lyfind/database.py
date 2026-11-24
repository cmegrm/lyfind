"""SQLite storage: WAL mode, a busy timeout, idempotent migrations and integrity checks."""
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from lyfind.migrations import SchemaMigrator

SCHEMA_VERSION = 13
SCHEMA = Path(__file__).with_name("schema.sql")


class Connection(sqlite3.Connection):
    """The application context owns and closes its connection on every platform."""
    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


class Database:
    def __init__(self, path):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)

    def connect(self):
        conn = sqlite3.connect(self.path, timeout=15, factory=Connection)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 15000")
        conn.execute("PRAGMA foreign_keys = ON")
        if self.path != ":memory:":
            # WAL lets readers and one writer work together, so requests do not queue behind each other.
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
        return conn

    def initialize(self):
        """Create or upgrade in one transaction; never clear existing records."""
        with self.connect() as conn:
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            if version > SCHEMA_VERSION:
                raise ValueError("This database needs a newer version of LyFind.")
            legacy_answers = "answers" in SchemaMigrator(conn).columns("claims")
            legacy_name = any(row["name"] == "name" and row["hidden"] == 0
                              for row in conn.execute("PRAGMA table_xinfo(users)"))
        if legacy_answers or legacy_name:
            if sqlite3.sqlite_version_info < (3, 35, 0):
                raise RuntimeError("Upgrading LyFind requires SQLite 3.35 or newer.")
            # Uploads are not altered by this migration. Preserve the old DB first.
            self.backup(None, Path(self.path).parent / "backups" / "schema_migrations")
        with self.connect() as conn:
            conn.executescript("BEGIN IMMEDIATE;\n" + SCHEMA.read_text(encoding="utf-8"))
            SchemaMigrator(conn).upgrade()
            conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            conn.commit()

    def check(self):
        """Run SQLite's own integrity and foreign-key checks. Returns {'ok': bool, 'problems': [...]}."""
        problems = []
        with self.connect() as conn:
            for row in conn.execute("PRAGMA integrity_check"):
                if row[0] != "ok":
                    problems.append("integrity: " + str(row[0]))
            for row in conn.execute("PRAGMA foreign_key_check"):
                problems.append(f"foreign key: {row[0]} row {row[1]} points to a missing {row[2]}")
            version = conn.execute("PRAGMA user_version").fetchone()[0]
        return {"ok": not problems, "problems": problems, "schema_version": version}

    def backup(self, upload_dir, backups_dir, stamp=None):
        """Copy a consistent snapshot of the database and the upload folder into backups_dir/<timestamp>/."""
        stamp = stamp or datetime.now().strftime("%Y%m%d-%H%M%S")
        target = Path(backups_dir) / stamp
        n = 1
        while target.exists():  # never overwrite an earlier backup
            n += 1
            target = Path(backups_dir) / f"{stamp}-{n}"
        target.mkdir(parents=True)
        source = sqlite3.connect(self.path, timeout=15)
        try:
            destination = sqlite3.connect(str(target / Path(self.path).name))
            try:
                source.backup(destination)  # safe while the server is running
            finally:
                destination.close()
        finally:
            source.close()
        if upload_dir and Path(upload_dir).is_dir():
            shutil.copytree(upload_dir, target / "uploads")
        return target
