"""Upgrade older SQLite files without resetting user records."""
import json

from lyfind.claim_answers import ClaimAnswers
from lyfind.users import split_display_name

# (table, column, definition). Fresh databases get these from schema.sql; older ones get them here.
NEW_COLUMNS = (
    ("items", "board_published", "INTEGER NOT NULL DEFAULT 0 CHECK(board_published IN (0,1))"),
    ("matches", "score_details", "TEXT NOT NULL DEFAULT '{}'"),
    ("users", "email_verified", "INTEGER NOT NULL DEFAULT 1"),
    ("users", "student_number", "TEXT NOT NULL DEFAULT ''"),
    ("users", "phone", "TEXT NOT NULL DEFAULT ''"),
    ("users", "first_name", "TEXT NOT NULL DEFAULT ''"),
    ("users", "middle_name", "TEXT NOT NULL DEFAULT ''"),
    ("users", "last_name", "TEXT NOT NULL DEFAULT ''"),
    ("users", "suffix", "TEXT NOT NULL DEFAULT ''"),
    ("lost_reports", "flagged", "INTEGER NOT NULL DEFAULT 0"),
    ("lost_reports", "hidden", "INTEGER NOT NULL DEFAULT 0"),
    ("found_reports", "hidden", "INTEGER NOT NULL DEFAULT 0"),
    ("claims", "flagged", "INTEGER NOT NULL DEFAULT 0"),
    ("lost_reports", "time_lost", "TEXT NOT NULL DEFAULT ''"),
    ("desk_holds", "time_lost", "TEXT NOT NULL DEFAULT ''"),
    ("found_reports", "color", "TEXT NOT NULL DEFAULT ''"),
    ("found_reports", "brand", "TEXT NOT NULL DEFAULT ''"),
    ("found_reports", "time_found", "TEXT NOT NULL DEFAULT ''"),
    ("found_reports", "where_now", "TEXT NOT NULL DEFAULT 'with_me'"),
    ("found_reports", "photo_id", "INTEGER REFERENCES uploads(id)"),
)

# Safe to rerun. Speeds up matching, sessions, and the staff inbox.
NEW_INDEXES = (
    "CREATE INDEX IF NOT EXISTS lost_reports_open ON lost_reports(status, hidden)",
    "CREATE INDEX IF NOT EXISTS items_status ON items(status)",
    "CREATE INDEX IF NOT EXISTS matches_status ON matches(status, level)",
    "CREATE INDEX IF NOT EXISTS notifications_user ON notifications(user_id, created_at)",
    "CREATE INDEX IF NOT EXISTS sessions_expiry ON sessions(expires)",
    "CREATE INDEX IF NOT EXISTS audit_when ON audit_logs(created_at)",
    "CREATE INDEX IF NOT EXISTS ai_match_cache_created ON ai_match_cache(created_at)",
)


class SchemaMigrator:
    """Apply upgrades inside the transaction owned by Database.initialize()."""

    def __init__(self, connection):
        self.connection = connection

    def columns(self, table):
        return {row["name"] for row in self.connection.execute(f"PRAGMA table_info({table})")}

    def upgrade(self):
        self.add_missing_columns()
        self.upgrade_email_codes()
        self.normalize_display_name()
        self.normalize_claim_answers()
        if 'board_type' in self.columns('items'):
            # Preserve the existing CSA-curated listings on their first upgrade.
            version = self.connection.execute('PRAGMA user_version').fetchone()[0]
            if version < 11:
                self.connection.execute("UPDATE items SET board_published=1 WHERE board_type<>''")
        for statement in NEW_INDEXES:
            self.connection.execute(statement)

    def upgrade_email_codes(self):
        row = self.connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='email_codes'"
        ).fetchone()
        if not row or not row["sql"] or "'reset'" in row["sql"]:
            return
        self.connection.execute("""CREATE TABLE email_codes_v13 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL COLLATE NOCASE,
            purpose TEXT NOT NULL CHECK(purpose IN ('school','signup','reset')),
            salt TEXT NOT NULL,
            code_hash TEXT NOT NULL,
            expires REAL NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            used INTEGER NOT NULL DEFAULT 0,
            requested REAL NOT NULL
        )""")
        self.connection.execute("""INSERT INTO email_codes_v13(id,email,purpose,salt,code_hash,expires,attempts,used,requested)
            SELECT id,email,purpose,salt,code_hash,expires,attempts,used,requested FROM email_codes""")
        self.connection.execute("DROP TABLE email_codes")
        self.connection.execute("ALTER TABLE email_codes_v13 RENAME TO email_codes")
        self.connection.execute("CREATE INDEX IF NOT EXISTS email_codes_lookup ON email_codes(email, purpose, id)")

    def add_missing_columns(self):
        for table, column, definition in NEW_COLUMNS:
            if column not in self.columns(table):
                self.connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def normalize_display_name(self):
        columns = self.connection.execute("PRAGMA table_xinfo(users)").fetchall()
        name_column = next(row for row in columns if row["name"] == "name")
        if name_column["hidden"] != 0:  # already a generated column
            return
        self.connection.execute("DROP TRIGGER IF EXISTS users_sync_display_name_insert")
        self.connection.execute("DROP TRIGGER IF EXISTS users_sync_display_name")
        for row in self.connection.execute("SELECT id, name, first_name, last_name FROM users"):
            if row["name"] and not (row["first_name"] or "").strip() and not (row["last_name"] or "").strip():
                first, middle, last, suffix = split_display_name(row["name"])
                self.connection.execute(
                    "UPDATE users SET first_name=?, middle_name=?, last_name=?, suffix=? WHERE id=?",
                    (first, middle, last, suffix, row["id"]),
                )
        self.connection.execute("ALTER TABLE users DROP COLUMN name")
        self.connection.execute("""ALTER TABLE users ADD COLUMN name TEXT
            GENERATED ALWAYS AS (trim(
    trim(first_name) || ' ' ||
    CASE WHEN trim(middle_name) != '' THEN trim(middle_name) || ' ' ELSE '' END ||
    trim(last_name) ||
    CASE WHEN trim(suffix) != '' THEN ' ' || trim(suffix) ELSE '' END
 )) VIRTUAL""")

    def normalize_claim_answers(self):
        if "answers" not in self.columns("claims"):
            return
        repository = ClaimAnswers(self.connection)
        for row in self.connection.execute("SELECT id, answers FROM claims"):
            try:
                answers = json.loads(row["answers"])
            except (ValueError, TypeError) as error:
                raise ValueError(f"Cannot migrate answers for claim {row['id']}: invalid JSON") from error
            if not isinstance(answers, dict):
                raise ValueError(f"Cannot migrate answers for claim {row['id']}: expected an object")
            for question, answer in answers.items():
                if (not isinstance(question, str) or not question.strip()
                        or not isinstance(answer, str) or not answer.strip() or len(answer) > 3000):
                    raise ValueError(f"Cannot migrate answers for claim {row['id']}: invalid answer")
            repository.save(row["id"], answers)
        # Remove the old copy only after every answer has been copied successfully.
        self.connection.execute("ALTER TABLE claims DROP COLUMN answers")
