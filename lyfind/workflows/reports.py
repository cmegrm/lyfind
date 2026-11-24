"""Lost and found reports, guest desk reports, and staff review."""
import hashlib
import json
import re
from lyfind.users import DomainError, User

from .base import AuditLog, FOUND_NOW, TIMES, WorkflowBase


class ReportService(WorkflowBase):
    """Lost and found reports, guest desk reports, and staff review."""

    def _report_receipt(self, conn, user, kind, data):
        key = data.get('submission_key')
        if key is None:
            return None, None
        if not isinstance(key, str) or not re.fullmatch(r'[A-Za-z0-9_-]{16,128}', key):
            raise DomainError('Open a new report and try again.', 400)
        payload = {k:v for k,v in data.items() if k != 'submission_key'}
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        existing = conn.execute('SELECT * FROM report_receipts WHERE user_id=? AND kind=? AND submission_key=?', (user.id,kind,key)).fetchone()
        if existing:
            if existing['data_hash'] != digest:
                raise DomainError('This submission was already saved with different details. Check My reports before starting another report.', 409)
            table = 'lost_reports' if kind == 'lost' else 'found_reports'
            return dict(conn.execute(f'SELECT * FROM {table} WHERE id=?', (existing['report_id'],)).fetchone()), None
        return None, (key, digest)

    @staticmethod
    def _save_report_receipt(conn, user, kind, report_id, receipt):
        if receipt:
            conn.execute('INSERT INTO report_receipts(user_id,kind,submission_key,data_hash,report_id) VALUES(?,?,?,?,?)', (user.id,kind,*receipt,report_id))

    def create_lost_report(self, user, data):
        user = self._guard(user, "report_lost")
        values = self._lost_details(data)
        with self._tx() as conn:
            saved, receipt = self._report_receipt(conn, user, 'lost', data)
            if saved is not None:
                return saved
            self._daily_cap(conn, user, "lost")
            values["photo_id"] = self._photo(conn, user, data.get("photo_id"), "report_photo")
            values["flagged"] = int(user.role == "guest")  # a guest's report waits for a staff check
            keys = list(values)
            cursor = conn.execute(f"INSERT INTO lost_reports(owner_id,{','.join(keys)}) VALUES({','.join('?' for _ in range(len(keys)+1))})",
                                  (user.id, *[values[k] for k in keys]))
            result = self._row(conn, "lost_reports", cursor.lastrowid)
            AuditLog(conn).record(user, "LOST_REPORT_CREATED", f"Report {result['id']}")
            self._save_report_receipt(conn, user, 'lost', result['id'], receipt)
        self._run_matching_unlocked()
        return result

    def _lost_details(self, data):
        values = {key: self._text(data, key, key in {"category", "description", "place"})
                  for key in ("category", "description", "color", "brand", "place", "identifying_marks")}
        values["category"] = self._category(values["category"])
        values["brand"] = self._brand(data)
        values["date_lost"] = self._date(data, "date_lost")
        values["time_lost"] = self._time(data, "time_lost")
        return values

    def _time(self, data, field):
        value = self._text(data, field, required=False, maximum=20)
        if value and value not in TIMES:
            raise DomainError("Choose a time of day from the list.")
        return value

    def _save_guest_lost(self, conn, staff, owner, values):
        self._daily_cap(conn, owner, "lost")
        values = dict(values)
        values["flagged"] = 0
        keys = list(values)
        cursor = conn.execute(
            f"INSERT INTO lost_reports(owner_id,{','.join(keys)}) VALUES({','.join('?' for _ in range(len(keys)+1))})",
            (owner.id, *[values[k] for k in keys]))
        result = self._row(conn, "lost_reports", cursor.lastrowid)
        AuditLog(conn).record(staff, "LOST_REPORT_CREATED", f"Report {result['id']} for guest {owner.email}")
        self._notify(conn, owner.id, "CSA saved a lost report for you at the desk.", result["id"])
        return result

    def create_lost_report_for_guest(self, staff, data, auth=None, ip="local"):
        """Save a desk report onto a Guest account. A new visitor gets a sign-up code, and the report waits until they finish."""
        staff = self._guard(staff, "moderate")
        raw_email = self._text(data, "guest_email").strip().lower()
        if auth is not None:
            email, problems = auth._guest_email(raw_email)
            if problems:
                raise DomainError(next(iter(problems.values())), 400, fields=problems)
        else:
            email = raw_email
            if "@" not in email or email.startswith("@") or email.endswith("@"):
                raise DomainError("Enter the guest’s personal email.", field="guest_email")
        values = self._lost_details(data)
        with self._tx() as conn:
            values["photo_id"] = self._photo(conn, staff, data.get("photo_id"), "report_photo")
            row = conn.execute("SELECT * FROM users WHERE lower(email)=?", (email,)).fetchone()
            if row is not None:
                if row["role"] != "guest":
                    raise DomainError("That email already has an account. A desk report can only be saved for a Guest account.", field="guest_email")
                owner = User.from_row(row)
                if owner.blocked or not owner.active:
                    raise DomainError("That guest account cannot take a new report.", field="guest_email")
                result = self._save_guest_lost(conn, staff, owner, values)
                immediate_result = result
            else:
                immediate_result = None
            if immediate_result is None:
                if auth is None:
                    raise DomainError("No guest account uses that email. Ask them to sign up as Guest first, then file this report.", field="guest_email")
                conn.execute("UPDATE desk_holds SET status='dropped' WHERE lower(guest_email)=? AND status='waiting'", (email,))
                cursor = conn.execute(
                    "INSERT INTO desk_holds(staff_id,guest_email,category,description,color,brand,place,date_lost,time_lost,identifying_marks,photo_id) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                    (staff.id, email, values["category"], values["description"], values["color"], values["brand"],
                     values["place"], values["date_lost"], values["time_lost"], values["identifying_marks"], values["photo_id"]))
                hold_id = cursor.lastrowid
                AuditLog(conn).record(staff, "DESK_REPORT_HELD", f"Holding a lost report for {email} until they finish Guest sign-up")
        if immediate_result is not None:
            self._run_matching_unlocked()
            return immediate_result
        code_sent = True
        try:
            auth.register(email, ip)
        except DomainError as error:
            if error.status == 429 and "before asking for another code" in str(error):
                code_sent = False
            elif "already exists" in str(error):
                self._drop_hold(hold_id)
                return self.create_lost_report_for_guest(staff, data, auth, ip)
            else:
                self._drop_hold(hold_id)
                raise
        return {"status": "waiting", "hold_id": hold_id, "email": email, "code_sent": code_sent}

    def _drop_hold(self, hold_id):
        with self._tx() as conn:
            conn.execute("UPDATE desk_holds SET status='dropped' WHERE id=? AND status='waiting'", (hold_id,))

    def claim_desk_holds(self, user):
        """Attach waiting desk reports once the visitor has a real Guest account. Sign-up still succeeds if this cannot."""
        if getattr(user, "role", None) != "guest" or not getattr(user, "email", None):
            return 0
        try:
            with self._tx() as conn:
                holds = conn.execute(
                    "SELECT * FROM desk_holds WHERE lower(guest_email)=? AND status='waiting' ORDER BY id",
                    (user.email.strip().lower(),)).fetchall()
                saved = 0
                for hold in holds:
                    staff_row = conn.execute("SELECT * FROM users WHERE id=?", (hold["staff_id"],)).fetchone()
                    if staff_row is None:
                        conn.execute("UPDATE desk_holds SET status='dropped' WHERE id=?", (hold["id"],))
                        continue
                    staff = User.from_row(staff_row)
                    values = {key: hold[key] for key in ("category", "description", "color", "brand", "place", "date_lost", "time_lost", "identifying_marks")}
                    try:
                        values["photo_id"] = self._photo(conn, staff, hold["photo_id"], "report_photo")
                    except DomainError:
                        values["photo_id"] = None
                    try:
                        result = self._save_guest_lost(conn, staff, user, values)
                    except DomainError:
                        continue
                    conn.execute("UPDATE desk_holds SET status='saved', report_id=? WHERE id=?", (result["id"], hold["id"]))
                    saved += 1
            if saved:
                self._run_matching_unlocked()
            return saved
        except Exception:
            return 0

    def desk_hold_status(self, staff, hold_id):
        staff = self._guard(staff, "moderate")
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM desk_holds WHERE id=?", (int(hold_id),)).fetchone()
        if row is None or row["staff_id"] != staff.id:
            raise DomainError("That desk report is not open.", 404)
        if row["status"] == "waiting":
            with self.db.connect() as conn:
                person = conn.execute("SELECT * FROM users WHERE lower(email)=?", (row["guest_email"].strip().lower(),)).fetchone()
            if person and person["role"] == "guest" and person["email_verified"] and person["active"] and not person["blocked"]:
                self.claim_desk_holds(User.from_row(person))
                with self.db.connect() as conn:
                    row = conn.execute("SELECT * FROM desk_holds WHERE id=?", (row["id"],)).fetchone()
        return {"status": row["status"], "email": row["guest_email"], "report_id": row["report_id"]}

    def create_found_report(self, user, data):
        user = self._guard(user, "report_found")
        values = {key: self._text(data, key) for key in ("category", "description", "place")}
        values["color"] = self._text(data, "color", required=False, maximum=40)
        values["brand"] = self._brand(data)
        values["category"] = self._category(values["category"])
        values["date_found"] = self._date(data, "date_found")
        values["time_found"] = self._time(data, "time_found")
        values["where_now"] = self._text(data, "where_now", required=False, maximum=20) or "with_me"
        if values["where_now"] not in FOUND_NOW:
            raise DomainError("Say where the item is now.")
        if values["where_now"] == "with_me":
            values["turn_in_deadline"] = self._date(data, "turn_in_deadline", future=True)
            if values["turn_in_deadline"] < values["date_found"]:
                raise DomainError("The turn-in day cannot be earlier than the day it was found.")
        else:
            values["turn_in_deadline"] = values["date_found"]
        with self._tx() as conn:
            saved, receipt = self._report_receipt(conn, user, 'found', data)
            if saved is not None:
                return saved
            self._daily_cap(conn, user, "found")
            values["photo_id"] = self._photo(conn, user, data.get("photo_id"), "report_photo")
            keys = list(values)
            cursor = conn.execute(f"INSERT INTO found_reports(finder_id,{','.join(keys)}) VALUES({','.join('?' for _ in range(len(keys)+1))})",
                                  (user.id, *[values[k] for k in keys]))
            result = self._row(conn, "found_reports", cursor.lastrowid)
            AuditLog(conn).record(user, "FOUND_REPORT_CREATED", f"Report {result['id']}; awaiting physical turn-in")
            self._save_report_receipt(conn, user, 'found', result['id'], receipt)
        return result

    def review_report(self, admin, data):
        """Mark a guest's report as checked, hide a spam report (kept in the database), or show it again."""
        admin = self._guard(admin, "moderate")
        kind, action = str(data.get("kind", "")), str(data.get("action", ""))
        if kind not in ("lost", "found") or action not in ("checked", "hide", "unhide"):
            raise DomainError("Choose a report and an action.")
        if action == "checked" and kind != "lost":
            raise DomainError("Only lost reports need a check.")
        table = "lost_reports" if kind == "lost" else "found_reports"
        reason = self._text(data, "reason", required=action == "hide", maximum=500)
        with self._tx() as conn:
            row = self._row(conn, table, data.get("id"))
            if action == "checked":
                conn.execute("UPDATE lost_reports SET flagged=0 WHERE id=?", (row["id"],))
                self._notify(conn, row["owner_id"], "CSA checked your lost report. Matching can start.", row["id"])
            else:
                conn.execute(f"UPDATE {table} SET hidden=? WHERE id=?", (int(action == "hide"), row["id"]))
                if action == "hide" and kind == "lost":
                    conn.execute("DELETE FROM matches WHERE report_id=? AND status='suggested'", (row["id"],))
            names = {"checked": "REPORT_CHECKED", "hide": "REPORT_HIDDEN", "unhide": "REPORT_RESTORED"}
            AuditLog(conn).record(admin, names[action], f"{kind.title()} report {row['id']}; {reason or 'no note'}")
            updated = self._row(conn, table, row["id"])
        if action == "unhide" and kind == "lost":
            self._run_matching_unlocked(admin)
        return updated
