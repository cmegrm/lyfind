"""Transactional use cases. The service is the only supported writer of domain state."""
import json
import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import timedelta, date, datetime, timezone
from pathlib import Path

from domain import Claim, Item
from matching import AIMatchingService, SavedEmbeddings, ClipAdapter, MatchingServiceFactory, TypedDetailsMatchingService, brand_key
from users import DomainError, User, hash_password, require_permission
from storage import resolve_upload
from ai_runtime import LocalAI


ACTIVE = ("step1_pending", "step2_pending", "verified", "approved")
BOARD_TYPES = {
    "electronics": ("Phone", "Headphones", "Charger", "Calculator", "Other electronics"),
    "bags": ("Backpack", "Tote bag", "Other bag"),
    "clothing": ("Jacket", "Sweater", "Other clothing"),
    "accessories": ("Umbrella", "Glasses", "Water bottle", "Other accessory"),
}
CLAIM_REJECTED_MESSAGE = "CSA could not verify ownership from the evidence provided."
BOARD_AREAS = ("library", "cafeteria", "gym", "canteen", "auditorium")
HOLDING_PERIOD_ELAPSED = "julianday('now')-julianday(received_at)>=unclaimed_after_days"


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class AuditLog:
    """Append entries through a method; SQLite also rejects UPDATE and DELETE."""
    def __init__(self, conn):
        self._conn = conn

    def record(self, actor, action, detail):
        self._conn.execute("INSERT INTO audit_logs(actor_id,action,detail) VALUES(?,?,?)",
                           (actor.id if actor else None, action, str(detail)))


class Service:
    def __init__(self, db, upload_dir=None, matcher=None):
        self.db = db
        self.upload_dir = Path(upload_dir) if upload_dir else None
        self.matcher = matcher
        self._ai_load_attempted = False
        self._ai_adapter = None
        self._ai_error = None
        self.ai = LocalAI()

    def prepare_matching(self):
        """Load local weights before serving requests, outside database transactions."""
        return self.ai.prepare()

    @contextmanager
    def _tx(self):
        conn = self.db.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except sqlite3.IntegrityError as error:
            conn.rollback()
            raise DomainError("The operation conflicts with a saved record or workflow rule.") from error
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
            raise DomainError("Record not found.", 404)
        return dict(row)

    @staticmethod
    def _text(data, field, required=True, maximum=2000):
        if data.get(field) is not None and not isinstance(data.get(field), (str, int, float)):
            raise DomainError(f"Enter text for {field.replace('_',' ')}.")
        value = str(data.get(field, "") or "").strip()
        if required and not value:
            raise DomainError(f"Enter {field.replace('_',' ')}.")
        if len(value) > maximum:
            raise DomainError(f"{field.replace('_',' ').title()} is too long (maximum {maximum}).")
        return value

    def _date(self, data, field, future=False):
        value = self._text(data, field, maximum=10)
        try:
            parsed = date.fromisoformat(value)
        except ValueError:
            raise DomainError(f"Enter a valid {field.replace('_',' ')}.")
        if not future and parsed > date.today():
            raise DomainError(f"{field.replace('_',' ').title()} cannot be in the future.")
        return value

    @staticmethod
    def _notify(conn, user_id, message, report_id=None, claim_id=None):
        conn.execute("INSERT INTO notifications(user_id,message,report_id,claim_id) VALUES(?,?,?,?)",
                     (user_id, message, report_id, claim_id))

    def _photo(self, conn, user, photo_id, kind, required=False, claim_id=None):
        if not photo_id:
            if required:
                raise DomainError(f"Upload the {kind.replace('_',' ')} first.")
            return None
        photo = self._row(conn, "uploads", photo_id)
        if photo["kind"] != kind or (photo["owner_id"] != user.id and user.role != "admin"):
            raise DomainError("The selected upload cannot be used here.", 403)
        if claim_id is not None and photo["claim_id"] != int(claim_id):
            raise DomainError("Evidence must be uploaded for this specific claim.")
        if not photo["mime"].startswith("image/"):
            raise DomainError("Use an image file for this field.")
        if self.upload_dir is not None:
            resolve_upload(self.upload_dir, photo["path"], must_exist=True)
        return int(photo_id)

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

    def _check_duplicate(self, conn, kind, user, values, data):
        if kind == "lost":
            sql = "SELECT id,description FROM lost_reports WHERE owner_id=? AND category=? AND date_lost=? AND status='open' ORDER BY id"
            reported_on = values["date_lost"]
        else:
            sql = "SELECT id,description FROM found_reports WHERE finder_id=? AND category=? AND date_found=? AND status='awaiting_turn_in' ORDER BY id"
            reported_on = values["date_found"]
        description = " ".join(values["description"].casefold().split())
        for row in conn.execute(sql, (user.id, values["category"], reported_on)):
            if " ".join(row["description"].casefold().split()) == description:
                if data.get("confirm_duplicate") is False:
                    raise DomainError("This looks like a duplicate of one of your open reports.", 409)
                return row["id"]
        return None

    @staticmethod
    def _flag_duplicate(conn, kind, report_id, duplicate_of):
        if duplicate_of is not None:
            conn.execute("INSERT INTO duplicate_reports(kind,report_id,duplicate_of) VALUES(?,?,?)",
                         (kind, report_id, duplicate_of))

    def review_duplicate(self, admin, kind, report_id):
        admin = self._guard(admin, "receive_item")
        if kind not in ("lost", "found"):
            raise DomainError("Choose a lost or found report.")
        with self._tx() as conn:
            result = conn.execute(
                "UPDATE duplicate_reports SET reviewed_by=? WHERE kind=? AND report_id=? AND reviewed_by IS NULL",
                (admin.id, kind, report_id),
            )
            if not result.rowcount:
                raise DomainError("This flag has already been reviewed or does not exist.")
            AuditLog(conn).record(admin, "DUPLICATE_REVIEWED", f"{kind.title()} report {report_id}")
            return {"reviewed": True}

    def create_lost_report(self, user, data):
        user = self._guard(user, "report_lost")
        with self._tx() as conn:
            return self._save_lost_report(conn, user, user, data)

    def create_guest_lost_report(self, admin, email, data):
        admin = self._guard(admin, "report_for_guest")
        with self._tx() as conn:
            owner = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
            if owner and owner["role"] != "guest":
                raise DomainError("This email belongs to a campus account. Ask the owner to sign in with LPU or CSA.")
            if not owner:
                guest_id = conn.execute("INSERT INTO users(name,email,role) VALUES(?,?,'guest')",
                                        (email.split('@')[0], email)).lastrowid
                owner = self._row(conn, "users", guest_id)
            guest = User.from_row(owner)
            require_permission(guest, "report_lost")
            return self._save_lost_report(conn, admin, guest, data)

    def _save_lost_report(self, conn, actor, owner, data):
        values = {key: self._text(data, key, key in {"category", "description", "place"})
                  for key in ("category", "description", "color", "brand", "place", "identifying_marks")}
        values["category"] = values["category"].casefold()
        values['brand'] = self._brand(data)
        values["date_lost"] = self._date(data, "date_lost")
        duplicate_of = self._check_duplicate(conn, "lost", owner, values, data)
        photo_id = self._photo(conn, actor, data.get("photo_id"), "report_photo")
        if photo_id and actor.id != owner.id:
            transfer = conn.execute("UPDATE uploads SET owner_id=? WHERE id=? AND owner_id=?",
                                    (owner.id, photo_id, actor.id))
            if not transfer.rowcount:
                raise DomainError("Upload a new photo for this guest report.", 403)
        values["photo_id"] = photo_id
        keys = list(values)
        cursor = conn.execute(f"INSERT INTO lost_reports(owner_id,{','.join(keys)}) VALUES({','.join('?' for _ in range(len(keys)+1))})",
                              (owner.id, *[values[k] for k in keys]))
        result = self._row(conn, "lost_reports", cursor.lastrowid)
        self._flag_duplicate(conn, "lost", result["id"], duplicate_of)
        detail = f"Report {result['id']}"
        if actor.id != owner.id:
            detail += f"; recorded for guest {owner.id}"
        AuditLog(conn).record(actor, "LOST_REPORT_CREATED", detail)
        self._run_matching(conn)
        return result

    def close_lost_report(self, user, report_id):
        user = self._guard(user, "report_lost")
        with self._tx() as conn:
            report = self._row(conn, "lost_reports", report_id)
            if report["owner_id"] != user.id:
                raise DomainError("You can only close your own lost report.", 403)
            if report["status"] == "closed":
                return {"closed": True}
            if conn.execute("SELECT 1 FROM claims WHERE report_id=? AND status IN (?,?,?,?)",
                            (report_id, *ACTIVE)).fetchone():
                raise DomainError("Ask CSA to resolve your active claim before closing this report.")
            conn.execute("UPDATE lost_reports SET status='closed' WHERE id=?", (report_id,))
            conn.execute("UPDATE matches SET status='dismissed',withdrawal_reason='Owner recovered their item' "
                         "WHERE report_id=? AND status IN ('suggested','confirmed')", (report_id,))
            self._notify(conn, user.id, "Your lost report is closed because you found your item.", report_id)
            AuditLog(conn).record(user, "LOST_REPORT_CLOSED_BY_OWNER", f"Report {report_id}; owner recovered item")
            return {"closed": True}

    def create_found_report(self, user, data):
        user = self._guard(user, "report_found")
        values = {key: self._text(data, key) for key in ("category", "description", "place")}
        values["category"] = values["category"].casefold()
        values["date_found"] = self._date(data, "date_found")
        values["turn_in_deadline"] = (date.today() + timedelta(days=2)).isoformat()
        with self._tx() as conn:
            duplicate_of = self._check_duplicate(conn, "found", user, values, data)
            keys = list(values)
            cursor = conn.execute(f"INSERT INTO found_reports(finder_id,{','.join(keys)}) VALUES({','.join('?' for _ in range(len(keys)+1))})",
                                  (user.id, *[values[k] for k in keys]))
            result = self._row(conn, "found_reports", cursor.lastrowid)
            self._flag_duplicate(conn, "found", result["id"], duplicate_of)
            AuditLog(conn).record(user, "FOUND_REPORT_CREATED", f"Report {result['id']}; awaiting physical turn-in")
        return result

    def _board_type(self, data, category):
        value = self._text(data, "board_type", required=False, maximum=40)
        if value and value not in BOARD_TYPES.get(category, ()):
            raise DomainError("Choose a listed item type or keep the item private.")
        return value

    @staticmethod
    def _board_campus_only(data):
        value = data.get("board_campus_only", False)
        if not isinstance(value, bool):
            raise DomainError("Choose whether to show only the campus.")
        return int(value)

    def set_board_listing(self, admin, item_id, data):
        admin = self._guard(admin, "receive_item")
        with self._tx() as conn:
            item = self._row(conn, "items", item_id)
            board_type = self._board_type(data, item["category"])
            if board_type and item["status"] != "available" and board_type != item["board_type"]:
                raise DomainError("Only available items can be listed.")
            campus_only = self._board_campus_only(data)
            conn.execute("UPDATE items SET board_type=?,board_campus_only=? WHERE id=?",
                         (board_type, campus_only, item["id"]))
            location = "Campus only" if campus_only else "General area"
            AuditLog(conn).record(admin, "BOARD_LISTING_UPDATED", f"Item {item['id']}; {board_type or 'private'}; {location}")
            return {"board_type": board_type}

    def receive_item(self, admin, data):
        admin = self._guard(admin, "receive_item")
        values = {key: self._text(data, key, key in {"category", "description", "place", "private_details"})
                  for key in ("category", "description", "color", "brand", "place", "private_details")}
        values["category"] = values["category"].casefold()
        values['brand'] = self._brand(data)
        values["date_found"] = self._date(data, "date_found")
        values["board_type"] = self._board_type(data, values["category"])
        values["board_campus_only"] = self._board_campus_only(data)
        try:
            days = data.get("unclaimed_after_days", "")
            values["unclaimed_after_days"] = int(os.getenv("UNCLAIMED_DAYS", "30") if days == "" else days)
            if not 1 <= values["unclaimed_after_days"] <= 3650:
                raise ValueError()
        except (ValueError, TypeError):
            raise DomainError("Unclaimed period must be between 1 and 3650 days.")
        with self._tx() as conn:
            values["photo_id"] = self._photo(conn, admin, data.get("photo_id"), "item_photo", required=True)
            values["found_report_id"] = data.get("found_report_id") or None
            if values["found_report_id"]:
                report = self._row(conn, "found_reports", values["found_report_id"])
                if report["status"] != "awaiting_turn_in":
                    raise DomainError("This found report has already been received.")
                conn.execute("UPDATE found_reports SET status='received' WHERE id=?", (report["id"],))
                self._notify(conn, report["finder_id"], "CSA received the item you turned in.")
            keys = list(values)
            cursor = conn.execute(f"INSERT INTO items(recorded_by,{','.join(keys)}) VALUES({','.join('?' for _ in range(len(keys)+1))})",
                                  (admin.id, *[values[k] for k in keys]))
            result = self._row(conn, "items", cursor.lastrowid)
            AuditLog(conn).record(admin, "ITEM_RECEIVED", f"Item {result['id']}; physical turn-in confirmed")
            self._run_matching(conn)
        return result

    def run_matching(self, admin):
        admin = self._guard(admin, "run_matching")
        with self._tx() as conn:
            return self._run_matching(conn, admin)

    def correct_item(self, admin, item_id, data):
        admin = self._guard(admin, "receive_item")
        reason = self._text(data, "reason")
        values = {key: self._text(data, key, key not in {"color", "brand"})
                  for key in ("category", "description", "place", "private_details", "color", "brand")}
        values["category"] = values["category"].casefold()
        values["brand"] = self._brand(data)
        values["date_found"] = self._date(data, "date_found")
        with self._tx() as conn:
            item = self._row(conn, "items", item_id)
            if item["status"] != "available" or conn.execute(
                "SELECT 1 FROM claims WHERE item_id=? AND status IN (?,?,?,?)", (item_id, *ACTIVE),
            ).fetchone():
                raise DomainError("Only available items without an active claim can be corrected.")
            changes = {key: value for key, value in values.items() if item[key] != value}
            if not changes:
                return item
            if item["board_type"] and item["board_type"] not in BOARD_TYPES.get(values["category"], ()):
                changes["board_type"] = ""
            conn.execute("UPDATE items SET " + ",".join(f"{key}=?" for key in changes) + " WHERE id=?",
                         (*changes.values(), item_id))
            for match in conn.execute(
                "SELECT m.id,m.report_id,r.owner_id FROM matches m JOIN lost_reports r ON r.id=m.report_id "
                "WHERE m.item_id=? AND m.status='confirmed' AND r.status='open'", (item_id,),
            ).fetchall():
                conn.execute("UPDATE matches SET status='suggested',decided_by=NULL WHERE id=?", (match["id"],))
                self._notify(conn, match["owner_id"], "CSA corrected the inventory record and will review the match again.", match["report_id"])
            # Drop suggestions whose category or eligibility may have changed.
            conn.execute("DELETE FROM matches WHERE item_id=? AND status='suggested'", (item_id,))
            before_and_after = {key: {"from": item[key], "to": value} for key, value in changes.items()}
            AuditLog(conn).record(admin, "ITEM_CORRECTED", f"Item {item_id}; {reason}; {json.dumps(before_and_after)}")
            self._run_matching(conn, admin, item_id=item_id)
            return self._row(conn, "items", item_id)

    def _run_matching(self, conn, actor=None, item_id=None):
        log = AuditLog(conn)
        if self.matcher:
            matcher = self.matcher
        else:
            photo_adapter = self.ai.photo_adapter
            if photo_adapter:
                photo_adapter = SavedEmbeddings(conn, photo_adapter, "dinov2-small-v1")
            matcher = MatchingServiceFactory.create(self.ai.adapter is not None, SavedEmbeddings(conn,self.ai.adapter),
                        weights=self.ai.weights, photo_adapter=photo_adapter,
                        log=lambda a, d: log.record(actor, a, d+' '+self.ai.reason))
        reports = [dict(r) for r in conn.execute("SELECT * FROM lost_reports WHERE status='open'")]
        item_sql = "SELECT * FROM items WHERE status='available' AND NOT EXISTS (SELECT 1 FROM claims c WHERE c.item_id=items.id AND c.status IN ('step2_pending','verified','approved'))"
        items = [dict(r) for r in conn.execute(item_sql + (" AND id=?" if item_id is not None else ""),
                                               (item_id,) if item_id is not None else ())]
        for row in reports + items:
            if row.get("photo_id"):
                photo = self._row(conn, "uploads", row["photo_id"])
                row["photo_path"] = str(resolve_upload(self.upload_dir, photo["path"])) if self.upload_dir else photo["path"]
        saved = []
        for report in reports:
            for item in items:
                if str(report['category']).strip().casefold() != str(item['category']).strip().casefold():
                    continue
                try:
                    method = matcher.method
                    if isinstance(matcher, AIMatchingService):
                        score, level, details = matcher.evaluate(report, item)
                    else:
                        score, level = matcher.compare(report, item)
                        details = matcher.explain(report,item) if hasattr(matcher,'explain') else {}
                except Exception:
                    log.record(actor, "AI_UNAVAILABLE", "Embedding failed; used typed details for this comparison")
                    fallback = TypedDetailsMatchingService(self.ai.weights)
                    score, level = fallback.compare(report, item)
                    details = fallback.explain(report,item)
                    details['explanation'] = 'AI inference failed for this pair. Typed details were used and rescaled.'
                    method = "typed_details"
                if level == "hidden":
                    conn.execute("DELETE FROM matches WHERE report_id=? AND item_id=? AND status='suggested'", (report['id'],item['id']))
                    continue
                old = conn.execute("SELECT * FROM matches WHERE report_id=? AND item_id=?", (report["id"], item["id"])).fetchone()
                if old and old["status"] != "suggested":
                    continue
                details['total'] = score
                conn.execute("INSERT INTO matches(report_id,item_id,score,level,method,score_details) VALUES(?,?,?,?,?,?) ON CONFLICT(report_id,item_id) DO UPDATE SET score=excluded.score,level=excluded.level,method=excluded.method,score_details=excluded.score_details",
                             (report["id"], item["id"], score, level, method, json.dumps(details)))
                saved.append({"report_id": report["id"], "item_id": item["id"], "score": score, "level": level, "method": method})
        log.record(actor, "MATCHING_RUN", f"{len(saved)} suggestions saved; owners are not notified of suggestions")
        return {"suggestions": saved, "count": len(saved)}

    def decide_match(self, admin, match_id, confirmed):
        admin = self._guard(admin, "decide_match")
        if not isinstance(confirmed, bool):
            raise DomainError("Choose confirm or dismiss.")
        with self._tx() as conn:
            match = self._row(conn, "matches", match_id)
            if match["status"] != "suggested":
                raise DomainError("This suggestion has already been reviewed.")
            item = self._row(conn, "items", match["item_id"])
            report = self._row(conn, "lost_reports", match["report_id"])
            if item["status"] != "available" or report["status"] != "open":
                raise DomainError("The item or report is no longer available for matching.")
            status = "confirmed" if confirmed else "dismissed"
            conn.execute("UPDATE matches SET status=?,decided_by=? WHERE id=?", (status, admin.id, match_id))
            if confirmed:
                self._notify(conn, report["owner_id"], "CSA found a possible item for your report. Submit ownership answers to begin verification.", report["id"])
            AuditLog(conn).record(admin, "MATCH_" + status.upper(), f"Match {match_id}")
            return self._row(conn, "matches", match_id)

    def withdraw_invitation(self, admin, match_id, data):
        admin = self._guard(admin, "decide_match")
        reason = self._text(data, "reason")
        with self._tx() as conn:
            match = self._row(conn, "matches", match_id)
            if match["status"] != "confirmed":
                raise DomainError("Only a confirmed invitation can be withdrawn.")
            report = self._row(conn, "lost_reports", match["report_id"])
            if report["status"] != "open":
                raise DomainError("This lost report is closed.")
            blocking = conn.execute(
                "SELECT id,status FROM claims WHERE report_id=? AND item_id=? AND status<>'rejected'",
                (report["id"], match["item_id"]),
            ).fetchone()
            if blocking:
                raise DomainError(f"Resolve claim #{blocking['id']} in Ownership claims before withdrawing this invitation.")
            conn.execute("UPDATE matches SET status='dismissed',withdrawal_reason=?,decided_by=? WHERE id=?",
                         (reason, admin.id, match_id))
            self._notify(conn, report["owner_id"],
                         "CSA withdrew a verification invitation. Your lost report remains open for other matches.",
                         report["id"])
            AuditLog(conn).record(admin, "INVITATION_WITHDRAWN", f"Match {match_id}; {reason}")
            return {"status": "withdrawn"}

    def submit_claim(self, user, data):
        try:
            return self._submit_claim(user, data)
        except DomainError as error:
            if user:
                with self._tx() as conn:
                    if conn.execute("SELECT id FROM users WHERE id=?", (user.id,)).fetchone():
                        AuditLog(conn).record(user, "CLAIM_REFUSED", str(error))
            raise

    def _submit_claim(self, user, data):
        user = self._guard(user, "submit_claim")
        answers = data.get("answers")
        if not isinstance(answers, dict) or not answers or len(answers) > 20 or any(not isinstance(k, str) or not isinstance(v, str) or not k.strip() or not v.strip() or len(v) > 3000 for k, v in answers.items()):
            raise DomainError("Answer all ownership questions before submitting.")
        if data.get("consent") is not True:
            raise DomainError("Consent to submit verification answers is required.")
        with self._tx() as conn:
            item = self._row(conn, "items", data.get("item_id"))
            report = self._row(conn, "lost_reports", data.get("report_id"))
            if report["owner_id"] != user.id:
                raise DomainError("You can only claim for your own report.", 403)
            if report["status"] != "open" or item["status"] not in ("available","under_verification"):
                raise DomainError("The item is released, unclaimed, or currently under verification.")
            match = conn.execute("SELECT id FROM matches WHERE item_id=? AND report_id=? AND status='confirmed'", (item["id"], report["id"])).fetchone()
            if not match:
                raise DomainError("Wait for a CSA-confirmed verification invitation.", 403)
            if conn.execute("SELECT id FROM claims WHERE item_id=? AND claimant_id=? AND status IN ('step1_pending','step2_pending','verified','approved')", (item["id"],user.id)).fetchone():
                raise DomainError("This item already has an active claim. Wait for availability.")
            attempts = conn.execute("SELECT COUNT(*) FROM claims WHERE item_id=? AND claimant_id=? AND status='rejected' AND reservation_ended=0", (item["id"], user.id)).fetchone()[0]
            if attempts >= 3:
                raise DomainError("Three rejected attempts block further claims for this item.", 403)
            cursor = conn.execute("INSERT INTO claims(claimant_id,item_id,report_id,answers,online_consent) VALUES(?,?,?,?,1)",
                                  (user.id, item["id"], report["id"], json.dumps(answers)))
            AuditLog(conn).record(user, "CLAIM_SUBMITTED", f"Claim {cursor.lastrowid}; item {item['id']}")
            return self._row(conn, "claims", cursor.lastrowid)

    def _reject(self, conn, admin, claim, reason):
        if not str(reason).strip():
            raise DomainError("Record a reason when rejecting a claim.")
        model = Claim(claim["id"], claim["status"], claim["in_person_consent"])
        model.advance("rejected")
        conn.execute("UPDATE claims SET status=?,reason=? WHERE id=?", (model.status, str(reason).strip(), claim["id"]))
        if claim["status"] != "step1_pending":
            self._free_reservation(conn, admin, claim["item_id"])
        count = conn.execute("SELECT COUNT(*) FROM claims WHERE claimant_id=? AND item_id=? AND status='rejected' AND reservation_ended=0", (claim["claimant_id"], claim["item_id"])).fetchone()[0]
        self._notify(conn, claim["claimant_id"], f"{CLAIM_REJECTED_MESSAGE} Rejected attempts for this item: {count}/3.", claim["report_id"], claim["id"])
        AuditLog(conn).record(admin, "CLAIM_REJECTED", f"Claim {claim['id']}; attempt {count}; {reason}")

    def _free_reservation(self, conn, admin, item_id):
        item = self._row(conn, "items", item_id)
        if item["status"] == "under_verification":
            model_item = Item(item["id"], item["status"])
            model_item.change_status("available")
            conn.execute("UPDATE items SET status=? WHERE id=?", (model_item.status, item["id"]))
            waiting = conn.execute("SELECT * FROM claims WHERE item_id=? AND status='step1_pending' AND online_verified_by IS NOT NULL ORDER BY id LIMIT 1",(item["id"],)).fetchone()
            if waiting:
                conn.execute("UPDATE claims SET status='step2_pending' WHERE id=?", (waiting["id"],))
                conn.execute("UPDATE items SET status='under_verification' WHERE id=?", (item["id"],))
                self._notify(conn,waiting["claimant_id"],"Your in-person check is ready. Bring your ID and proof.",waiting["report_id"],waiting["id"])
                AuditLog(conn).record(admin,"WAITING_CLAIM_PROMOTED",str(waiting["id"]))

    def end_reservation(self, admin, claim_id, data):
        admin = self._guard(admin, "verify_in_person")
        reason = self._text(data, "reason")
        with self._tx() as conn:
            claim = self._row(conn, "claims", claim_id)
            if claim["status"] != "step2_pending" or not claim["consent_declined_at"] or claim["in_person_consent"]:
                raise DomainError("Only a visit paused before consent can end this way.")
            model = Claim(claim_id, claim["status"])
            model.advance("rejected")
            conn.execute("UPDATE claims SET status=?,reservation_ended=1,reason=? WHERE id=?", (model.status, reason, claim_id))
            self._free_reservation(conn, admin, claim["item_id"])
            self._notify(conn, claim["claimant_id"], "CSA ended your paused reservation. Your lost report remains open.", claim["report_id"], claim_id)
            AuditLog(conn).record(admin, "RESERVATION_ENDED", f"Claim {claim_id}; {reason}")
            return {"status": "reservation_ended"}

    def verify_online(self, admin, claim_id, passed, reason=""):
        admin = self._guard(admin, "verify_online")
        if not isinstance(passed, bool):
            raise DomainError("Record a pass or fail decision.")
        with self._tx() as conn:
            claim = self._row(conn, "claims", claim_id)
            if claim["status"] != "step1_pending" or claim["online_verified_by"]:
                raise DomainError("Online verification has already been decided.")
            if passed:
                model = Claim(claim_id, claim["status"])
                model.advance("step2_pending")
                item = self._row(conn, "items", claim["item_id"])
                if item["status"] == "under_verification":
                    conn.execute("UPDATE claims SET online_verified_by=? WHERE id=?",(admin.id,claim_id))
                    self._notify(conn,claim["claimant_id"],"Online check passed. Wait for your in-person invitation.",claim["report_id"],claim_id)
                    AuditLog(conn).record(admin,"STEP1_PASSED_WAITING",str(claim_id))
                    return self._row(conn,"claims",claim_id)
                model_item = Item(item["id"], item["status"])
                model_item.change_status("under_verification")
                conn.execute("UPDATE claims SET status=?,online_verified_by=? WHERE id=?", (model.status, admin.id, claim_id))
                conn.execute("UPDATE items SET status=? WHERE id=?", (model_item.status, item["id"]))
                self._notify(conn, claim["claimant_id"], "Online verification passed. Visit the CSA office with ID and proof of ownership.", claim["report_id"], claim_id)
                AuditLog(conn).record(admin, "STEP1_PASSED", f"Claim {claim_id}; notes: {str(reason).strip()[:2000]}")
            else:
                self._reject(conn, admin, claim, reason)
            return self._row(conn, "claims", claim_id)

    def record_consent(self, user, claim_id, data):
        user = self._guard(user, "record_consent" if user.role == "admin" else "view_own")
        if data.get("in_person") is not True:
            raise DomainError("The claimant must give explicit consent in person.")
        purpose = self._text(data, "purpose", maximum=1000)
        with self._tx() as conn:
            claim = self._row(conn, "claims", claim_id)
            if user.role != "admin" and user.id != claim["claimant_id"]:
                raise DomainError("You cannot record consent for another claimant.", 403)
            if user.role != "admin":
                raise DomainError("CSA must record consent with the claimant present at the office.", 403)
            model = Claim(claim_id, claim["status"], claim["in_person_consent"])
            if model.consent:
                raise DomainError("In-person consent has already been recorded.")
            model.record_consent()
            conn.execute("UPDATE claims SET in_person_consent=1,consent_at=?,consent_purpose=?,consent_recorded_by=? WHERE id=?", (now(), purpose, user.id, claim_id))
            AuditLog(conn).record(user, "IN_PERSON_CONSENT_RECORDED", f"Claim {claim_id}; purpose: {purpose}")
            return self._row(conn, "claims", claim_id)

    def record_consent_declined(self, admin, claim_id):
        admin = self._guard(admin, "record_consent")
        with self._tx() as conn:
            claim = self._row(conn, "claims", claim_id)
            if claim["status"] != "step2_pending" or claim["in_person_consent"]:
                raise DomainError("Record declined consent only before the in-person check begins.")
            if not claim["consent_declined_at"]:
                conn.execute("UPDATE claims SET consent_declined_at=? WHERE id=?", (now(), claim_id))
                self._notify(conn, claim["claimant_id"],
                             "Your in-person check paused because consent was declined. Contact CSA if you want to resume.",
                             claim["report_id"], claim_id)
                AuditLog(conn).record(admin, "IN_PERSON_CONSENT_DECLINED", f"Claim {claim_id}; visit paused")
            return self._row(conn, "claims", claim_id)

    def verify_in_person(self, admin, claim_id, passed, reason=""):
        admin = self._guard(admin, "verify_in_person")
        if not isinstance(passed, bool):
            raise DomainError("Record a pass or fail decision.")
        with self._tx() as conn:
            claim = self._row(conn, "claims", claim_id)
            if claim["status"] != "step2_pending":
                raise DomainError("Pass online verification before the in-person check.")
            if not claim["in_person_consent"]:
                raise DomainError("Record explicit in-person consent before the ownership check.")
            if passed:
                model = Claim(claim_id, claim["status"], claim["in_person_consent"])
                model.advance("verified")
                conn.execute("UPDATE claims SET status=?,in_person_verified_by=? WHERE id=?", (model.status, admin.id, claim_id))
                AuditLog(conn).record(admin, "STEP2_PASSED", f"Claim {claim_id}; ID and ownership proof checked in person; notes: {str(reason).strip()[:2000]}")
            else:
                self._reject(conn, admin, claim, reason)
            return self._row(conn, "claims", claim_id)

    def approve_claim(self, admin, claim_id, data):
        admin = self._guard(admin, "approve_claim")
        evidence = data.get("evidence", data)
        with self._tx() as conn:
            claim = self._row(conn, "claims", claim_id)
            model = Claim(claim_id, claim["status"], claim["in_person_consent"])
            model.advance("approved")
            if not claim["online_verified_by"] or not claim["in_person_verified_by"]:
                raise DomainError("Both verification steps must pass before approval.")
            ids = []
            for kind in ("claimant_photo", "id_photo", "signature"):
                file_id = self._photo(conn, admin, evidence.get(kind), kind, required=True, claim_id=claim_id)
                file = self._row(conn, "uploads", file_id)
                if not claim["consent_at"] or file["created_at"] < claim["consent_at"]:
                    raise DomainError("Evidence cannot be captured before consent.")
                ids.append(file_id)
            conn.execute("UPDATE claims SET status=?,claimant_photo=?,id_photo=?,signature=?,evidence_captured_at=?,approved_by=?,approved_at=?,handover_note=? WHERE id=?",
                         (model.status, *ids, now(), admin.id, now(), self._text(data, "handover_note", required=False), claim_id))
            AuditLog(conn).record(admin, "CLAIM_APPROVED", f"Claim {claim_id}; verified evidence recorded")
            self._notify(conn, claim["claimant_id"], "Your claim is approved. CSA will complete the physical handover.", claim["report_id"], claim_id)
            return self._row(conn, "claims", claim_id)

    def release_item(self, admin, claim_id):
        admin = self._guard(admin, "release_item")
        with self._tx() as conn:
            claim = self._row(conn, "claims", claim_id)
            model = Claim(claim_id, claim["status"], claim["in_person_consent"])
            model.advance("released")
            if not all(claim[k] for k in ("online_verified_by", "in_person_verified_by", "claimant_photo", "id_photo", "signature", "approved_by")):
                raise DomainError("Approval and all release evidence are required.")
            for kind in ("claimant_photo", "id_photo", "signature"):
                self._photo(conn, admin, claim[kind], kind, required=True, claim_id=claim_id)
            item = self._row(conn, "items", claim["item_id"])
            model_item = Item(item["id"], item["status"])
            model_item.change_status("released")
            conn.execute("UPDATE claims SET status=?,released_by=?,released_at=? WHERE id=?", (model.status, admin.id, now(), claim_id))
            conn.execute("UPDATE items SET status=? WHERE id=?", (model_item.status, item["id"]))
            conn.execute("UPDATE lost_reports SET status='closed' WHERE id=?", (claim["report_id"],))
            for other in conn.execute("SELECT * FROM claims WHERE item_id=? AND status='step1_pending'",(item["id"],)).fetchall():
                conn.execute("UPDATE claims SET status='rejected',reason='Item already released' WHERE id=?",(other["id"],))
                self._notify(conn,other["claimant_id"],"Claim closed: item already released.",other["report_id"],other["id"])
                AuditLog(conn).record(admin,"CLAIM_CLOSED_ON_RELEASE",str(other["id"]))
            self._notify(conn, claim["claimant_id"], "Your item has been released. The claim is complete and your report is closed.", claim["report_id"], claim_id)
            AuditLog(conn).record(admin, "ITEM_RELEASED", f"Item {item['id']} to claimant {claim['claimant_id']}; claim {claim_id}; handover complete")
            return self._row(conn, "claims", claim_id)

    def expire_items(self, admin):
        admin = self._guard(admin, "expire_items")
        with self._tx() as conn:
            rows = conn.execute(f"SELECT * FROM items WHERE status='available' AND {HOLDING_PERIOD_ELAPSED} AND NOT EXISTS(SELECT 1 FROM claims c WHERE c.item_id=items.id AND c.status IN ('step1_pending','step2_pending','verified','approved'))").fetchall()
            for row in rows:
                model = Item(row["id"], row["status"])
                model.change_status("unclaimed")
                conn.execute("UPDATE items SET status=? WHERE id=?", (model.status, row["id"]))
                AuditLog(conn).record(admin, "ITEM_UNCLAIMED", f"Item {row['id']}; retention period elapsed")
            return {"expired": len(rows)}

    def authorize_upload(self, user, kind, claim_id=None):
        permission = {
            "item_photo": "receive_item",
            "claimant_photo": "approve_claim",
            "id_photo": "approve_claim",
            "signature": "approve_claim",
            "report_photo": "report_for_guest" if user and user.role == "admin" else "report_lost",
        }.get(kind, "report_lost")
        user = self._guard(user, permission)
        if kind not in {"report_photo", "item_photo", "claimant_photo", "id_photo", "signature"}:
            raise DomainError("Unknown upload purpose.")
        if kind in {"claimant_photo", "id_photo", "signature"}:
            with self.db.connect() as conn:
                claim = self._row(conn, "claims", claim_id)
                if claim["status"] not in {"step2_pending", "verified"} or not claim["in_person_consent"]:
                    raise DomainError("Record in-person consent after online verification before capturing evidence.")
        return True

    def file_access(self, user, file_id):
        user = self._guard(user, "view_own")
        with self.db.connect() as conn:
            upload = self._row(conn, "uploads", file_id)
        if user.role != "admin" and not (upload["kind"] == "report_photo" and upload["owner_id"] == user.id):
            raise DomainError("This image is restricted to CSA staff.", 403)
        return upload

    def _draft_evidence(self, conn, admin):
        if self.upload_dir is None:
            return {}
        drafts = {}
        expired = 0
        for upload in conn.execute(
            "SELECT u.*,c.status AS claim_status,c.consent_at,"
            "julianday('now')-julianday(u.created_at)>=7 AS expired "
            "FROM uploads u JOIN claims c ON c.id=u.claim_id "
            "WHERE u.kind IN ('claimant_photo','id_photo','signature') AND NOT EXISTS ("
            "SELECT 1 FROM claims attached WHERE u.id IN (attached.claimant_photo,attached.id_photo,attached.signature)) "
            "ORDER BY u.id",
        ).fetchall():
            try:
                path = resolve_upload(self.upload_dir, upload["path"])
                if upload["expired"]:
                    shared = conn.execute("SELECT 1 FROM uploads WHERE path=? AND id<>?",
                                          (upload["path"], upload["id"])).fetchone()
                    if not shared:
                        path.unlink(missing_ok=True)
                    conn.execute("DELETE FROM uploads WHERE id=?", (upload["id"],))
                    expired += 1
                elif (upload["claim_status"] in ("step2_pending", "verified") and upload["consent_at"]
                      and upload["created_at"] >= upload["consent_at"] and path.is_file()):
                    drafts.setdefault(upload["claim_id"], {})[upload["kind"]] = upload["id"]
            except (DomainError, OSError):
                continue
        if expired:
            AuditLog(conn).record(admin, "ABANDONED_EVIDENCE_CLEANED", f"{expired} unattached uploads removed")
        return drafts

    def manage_staff(self, admin, data):
        admin = self._guard(admin, "manage_staff")
        action = data.get("action", "create")
        with self._tx() as conn:
            if action == "create":
                if data.get("role", "admin") != "admin":
                    raise DomainError("Staff management creates CSA administrator accounts only.")
                name = self._text(data, "name", maximum=120)
                email = self._text(data, "email", maximum=254).casefold()
                if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
                    raise DomainError("Enter a valid staff email address.")
                password = hash_password(str(data.get("password", "")))
                cursor = conn.execute("INSERT INTO users(name,email,role,password_hash) VALUES(?,?,'admin',?)", (name, email, password))
                result = self._row(conn, "users", cursor.lastrowid)
                AuditLog(conn).record(admin, "STAFF_CREATED", f"Administrator {cursor.lastrowid}")
            elif action == "update":
                staff = self._row(conn, "users", data.get("user_id"))
                if staff["role"] != "admin":
                    raise DomainError("Guest and university identities cannot be promoted through staff management.")
                active_value = data.get("active", bool(staff["active"]))
                if not isinstance(active_value, bool):
                    raise DomainError("Staff active status must be true or false.")
                active = active_value
                if not active and conn.execute("SELECT COUNT(*) FROM users WHERE role='admin' AND active=1 AND blocked=0").fetchone()[0] <= 1:
                    raise DomainError("Keep at least one active CSA administrator.")
                if data.get("role", "admin") != "admin":
                    raise DomainError("CSA staff role cannot be changed to a public role.")
                name = self._text(data, "name", required=False, maximum=120) or staff["name"]
                email = self._text(data, "email", required=False, maximum=254).casefold() or staff["email"]
                if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
                    raise DomainError("Enter a valid staff email address.")
                conn.execute("UPDATE users SET active=?,name=?,email=? WHERE id=?", (int(active), name, email, staff["id"]))
                if data.get("password"):
                    conn.execute("UPDATE users SET password_hash=? WHERE id=?", (hash_password(str(data["password"])), staff["id"]))
                result = self._row(conn, "users", staff["id"])
                AuditLog(conn).record(admin, "STAFF_UPDATED", f"Administrator {staff['id']}; active={active}")
            else:
                raise DomainError("Unknown staff operation.")
            result.pop("password_hash", None)
            return result

    def dashboard(self, user):
        user = self._guard(user, "view_own")
        with self._tx() as conn:
            for overdue in conn.execute("SELECT * FROM found_reports WHERE status='awaiting_turn_in' AND turn_in_deadline<? AND id NOT IN (SELECT report_id FROM overdue_notices)",(date.today().isoformat(),)).fetchall():
                conn.execute("INSERT INTO overdue_notices VALUES(?)",(overdue["id"],))
                self._notify(conn,overdue["finder_id"],f"Report #{overdue['id']} is overdue. Please bring the item to CSA.")
            def rows(sql, params=()):
                return [dict(r) for r in conn.execute(sql, params)]
            result = {"user": user.public(), "items": [], "reports": [], "found_reports": [], "claims": [],
                      "matches": [], "staff": [], "audit": [], "notifications": rows("SELECT * FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT 100", (user.id,))}
            admin = user.role == "admin"
            if "view_found_board" in user.permissions():
                board = []
                for item in conn.execute(
                    "SELECT category,board_type,board_campus_only,place,date_found FROM items "
                    f"WHERE status='available' AND board_type<>'' AND NOT ({HOLDING_PERIOD_ELAPSED}) "
                    "ORDER BY date_found DESC,id DESC",
                ):
                    if item["board_type"] not in BOARD_TYPES.get(item["category"], ()):
                        continue
                    words = set(re.findall(r"[a-z]+", item["place"].lower()))
                    area = "Campus"
                    if not item["board_campus_only"]:
                        area = next((name.title() for name in BOARD_AREAS if name in words), "Campus")
                    found = date.fromisoformat(item["date_found"])
                    board.append({
                        "category": item["category"],
                        "type": item["board_type"],
                        "area": area,
                        "week": (found - timedelta(days=found.weekday())).isoformat(),
                    })
                result["found_board"] = board
            result["reports"] = rows("SELECT r.*,u.name AS owner_name FROM lost_reports r JOIN users u ON u.id=r.owner_id " + ("" if admin else "WHERE owner_id=? ") + "ORDER BY r.id DESC", () if admin else (user.id,))
            result["found_reports"] = rows("SELECT f.*,u.name AS finder_name FROM found_reports f JOIN users u ON u.id=f.finder_id " + ("" if admin else "WHERE finder_id=? ") + "ORDER BY f.id DESC", () if admin else (user.id,))
            for found in result["found_reports"]:
                if found["status"]=="awaiting_turn_in" and found["turn_in_deadline"]<date.today().isoformat():
                    found["status"]="overdue"
            claim_sql = "SELECT c.*,u.name AS claimant_name,u.email AS claimant_email,i.description AS item_description,i.private_details,i.photo_id AS item_photo_id,i.category AS item_category,r.description AS report_description FROM claims c JOIN users u ON u.id=c.claimant_id JOIN items i ON i.id=c.item_id JOIN lost_reports r ON r.id=c.report_id "
            if not admin:
                for notice in result["notifications"]:
                    if notice["message"].startswith("Claim rejected:"):
                        notice["message"] = CLAIM_REJECTED_MESSAGE
            result["claims"] = rows(claim_sql + ("" if admin else "WHERE c.claimant_id=? ") + "ORDER BY c.id DESC", () if admin else (user.id,))
            drafts = self._draft_evidence(conn, user) if admin else {}
            for claim in result["claims"]:
                claim["answers"] = json.loads(claim["answers"])
                claim["step1_passed"] = bool(claim["online_verified_by"])
                claim["step2_passed"] = bool(claim["in_person_verified_by"])
                if not admin:
                    for field in ("private_details", "item_photo_id", "claimant_photo", "id_photo", "signature"):
                        claim.pop(field, None)
                    claim["item_description"] = claim["item_category"].replace("_", " ").title() + " held by CSA"
                    if claim["reservation_ended"]:
                        claim["reason"] = "CSA ended the paused reservation. Your report remains open."
                    elif claim["status"] == "rejected" and claim["reason"] != "Item already released":
                        claim["reason"] = CLAIM_REJECTED_MESSAGE
                else:
                    claim["draft_evidence"] = drafts.get(claim["id"], {})
                    claim["previous_rejections"] = conn.execute(
                        "SELECT COUNT(*) FROM claims WHERE claimant_id=? AND item_id=? AND status='rejected' AND reservation_ended=0 AND id<?",
                        (claim["claimant_id"], claim["item_id"], claim["id"]),
                    ).fetchone()[0]
            if admin:
                result["board_types"] = BOARD_TYPES
                result["duplicates"] = rows("SELECT * FROM duplicate_reports WHERE reviewed_by IS NULL ORDER BY report_id DESC")
                result["board_areas"] = BOARD_AREAS
                result['matching_status'] = self.ai.status()
                result["items"] = rows(f"SELECT i.*,u.name AS recorded_by_name, ({HOLDING_PERIOD_ELAPSED}) AS holding_period_elapsed, (SELECT COUNT(*) FROM claims c WHERE c.item_id=i.id AND c.status IN ('step1_pending','step2_pending','verified','approved')) AS active_claims FROM items i JOIN users u ON u.id=i.recorded_by ORDER BY i.id DESC")
                result["matches"] = rows("SELECT m.*,i.description AS item_description,i.private_details,i.photo_id AS item_photo_id,r.description AS report_description,r.owner_id,u.name AS owner_name FROM matches m JOIN items i ON i.id=m.item_id JOIN lost_reports r ON r.id=m.report_id JOIN users u ON u.id=r.owner_id ORDER BY m.id DESC")
                available = {item['id'] for item in result['items']
                             if item['status'] == 'available' and not item['holding_period_elapsed']
                             and not item['active_claims']}
                open_reports = {report['id'] for report in result['reports'] if report['status'] == 'open'}
                by_report = {}
                for match in result['matches']:
                    match['score_details'] = json.loads(match['score_details'] or '{}')
                    if (match['status'] == 'suggested' and match['item_id'] in available
                            and match['report_id'] in open_reports):
                        by_report.setdefault(match['report_id'], []).append(match)
                for candidates in by_report.values():
                    best = max(candidate['score'] for candidate in candidates)
                    close = [candidate for candidate in candidates if best - candidate['score'] <= 6]
                    if len(close) > 1:
                        for candidate in close:
                            candidate['similar_candidates'] = len(close) - 1
                result["staff"] = rows("SELECT id,name,email,role,active,blocked,created_at FROM users WHERE role='admin' ORDER BY id")
                result["audit"] = rows("SELECT a.*,COALESCE(u.name,'System') AS actor_name FROM audit_logs a LEFT JOIN users u ON u.id=a.actor_id ORDER BY a.id DESC LIMIT 250")
            else:
                result["matches"] = rows("SELECT m.id,m.report_id,m.item_id,m.status,i.category,i.status AS item_status,r.description AS report_description FROM matches m JOIN items i ON i.id=m.item_id JOIN lost_reports r ON r.id=m.report_id WHERE m.status='confirmed' AND r.owner_id=? AND r.status='open' ORDER BY m.id DESC", (user.id,))
                for match in result["matches"]:
                    busy = conn.execute("SELECT COUNT(*) FROM claims WHERE item_id=? AND claimant_id=? AND status IN ('step1_pending','step2_pending','verified','approved')", (match["item_id"],user.id)).fetchone()[0]
                    attempts = conn.execute("SELECT COUNT(*) FROM claims WHERE claimant_id=? AND item_id=? AND status='rejected' AND reservation_ended=0", (user.id, match["item_id"])).fetchone()[0]
                    match["can_claim"] = match["item_status"] in ("available","under_verification") and not busy and attempts < 3
                    match["eligibility_note"] = ("The three-rejection limit for this item has been reached." if attempts >= 3 else "This item is currently reserved for verification. Wait for availability." if busy else "This item is no longer available for a claim." if match["item_status"] != "available" else "")
            result["stats"] = {"items": len(result["items"]), "reports": len(result["reports"]), "claims": len(result["claims"]),
                               "available": sum(i["status"] == "available" for i in result["items"]),
                               "pending": sum(c["status"] in ACTIVE for c in result["claims"]),
                               "released": sum(c["status"] == "released" for c in result["claims"]),
                               "suggestions": sum(m["status"] == "suggested" for m in result["matches"])}
            return result
