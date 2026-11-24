"""Profiles, passwords, staff accounts, and the school roster."""
import re

from lyfind.language import too_long
from lyfind.passwords import first_problem
from lyfind.users import DomainError, User, check_password, hash_password, join_display_name, split_display_name

from .base import AuditLog, WorkflowBase


class AccountService(WorkflowBase):
    """Profiles, passwords, staff accounts, and the school roster."""

    def manage_staff(self, admin, data):
        admin = self._guard(admin, "manage_staff")
        action = data.get("action", "create")
        with self._tx() as conn:
            if action == "create":
                if data.get("role", "admin") != "admin":
                    raise DomainError("New staff accounts are CSA administrators.")
                name = self._text(data, "name", maximum=120)
                email = self._text(data, "email", maximum=254).casefold()
                if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
                    raise DomainError("Enter a valid staff email address.")
                weak = first_problem(str(data.get("password", "")), name, email)
                if weak:
                    raise DomainError(weak, field="password")
                password = hash_password(str(data.get("password", "")))
                first, middle, last, suffix = split_display_name(name)
                cursor = conn.execute(
                    "INSERT INTO users(first_name,middle_name,last_name,suffix,email,role,password_hash) VALUES(?,?,?,?,?,'admin',?)",
                    (first, middle, last, suffix, email, password))
                result = self._row(conn, "users", cursor.lastrowid)
                AuditLog(conn).record(admin, "STAFF_CREATED", f"Administrator {cursor.lastrowid}")
            elif action == "update":
                staff = self._row(conn, "users", data.get("user_id"))
                if staff["role"] != "admin":
                    raise DomainError("Use a new email. Student and guest accounts cannot be turned into staff here.")
                active_value = data.get("active", bool(staff["active"]))
                if not isinstance(active_value, bool):
                    raise DomainError("Choose active or inactive.")
                active = active_value
                if not active and conn.execute("SELECT COUNT(*) FROM users WHERE role='admin' AND active=1 AND blocked=0").fetchone()[0] <= 1:
                    raise DomainError("Keep at least one active CSA administrator.")
                if data.get("role", "admin") != "admin":
                    raise DomainError("Staff stay staff. Create a separate student or guest account instead.")
                name = self._text(data, "name", required=False, maximum=120) or staff["name"]
                email = self._text(data, "email", required=False, maximum=254).casefold() or staff["email"]
                if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
                    raise DomainError("Enter a valid staff email address.")
                if data.get("password"):
                    weak = first_problem(str(data["password"]), name, email)
                    if weak:
                        raise DomainError(weak, field="password")
                if name == staff["name"]:
                    first, middle, last, suffix = (staff[key] for key in ("first_name", "middle_name", "last_name", "suffix"))
                else:
                    first, middle, last, suffix = split_display_name(name)
                conn.execute(
                    "UPDATE users SET active=?,first_name=?,middle_name=?,last_name=?,suffix=?,email=? WHERE id=?",
                    (int(active), first, middle, last, suffix, email, staff["id"]))
                if data.get("password"):
                    conn.execute("UPDATE users SET password_hash=? WHERE id=?", (hash_password(str(data["password"])), staff["id"]))
                result = self._row(conn, "users", staff["id"])
                AuditLog(conn).record(admin, "STAFF_UPDATED", f"Administrator {staff['id']}; active={active}")
            else:
                raise DomainError("Choose add or update for this staff account.")
            result.pop("password_hash", None)
            return result

    def set_blocked(self, admin, user_id, blocked, reason=""):
        """Block or unblock a student, professor or guest. Staff accounts are managed on the Staff tab."""
        admin = self._guard(admin, "moderate")
        if not isinstance(blocked, bool):
            raise DomainError("Choose block or unblock.")
        reason = str(reason or "").strip()
        if blocked and not reason:
            raise DomainError("Add a short reason so other staff know why.")
        if len(reason) > 500:
            raise DomainError(too_long("reason", 500))
        with self._tx() as conn:
            person = self._row(conn, "users", user_id)
            if person["role"] == "admin":
                raise DomainError("Staff accounts cannot be blocked here. Use the Staff tab.", 403)
            conn.execute("UPDATE users SET blocked=? WHERE id=?", (int(blocked), person["id"]))
            if blocked:
                conn.execute("DELETE FROM sessions WHERE user_id=?", (person["id"],))
            AuditLog(conn).record(admin, "USER_BLOCKED" if blocked else "USER_UNBLOCKED", f"Account {person['id']} ({person['role']}); {reason or 'no note'}")
            person.pop("password_hash", None)
            return {**person, "blocked": int(blocked)}

    def set_person_password(self, admin, data):
        """An administrator sets a new password after checking a valid ID. Nothing is emailed, and the password is not written to the log."""
        admin = self._guard(admin, "moderate")
        new = str(data.get("password") or "")
        confirm = str(data.get("confirm") or "")
        with self._tx() as conn:
            person = self._row(conn, "users", data.get("user_id"))
            if person["role"] not in ("student", "professor", "guest"):
                raise DomainError("Set a staff password from Administration, then Staff.")
            weak = first_problem(new, person["name"] or "", person["email"] or "")
            if weak:
                raise DomainError(weak, field="password")
            if confirm != new:
                raise DomainError("The two passwords are not the same.", field="confirm")
            conn.execute("UPDATE users SET password_hash=? WHERE id=?", (hash_password(new), person["id"]))
            conn.execute("DELETE FROM sessions WHERE user_id=?", (person["id"],))
            AuditLog(conn).record(admin, "PASSWORD_SET", f"Password set for account {person['id']} ({person['role']}) after an ID check")
        return {"ok": True}

    def _phone(self, value):
        phone = self._text({"phone": value}, "phone", required=False, maximum=20)
        if not phone:
            return ""
        if not re.fullmatch(r"\+?[\d\s\-().]+", phone):
            raise DomainError("Use numbers only in the phone field.", 400, field="phone")
        digits = re.sub(r"\D", "", phone)
        if not 10 <= len(digits) <= 15:
            raise DomainError("Enter a phone number with 10 to 15 digits, like 0917 123 4567.", 400, field="phone")
        return phone

    def _name_part(self, data, field, required=False, maximum=40):
        value = self._text(data, field, required=required, maximum=maximum)
        if required and len(value) < 2:
            raise DomainError("Enter at least two letters.", 400, field=field)
        return value

    def update_profile(self, user, data):
        """The signed-in person can change their name parts, phone, and ID / student number."""
        user = self._guard(user, "view_own")
        first = self._name_part(data, "first_name", required=True)
        middle = self._name_part(data, "middle_name")
        last = self._name_part(data, "last_name", required=True)
        suffix = self._name_part(data, "suffix", maximum=12)
        name = join_display_name(first, middle, last, suffix)
        phone = self._phone(data.get("phone", ""))
        parsed = self._derived_number(user.email, user.role)
        number = parsed or self._text(data, "student_number", required=False, maximum=40)
        with self._tx() as conn:
            conn.execute("UPDATE users SET first_name=?, middle_name=?, last_name=?, suffix=?, phone=?, student_number=? WHERE id=?",
                         (first, middle, last, suffix, phone, number, user.id))
            AuditLog(conn).record(user, "PROFILE_UPDATED", "Name, phone, or number changed")
            row = conn.execute("SELECT * FROM users WHERE id=?", (user.id,)).fetchone()
        return User.from_row(row)

    def change_password(self, user, data):
        """A signed-in person sets a new password with the same rules as sign-up. No email is sent."""
        user = self._guard(user, "view_own")
        current = str(data.get("current_password") or "")
        new = str(data.get("password") or "")
        confirm = str(data.get("confirm") or "")
        if not current:
            raise DomainError("Enter your current password.", field="current_password")
        with self._tx() as conn:
            row = conn.execute("SELECT * FROM users WHERE id=?", (user.id,)).fetchone()
            if not row or not row["password_hash"] or not check_password(current, row["password_hash"]):
                raise DomainError("That current password is not right.", field="current_password")
            weak = first_problem(new, row["name"] or "", row["email"] or "")
            if weak:
                raise DomainError(weak, field="password")
            if confirm != new:
                raise DomainError("The two passwords are not the same.", field="confirm")
            conn.execute("UPDATE users SET password_hash=? WHERE id=?", (hash_password(new), user.id))
            AuditLog(conn).record(user, "PASSWORD_CHANGED", "Password changed")
        return {"ok": True}

    @staticmethod
    def _derived_number(email, role):
        """2000-9-99999 for 2000-9-99999@lpunetwork.edu.ph, so staff see the student number without typing it."""
        from lyfind.auth import student_number
        return student_number(email) if role == "student" else ""

    @staticmethod
    def _roster_email(value):
        email = str(value or "").strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) or len(email) > 254:
            raise DomainError("Enter a valid school email address.", field="email")
        return email

    def roster_save(self, admin, data):
        """Add, switch on or off, or remove a school email on the allowed list."""
        admin = self._guard(admin, "manage_roster")
        action = str(data.get("action", "add"))
        with self._tx() as conn:
            if action == "add":
                email = self._roster_email(data.get("email"))
                role = str(data.get("role", "student") or "student")
                if role not in ("student", "professor"):
                    raise DomainError("Choose student or professor.", field="role")
                name = self._text(data, "name", required=False, maximum=120)
                number = self._text(data, "student_number", required=False, maximum=40) or self._derived_number(email, role)
                conn.execute("INSERT INTO roster(email,name,student_number,role) VALUES(?,?,?,?) "
                             "ON CONFLICT(email) DO UPDATE SET name=excluded.name,student_number=excluded.student_number,role=excluded.role,active=1",
                             (email, name, number, role))
                AuditLog(conn).record(admin, "ROSTER_ADDED", f"{email} as {role}")
            else:
                row = self._row(conn, "roster", data.get("id"))
                if action == "toggle":
                    active = not row["active"]
                    conn.execute("UPDATE roster SET active=? WHERE id=?", (int(active), row["id"]))
                    AuditLog(conn).record(admin, "ROSTER_ON" if active else "ROSTER_OFF", row["email"])
                elif action == "remove":
                    conn.execute("DELETE FROM roster WHERE id=?", (row["id"],))
                    AuditLog(conn).record(admin, "ROSTER_REMOVED", row["email"])
                else:
                    raise DomainError("Choose add, switch off or remove.")
            return {"roster": [dict(r) for r in conn.execute("SELECT * FROM roster ORDER BY email")]}

    def roster_import(self, admin, text, *, preview_only=False, expected=None):
        """Preview a roster and atomically import the reviewed rows."""
        import csv
        import hashlib
        import io
        import json
        admin = self._guard(admin, "manage_roster")
        text = str(text or "")
        if len(text) > 200_000:
            raise DomainError("Import a CSV smaller than 200 KB.", 413)
        reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
        names = {(h or "").strip().lower().replace(" ", "_"): h for h in (reader.fieldnames or [])}
        if "email" not in names:
            raise DomainError("The CSV header must include email.")
        entries, seen = [], set()
        try:
            for number, row in enumerate(reader, start=2):
                if number > 501:
                    raise DomainError("Import up to 500 accounts at a time.", 413)
                entry = {key: str(row.get(names.get(key, ""), "") or "").strip()
                         for key in ("email", "name", "student_number", "role")}
                entry.update(line=number, issue="")
                try:
                    entry['email'] = self._roster_email(entry['email'])
                    if entry['email'].rsplit('@',1)[-1] != 'lpunetwork.edu.ph':
                        raise DomainError('Use an @lpunetwork.edu.ph school email.')
                    entry['role'] = (entry['role'] or 'student').lower()
                    if entry['role'] not in ('student','professor'):
                        raise DomainError('Choose student or professor.')
                    if entry['email'] in seen:
                        raise DomainError('This email is repeated in the file.')
                    seen.add(entry['email'])
                    if len(entry['name'])>120 or len(entry['student_number'])>40:
                        raise DomainError('The name or student number is too long.')
                    entry['student_number'] = entry['student_number'] or self._derived_number(entry['email'],entry['role'])
                except DomainError as error:
                    entry['issue'] = str(error)
                entries.append(entry)
        except csv.Error as error:
            raise DomainError('Check the CSV formatting.') from error
        if not entries:
            raise DomainError('Add account rows below the header.')
        with self._tx() as conn:
            previous = [dict(row) for row in conn.execute('SELECT * FROM roster ORDER BY email')]
            for entry in entries:
                entry['status'] = 'invalid' if entry['issue'] else ('update' if any(row['email']==entry['email'] for row in previous) else 'new')
            token = hashlib.sha256(json.dumps([entries,previous],sort_keys=True).encode()).hexdigest()
            if preview_only:
                return dict(rows=entries, preview=token, invalid=sum(bool(row['issue']) for row in entries))
            if expected is not None and expected != token:
                raise DomainError('The roster changed. Preview the CSV again.',409)
            if expected is not None and any(row['issue'] for row in entries):
                raise DomainError('Fix the invalid rows before importing.')
            added, skipped = 0, []
            for row in entries:
                if row['issue']:
                    skipped.append(f"Row {row['line']}: {row['issue']}")
                    continue
                conn.execute("INSERT INTO roster(email,name,student_number,role) VALUES(?,?,?,?) "
                             "ON CONFLICT(email) DO UPDATE SET name=excluded.name,student_number=excluded.student_number,role=excluded.role,active=1",
                             (row['email'],row['name'],row['student_number'],row['role']))
                added += 1
            AuditLog(conn).record(admin,'ROSTER_IMPORTED',f'{added} added or updated, {len(skipped)} skipped')
            return dict(added=added,skipped=skipped[:20],skipped_count=len(skipped),
                        roster=[dict(row) for row in conn.execute('SELECT * FROM roster ORDER BY email')])
