"""Shared permission, transaction, and form checks for application services."""
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path

from lyfind.claim_answers import ClaimAnswers
from lyfind.ai_runtime import LocalAI
from lyfind.language import bad_date, future_date, invalid_text, known_category, missing, old_date, too_long
from lyfind.matching import brand_key
from lyfind.storage import resolve_upload
from lyfind.users import DomainError, User, require_permission

ACTIVE = ("step1_pending", "step2_pending", "verified", "approved")
# Per person, per rolling 24 hours. Staff have no cap. Guests start lower and everything they send is checked by staff.
DAILY_LIMITS = {"guest": {"lost": 3, "found": 3, "claim": 3}, "student": {"lost": 10, "found": 10, "claim": 5},
                "professor": {"lost": 10, "found": 10, "claim": 5}}
CAP_SQL = {"lost": ("lost_reports", "owner_id"), "found": ("found_reports", "finder_id"), "claim": ("claims", "claimant_id")}
TIMES = ("Morning", "Lunch time", "Afternoon", "Evening", "Not sure")
# Where a found item is right now. Only "with_me" needs a turn-in day.
FOUND_NOW = ("with_me", "security", "left")
CAP_WORDS = {"lost": "lost reports", "found": "found reports", "claim": "claims"}


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class AuditLog:
    """Append entries through a method; SQLite also rejects UPDATE and DELETE."""
    def __init__(self, conn):
        self._conn = conn

    def record(self, actor, action, detail):
        self._conn.execute("INSERT INTO audit_logs(actor_id,action,detail) VALUES(?,?,?)",
                           (actor.id if actor else None, action, str(detail)))


class WorkflowContext:
    """Objects shared by all workflows in one running application."""

    def __init__(self, db, upload_dir=None, matcher=None):
        self.db = db
        self.upload_dir = Path(upload_dir) if upload_dir else None
        self.matcher = matcher
        self.ai = LocalAI()
        self.matching = None


class WorkflowBase:
    """Inherit common checks instead of copying them into every service."""

    def __init__(self, context):
        self.context = context
        self.db = context.db
        self.upload_dir = context.upload_dir
        self.ai = context.ai

    @property
    def matcher(self):
        return self.context.matcher

    @matcher.setter
    def matcher(self, value):
        self.context.matcher = value

    def _run_matching(self, conn, actor=None):
        # Reuse the caller's transaction when a caller explicitly owns the connection.
        return self.context.matching._run_matching(conn, actor)

    def _run_matching_unlocked(self, actor=None):
        # Run AI comparisons outside any SQLite write lock so concurrent users stay responsive.
        return self.context.matching.run_matching_unlocked(actor)

    @contextmanager
    def _tx(self):
        conn = self.db.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except sqlite3.IntegrityError as error:
            conn.rollback()
            raise DomainError("That step was already completed, or it conflicts with another saved record.") from error
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _guard(self, user, action):
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE id=?", (user.id if user else -1,)).fetchone()
        current = User.from_row(row) if row else None
        try:
            require_permission(current, action)
        except DomainError:
            if row:
                with self._tx() as conn:
                    AuditLog(conn).record(current, "DENIED_" + action.upper(), "Role or account state denied action")
            raise
        return current

    @staticmethod
    def _row(conn, table, id):
        if isinstance(id, bool) or not isinstance(id, (int, str)) or not str(id).isdigit() or int(id) < 1:
            raise DomainError("Choose a valid record.")
        try:
            id = int(id)
        except (ValueError, TypeError):
            raise DomainError("Choose a valid record.")
        row = conn.execute(f"SELECT * FROM {table} WHERE id=?", (id,)).fetchone()
        if not row:
            raise DomainError("That record is no longer available.", 404)
        result = dict(row)
        if table == "claims":
            result["answers"] = ClaimAnswers(conn).for_claim(result["id"])
        return result

    @staticmethod
    def _daily_cap(conn, user, kind):
        """Plain-language limit on how many reports or claims one person can send in 24 hours."""
        limit = DAILY_LIMITS.get(user.role, {}).get(kind)
        if limit is None:
            return
        table, column = CAP_SQL[kind]
        used = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {column}=? AND created_at >= strftime('%Y-%m-%dT%H:%M:%SZ','now','-1 day')", (user.id,)).fetchone()[0]
        if used >= limit:
            raise DomainError(f"You have reached today's limit of {limit} {CAP_WORDS[kind]}. Try again tomorrow, or visit the CSA office.", 429)

    @staticmethod
    def _text(data, field, required=True, maximum=2000):
        if data.get(field) is not None and not isinstance(data.get(field), (str, int, float)):
            raise DomainError(invalid_text(field))
        value = str(data.get(field, "") or "").strip()
        if required and not value:
            raise DomainError(missing(field))
        if len(value) > maximum:
            raise DomainError(too_long(field, maximum))
        return value

    def _date(self, data, field, future=False):
        value = self._text(data, field, maximum=10)
        try:
            parsed = date.fromisoformat(value)
        except ValueError:
            raise DomainError(bad_date(field))
        if not future and parsed > date.today():
            raise DomainError(future_date())
        if not future and parsed < self._oldest_report_day():
            raise DomainError(old_date())
        return value

    @staticmethod
    def _oldest_report_day(today=None):
        """The earliest lost or found day still accepted: the same calendar day, 3 months ago."""
        today = today or date.today()
        month = today.month - 3
        year = today.year
        if month < 1:
            month += 12
            year -= 1
        day = today.day
        while day > 28:
            try:
                return date(year, month, day)
            except ValueError:
                day -= 1
        return date(year, month, day)

    @staticmethod
    def _notify(conn, user_id, message, report_id=None, claim_id=None):
        conn.execute("INSERT INTO notifications(user_id,message,report_id,claim_id) VALUES(?,?,?,?)",
                     (user_id, message, report_id, claim_id))

    def _photo(self, conn, user, photo_id, kind, required=False, claim_id=None):
        if not photo_id:
            if required:
                raise DomainError("Add a photo before saving.")
            return None
        photo = self._row(conn, "uploads", photo_id)
        if photo["kind"] != kind or (photo["owner_id"] != user.id and user.role != "admin"):
            raise DomainError("The selected upload cannot be used here.", 403)
        if claim_id is not None and photo["claim_id"] != int(claim_id):
            raise DomainError("Evidence must be uploaded for this specific claim.")
        if not photo["mime"].startswith("image/"):
            raise DomainError("Use a PNG, JPEG, or WebP image.")
        if self.upload_dir is not None:
            resolve_upload(self.upload_dir, photo["path"], must_exist=True)
        return int(photo_id)

    @staticmethod
    def _category(value):
        category = known_category(value)
        if not category:
            raise DomainError("Choose a category from the list.")
        return category

    def _brand(self, data):
        choice = data.get('brand_choice')
        if choice == 'unknown':
            return ''
        if choice == 'unbranded':
            return 'Unbranded'
        if choice not in (None,'known'):
            raise DomainError('Choose known, unknown, or no visible brand.')
        value = self._text(data,'brand',required=choice=='known',maximum=80)
        if choice == 'known' and not brand_key(value):
            raise DomainError('Enter the brand name or choose I don’t know.')
        return value if brand_key(value) else ''


