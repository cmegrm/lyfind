"""SQLite connections with foreign keys and predictable transaction ownership."""
import sqlite3
from pathlib import Path


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
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 15000")
        return conn

    def initialize(self):
        with self.connect() as conn:
            conn.executescript(Path(__file__).with_name("schema.sql").read_text(encoding="utf-8"))
            item_columns = {row["name"] for row in conn.execute("PRAGMA table_info(items)")}
            if "board_type" not in item_columns:
                conn.execute("ALTER TABLE items ADD COLUMN board_type TEXT NOT NULL DEFAULT ''")
            if "board_campus_only" not in item_columns:
                conn.execute("ALTER TABLE items ADD COLUMN board_campus_only INTEGER NOT NULL DEFAULT 0 CHECK(board_campus_only IN (0,1))")
            match_columns = {row["name"] for row in conn.execute("PRAGMA table_info(matches)")}
            if "score_details" not in match_columns:
                conn.execute("ALTER TABLE matches ADD COLUMN score_details TEXT NOT NULL DEFAULT '{}'")
            if "withdrawal_reason" not in match_columns:
                conn.execute("ALTER TABLE matches ADD COLUMN withdrawal_reason TEXT NOT NULL DEFAULT ''")
            claim_columns = {row["name"] for row in conn.execute("PRAGMA table_info(claims)")}
            if "consent_declined_at" not in claim_columns:
                conn.execute("ALTER TABLE claims ADD COLUMN consent_declined_at TEXT")
            if "reservation_ended" not in claim_columns:
                conn.execute("ALTER TABLE claims ADD COLUMN reservation_ended INTEGER NOT NULL DEFAULT 0")
