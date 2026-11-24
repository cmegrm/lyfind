"""Persistent sessions, one-time email codes, staff and Microsoft identity."""
import csv
import hashlib
import hmac
import io
import json
import os
import re
import secrets
import smtplib
import ssl
import time

from configuration import smtp_missing_settings, smtp_password
from domain import DomainError
from email_templates import code_email
from users import QUICK_GUEST_EMAIL_SUFFIX, User, hash_password, check_password, require_permission


# Fixed, valid hash format gives unknown accounts the same password-check cost.
_DUMMY_PASSWORD_HASH = 'pbkdf2_sha256$310000$reunite-dummy-salt$' + '0' * 64
_SETUP_CODE_LIFETIME = 24 * 60 * 60
_EMAIL_RESEND_DELAY = 60
_MAIL_ERRORS = (OSError, smtplib.SMTPException, ValueError, KeyError)
SESSION_LIFETIME = 8 * 60 * 60
REMEMBERED_GUEST_LIFETIME = 30 * 24 * 60 * 60
_LPU_ROLES = ('student', 'professor')
LPU_EMAIL_DOMAIN = 'lpunetwork.edu.ph'


def _admin_exists(conn):
    return conn.execute("SELECT 1 FROM users WHERE role='admin' AND email NOT LIKE '%@example.test' LIMIT 1").fetchone() is not None


def load_environment(path):
    """Load local .env without overriding the process environment."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


class AuthService:
    def __init__(self, db, demo_mode=True):
        self.db, self.demo_mode = db, demo_mode
        self.tenant = os.environ.get("MICROSOFT_TENANT_ID", "")
        self.client_id = os.environ.get("MICROSOFT_CLIENT_ID", "")
        self.client_secret = os.environ.get("MICROSOFT_CLIENT_SECRET", "")
        self.redirect = os.environ.get("MICROSOFT_REDIRECT_URI", "http://127.0.0.1:8765/auth/microsoft/callback")
        self.domains = {v.strip().lower() for v in os.environ.get("UNIVERSITY_EMAIL_DOMAINS", "").split(",") if v.strip()}
        self.smtp_enabled = not demo_mode and not smtp_missing_settings()
        self.msal_app = None
        if not demo_mode and self.tenant and self.client_id and self.client_secret:
            if not re.fullmatch(r"[0-9a-fA-F-]{36}", self.tenant):
                raise ValueError("MICROSOFT_TENANT_ID must be your university tenant UUID.")
            try:
                import msal
            except ImportError:
                raise RuntimeError("Install requirements-live.txt to enable Microsoft sign-in.") from None
            self.msal_app = msal.ConfidentialClientApplication(
                self.client_id, authority=f"https://login.microsoftonline.com/{self.tenant}",
                client_credential=self.client_secret,
            )
        with db.connect() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
              token_hash TEXT PRIMARY KEY, user_id INTEGER REFERENCES users(id),
              csrf TEXT NOT NULL, expires REAL NOT NULL, oauth_flow TEXT);
            CREATE TABLE IF NOT EXISTS login_codes (
              email TEXT PRIMARY KEY, code_hash TEXT NOT NULL, expires REAL NOT NULL,
              attempts INTEGER NOT NULL DEFAULT 0, requested REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS login_limits (
              identity TEXT PRIMARY KEY, failures INTEGER NOT NULL DEFAULT 0,
              locked_until REAL NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS local_accounts (
              user_id INTEGER PRIMARY KEY REFERENCES users(id),
              code_hash TEXT, code_expires REAL);
            """)
            if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='local_student_accounts'").fetchone():
                conn.execute("INSERT OR IGNORE INTO local_accounts SELECT * FROM local_student_accounts")

    def has_admin(self):
        with self.db.connect() as conn:
            return _admin_exists(conn)

    def setup_first_admin(self, data):
        email = self._account_email(data.get('email'))
        name = self._account_name(data.get('name'))
        password = self._confirmed_password(data.get('password'), data.get('confirmation'))
        with self.db.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            if _admin_exists(conn):
                raise DomainError('The first CSA administrator has already been set up.', 409)
            if conn.execute('SELECT 1 FROM users WHERE email=?', (email,)).fetchone():
                raise DomainError('Choose a separate email address for the CSA account.', 409)
            admin_id = conn.execute("INSERT INTO users(name,email,role,password_hash) VALUES(?,?,'admin',?)",
                                    (name, email, hash_password(password))).lastrowid
            self._audit(conn, admin_id, 'FIRST_ADMIN_CREATED', 'Local launcher setup completed')
        return self.get_user(admin_id)

    @property
    def microsoft_enabled(self):
        return self.msal_app is not None

    @staticmethod
    def digest(value):
        return hashlib.sha256(value.encode()).hexdigest()

    def session(self, token):
        with self.db.connect() as conn:
            conn.execute("DELETE FROM sessions WHERE expires < ?", (time.time(),))
            row = conn.execute("SELECT * FROM sessions WHERE token_hash=?", (self.digest(token or ""),)).fetchone()
            if row:
                return dict(row), None
            raw = secrets.token_urlsafe(32)
            record = {"token_hash": self.digest(raw), "csrf": secrets.token_urlsafe(32),
                      "user_id": None, "expires": time.time() + SESSION_LIFETIME, "oauth_flow": None}
            conn.execute("INSERT INTO sessions(token_hash,csrf,expires) VALUES(?,?,?)",
                         (record["token_hash"], record["csrf"], record["expires"]))
            return record, raw

    def current_user(self, session):
        if not session.get("user_id"):
            return None
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()
            if row and row["active"] and not row["blocked"]:
                if not self.demo_mode and row["email"].endswith("@example.test"):
                    return None
                if not self.demo_mode and row["role"] in _LPU_ROLES and row["email"].lower().rsplit('@', 1)[-1] != LPU_EMAIL_DOMAIN:
                    return None
                return User.from_row(row)
        return None

    def sign_in(self, session, user, *, lifetime=SESSION_LIFETIME):
        with self.db.connect() as conn:
            return self._start_session(conn, session, user, lifetime=lifetime)

    def _start_session(self, conn, session, user, lifetime=SESSION_LIFETIME):
        raw, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        expires = time.time() + lifetime
        conn.execute("DELETE FROM sessions WHERE token_hash=?", (session["token_hash"],))
        conn.execute("INSERT INTO sessions(token_hash,user_id,csrf,expires) VALUES(?,?,?,?)",
                     (self.digest(raw), user.id, csrf, expires))
        self._audit(conn, user.id, "SIGNED_IN", f"Role {user.role}")
        session.update(token_hash=self.digest(raw), csrf=csrf, user_id=user.id, expires=expires)
        return raw

    def guest_email(self, email):
        email = email.strip().lower() if isinstance(email, str) else ''
        if (not email.isprintable() or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) or len(email) > 254
                or email.endswith(QUICK_GUEST_EMAIL_SUFFIX)
                or (not self.demo_mode and email.endswith('@example.test'))):
            raise DomainError('Enter a valid personal email address.')
        domain = email.rsplit('@', 1)[1]
        if domain == LPU_EMAIL_DOMAIN or domain in self.domains or domain == 'lpu.edu.ph' or domain.endswith('.lpu.edu.ph'):
            raise DomainError('Use the LPU or CSA sign-in option for university email addresses.')
        return email

    @staticmethod
    def _guard_guest_email(conn, email):
        account = conn.execute("SELECT role FROM users WHERE email=?", (email,)).fetchone()
        if account and account['role'] != 'guest':
            raise DomainError('Use the LPU or CSA sign-in option for university accounts.')

    def logout(self, session):
        with self.db.connect() as conn:
            conn.execute("DELETE FROM sessions WHERE token_hash=?", (session["token_hash"],))
            if session.get("user_id"):
                self._audit(conn, session["user_id"], "SIGNED_OUT", "Session ended")

    def _audit(self, conn, actor, action, detail):
        # Auth records use the same append-only log as workflow records.
        columns = {r[1] for r in conn.execute("PRAGMA table_info(audit_logs)")}
        if "actor_id" in columns:
            conn.execute("INSERT INTO audit_logs(actor_id,action,detail) VALUES(?,?,?)", (actor, action, detail))

    @staticmethod
    def _limit_email_requests(conn, source, now):
        if not source:
            return
        key = 'email-code:' + source
        row = conn.execute("SELECT failures,locked_until FROM login_limits WHERE identity=?", (key,)).fetchone()
        if row and row["locked_until"] > now:
            if row["failures"] >= 12:
                raise DomainError("Too many code requests. Try again in 15 minutes.", 429)
            conn.execute("UPDATE login_limits SET failures=failures+1 WHERE identity=?", (key,))
        else:
            conn.execute("INSERT OR REPLACE INTO login_limits VALUES(?,1,?)", (key, now + 900))

    def request_code(self, email, source=None):
        email = self.guest_email(email)
        code = f"{secrets.randbelow(1000000):06d}"
        code_hash = self.digest(email + ':' + code)
        now = time.time()
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute("SELECT requested FROM login_codes WHERE email=?", (email,)).fetchone()
            if existing and now - existing[0] < _EMAIL_RESEND_DELAY:
                raise DomainError("Please wait a minute before requesting another code.", 429)
            self._guard_guest_email(conn, email)
            if not self.demo_mode and not self.smtp_enabled:
                raise DomainError("Guest email delivery is unavailable. Contact CSA for help signing in.", 503)
            if not self.demo_mode:
                self._limit_email_requests(conn, source, now)
            conn.execute("INSERT OR REPLACE INTO login_codes VALUES(?,?,?,?,?)",
                         (email, code_hash, now + 300, 0, now))
        if self.smtp_enabled:
            try:
                self._send_email(email, code)
            except _MAIL_ERRORS:
                with self.db.connect() as conn:
                    conn.execute("DELETE FROM login_codes WHERE email=? AND code_hash=?", (email, code_hash))
                raise DomainError("The email could not be delivered. Please try again later.", 503) from None
        result = {"email": email, "expires_in": 300}
        if self.demo_mode:
            result["demo_code"] = code
        return result

    def _send_email(self, email, code):
        self._deliver_email(code_email(
            email, code, subject="Your LyFind guest sign-in code", heading="Sign in as a guest",
            intro="Your one-time code is ready.",
            instructions="Enter this code on the LyFind Guest sign-in screen.",
            expiry="5 minutes",
            security_note="Keep this code private. If you didn’t request it, you can ignore this email.",
        ))

    def _send_account_setup_email(self, email, code, *, reset):
        purpose = 'password reset' if reset else 'account setup'
        heading = "Reset your LPU password" if reset else "Set up your LPU account"
        self._deliver_email(code_email(
            email, code, subject=f"Your LyFind {purpose} code", heading=heading,
            intro=f"Your one-time {purpose} code is ready.",
            instructions="In LyFind, choose LPU, then Set up or reset your password. Enter your school email and this code.",
            expiry="24 hours",
            security_note="Keep this code private. If you didn’t request it, contact CSA.",
        ))

    @staticmethod
    def _deliver_email(message):
        host, port = os.environ["SMTP_HOST"], int(os.environ.get("SMTP_PORT", "587"))
        username, password = os.environ.get("SMTP_USER"), smtp_password()
        if host.casefold() == "smtp.gmail.com":
            password = "".join(password.split())
        use_ssl = os.environ.get("SMTP_SSL", "0") == "1"
        message["From"] = os.environ["SMTP_FROM"]
        context = ssl.create_default_context()
        if use_ssl:
            client = smtplib.SMTP_SSL(host, port, timeout=15, context=context)
        else:
            client = smtplib.SMTP(host, port, timeout=15)
        with client:
            if not use_ssl:
                client.starttls(context=context)
            if username:
                client.login(username, password)
            client.send_message(message)

    def verify_code(self, email, code):
        try:
            email = self.guest_email(email)
        except DomainError as error:
            raise DomainError(str(error), 401) from None
        code = str(code).strip()
        error, user_id = None, None
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM login_codes WHERE email=?", (email,)).fetchone()
            if not row or row["expires"] < time.time() or row["attempts"] >= 5:
                error = "The code has expired or is unavailable. Request a new code."
            elif not hmac.compare_digest(row["code_hash"], self.digest(email + ':' + code)):
                conn.execute("UPDATE login_codes SET attempts=attempts+1 WHERE email=?", (email,))
                error = "Incorrect code. You have at most five attempts."
            else:
                existing = conn.execute("SELECT * FROM users WHERE lower(email)=?", (email,)).fetchone()
                if existing and (existing["role"] != "guest" or not existing["active"] or existing["blocked"]):
                    error = "This account cannot use guest sign-in."
                else:
                    if not existing:
                        cur = conn.execute("INSERT INTO users(name,email,role,password_hash) VALUES(?,?,?,?)",
                                           (email.split('@')[0], email, "guest", ""))
                        user_id = cur.lastrowid
                    else:
                        user_id = existing["id"]
                    conn.execute("DELETE FROM login_codes WHERE email=?", (email,))
        if error:
            raise DomainError(error, 401)
        return self.get_user(user_id)

    def get_user(self, user_id):
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
            return User.from_row(row)

    def _require_live_accounts(self):
        if self.demo_mode:
            raise DomainError("CSA-issued accounts are available in live mode.", 404)

    @staticmethod
    def _account_email(value):
        email = str(value).strip().lower()
        if (not email.isprintable() or len(email) > 254 or email.endswith(('@example.test', QUICK_GUEST_EMAIL_SUFFIX))
                or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email)):
            raise DomainError("Enter a valid email address.")
        return email

    def _lpu_email(self, value):
        email = self._account_email(value)
        if email.rsplit('@', 1)[1] != LPU_EMAIL_DOMAIN:
            raise DomainError(f"Use your @{LPU_EMAIL_DOMAIN} school email.")
        return email

    @staticmethod
    def _account_name(value):
        name = value.strip() if isinstance(value, str) else ''
        if not 1 <= len(name) <= 120:
            raise DomainError('Enter a full name (up to 120 characters).')
        return name

    @staticmethod
    def _confirmed_password(password, confirmation):
        if not isinstance(password, str) or not 15 <= len(password) <= 128:
            raise DomainError('Use a password between 15 and 128 characters.')
        if password != confirmation:
            raise DomainError('The passwords do not match.')
        return password

    @staticmethod
    def _confirmed_lpu_password(password, confirmation):
        if not isinstance(password, str) or not 8 <= len(password) <= 128:
            raise DomainError('Use 8 to 128 characters for your LPU password.')
        if password != password.strip() or not password.isprintable():
            raise DomainError('Use printable characters with no spaces at the start or end.')
        if not (any(c.isupper() for c in password) and any(c.islower() for c in password)
                and any(c.isdigit() for c in password)
                and any(not c.isalnum() and not c.isspace() for c in password)):
            raise DomainError('Include an uppercase letter, a lowercase letter, a number, and a symbol.')
        if password != confirmation:
            raise DomainError('The passwords do not match.')
        return password

    def issue_account_code(self, admin, email, name=None, *, reset=False, role='student'):
        self._require_live_accounts()
        require_permission(admin, "manage_staff")
        email = self._lpu_email(email)
        if not reset:
            if role not in _LPU_ROLES:
                raise DomainError('Choose Student or Professor.')
            name = self._account_name(name)
        code = secrets.token_urlsafe(24)
        code_hash = self.digest(code)
        expires = time.time() + _SETUP_CODE_LIFETIME
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            actor = conn.execute("SELECT * FROM users WHERE id=?", (admin.id,)).fetchone()
            require_permission(User.from_row(actor) if actor else None, "manage_staff")
            existing = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
            if reset:
                if (not existing or existing['role'] not in _LPU_ROLES or not existing['active'] or existing['blocked']
                        or not conn.execute("SELECT 1 FROM local_accounts WHERE user_id=?", (existing['id'],)).fetchone()):
                    raise DomainError("No active CSA-issued account uses this email.", 404)
                user_id = existing['id']
                role = existing['role']
            else:
                if existing:
                    raise DomainError("This email already has an account. Check its sign-in method or issue a replacement code.", 409)
                user_id = conn.execute("INSERT INTO users(name,email,role) VALUES(?,?,?)", (name, email, role)).lastrowid
            conn.execute("""INSERT INTO local_accounts(user_id,code_hash,code_expires) VALUES(?,?,?)
                         ON CONFLICT(user_id) DO UPDATE SET code_hash=excluded.code_hash,code_expires=excluded.code_expires""",
                         (user_id, code_hash, expires))
            self._audit(conn, admin.id, 'ACCOUNT_CODE_ISSUED', f'{role} account {user_id}; ' + ('replacement' if reset else 'new account'))
        if self.smtp_enabled:
            try:
                self._send_account_setup_email(email, code, reset=reset)
            except _MAIL_ERRORS:
                with self.db.connect() as conn:
                    conn.execute('UPDATE local_accounts SET code_hash=NULL,code_expires=NULL WHERE user_id=? AND code_hash=?',
                                 (user_id, code_hash))
                    self._audit(conn, admin.id, 'ACCOUNT_CODE_EMAIL_FAILED', f'{role} account {user_id}')
                raise DomainError('The account is saved, but the code email could not be sent. Check email delivery, then issue a replacement code.', 503) from None
            return {"email": email, "role": role, "delivery": "email"}
        return {"email": email, "code": code, "role": role, "delivery": "manual"}

    def import_accounts(self, admin, content, preview=None):
        """Preview a CSV, or create the reviewed accounts in one transaction."""
        self._require_live_accounts()
        require_permission(admin, 'manage_staff')
        if not isinstance(content, str) or not content.strip() or len(content) > 200_000:
            raise DomainError('Choose a UTF-8 CSV file smaller than 200 KB.')
        reader = csv.reader(io.StringIO(content.lstrip('\ufeff'), newline=''), strict=True)
        entries, seen = [], set()
        try:
            columns = [value.strip().lower() for value in next(reader, [])]
            if len(columns) != 3 or set(columns) != {'name', 'email', 'role'}:
                raise DomainError('Use three CSV columns: name, email, role.')
            for values in reader:
                if not any(value.strip() for value in values):
                    continue
                if len(entries) == 500:
                    raise DomainError('Import up to 500 accounts at a time.')
                line = reader.line_num
                if len(values) != 3:
                    entries.append({'line': line, 'status': 'invalid', 'issue': 'Expected three columns.'})
                    continue
                row = {key: value.strip() for key, value in zip(columns, values)}
                row.update(line=line, status='new')
                try:
                    row['email'] = self._lpu_email(row['email'])
                    row['name'] = self._account_name(row['name'])
                    row['role'] = row['role'].lower()
                    if row['role'] not in _LPU_ROLES:
                        raise DomainError('Use student or professor as the role.')
                    if row['email'] in seen:
                        raise DomainError('This school email is repeated in the file.')
                    seen.add(row['email'])
                except DomainError as exc:
                    row.update(status='invalid', issue=str(exc))
                entries.append(row)
        except csv.Error as exc:
            raise DomainError(f'Check the CSV formatting near line {reader.line_num}.') from exc
        if not entries:
            raise DomainError('Add at least one account below the CSV header.')

        with self.db.connect() as conn:
            conn.execute('BEGIN IMMEDIATE' if preview is not None else 'BEGIN')
            actor = conn.execute('SELECT * FROM users WHERE id=?', (admin.id,)).fetchone()
            require_permission(User.from_row(actor) if actor else None, 'manage_staff')
            for row in entries:
                if row['status'] == 'new' and conn.execute(
                        'SELECT 1 FROM users WHERE email=?', (row['email'],)).fetchone():
                    row.update(status='existing', issue='An account already uses this email.')
            token = self.digest(json.dumps(entries, sort_keys=True))
            new = [row for row in entries if row['status'] == 'new']
            invalid = sum(row['status'] == 'invalid' for row in entries)
            if preview is None:
                return {'rows': entries, 'preview': token, 'new': len(new), 'invalid': invalid}
            if not isinstance(preview, str) or preview != token:
                raise DomainError('The account list changed. Preview the CSV again before importing.', 409)
            if invalid or not new:
                raise DomainError('Fix invalid rows and include at least one new account.')
            for row in new:
                user_id = conn.execute('INSERT INTO users(name,email,role) VALUES(?,?,?)',
                                       (row['name'], row['email'], row['role'])).lastrowid
                conn.execute('INSERT INTO local_accounts(user_id) VALUES(?)', (user_id,))
            self._audit(conn, admin.id, 'LPU_ACCOUNTS_IMPORTED', f'{len(new)} campus accounts created')
            return {'created': len(new)}

    def request_account_setup_code(self, email, source):
        self._require_live_accounts()
        if not self.smtp_enabled:
            raise DomainError("LPU email delivery is unavailable. Contact CSA for a setup code.", 503)
        email = self._lpu_email(email)
        now = time.time()
        code = secrets.token_urlsafe(24)
        code_hash = self.digest(code)
        response = {"message": "If CSA has set up this account, check your school inbox for your latest code."}
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            self._limit_email_requests(conn, source, now)
            account = self._local_account(conn, email)
            if not account:
                return response
            expires = account["code_expires"] or 0
            if account["code_hash"] and expires > now + _SETUP_CODE_LIFETIME - _EMAIL_RESEND_DELAY:
                return response
            conn.execute("UPDATE local_accounts SET code_hash=?,code_expires=? WHERE user_id=?",
                         (code_hash, now + _SETUP_CODE_LIFETIME, account["id"]))
        try:
            self._send_account_setup_email(email, code, reset=bool(account["password_hash"]))
        except _MAIL_ERRORS:
            with self.db.connect() as conn:
                conn.execute("UPDATE local_accounts SET code_hash=?,code_expires=? WHERE user_id=? AND code_hash=?",
                             (account["code_hash"], account["code_expires"], account["id"], code_hash))
                self._audit(conn, None, 'ACCOUNT_CODE_EMAIL_FAILED', f'LPU account {account["id"]}')
        return response

    def check_account_setup_code(self, email, code):
        self._require_live_accounts()
        email = self._lpu_email(email)
        with self.db.connect() as conn:
            self._require_setup_code(conn, email, code)

    def _require_setup_code(self, conn, email, code):
        code = code.strip() if isinstance(code, str) else ''
        row = self._local_account(conn, email)
        if (not re.fullmatch(r'[A-Za-z0-9_-]{32}', code) or not row or not row['code_hash']
                or not row['code_expires'] or row['code_expires'] <= time.time()
                or not hmac.compare_digest(row['code_hash'], self.digest(code))):
            raise DomainError("Invalid or expired setup code.", 401)
        return row

    def set_account_password(self, email, code, password, confirmation):
        self._require_live_accounts()
        email = self._lpu_email(email)
        password = self._confirmed_lpu_password(password, confirmation)
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = self._require_setup_code(conn, email, code)
            conn.execute("UPDATE users SET password_hash=? WHERE id=?", (hash_password(password, minimum=8), row['id']))
            conn.execute("UPDATE local_accounts SET code_hash=NULL,code_expires=NULL WHERE user_id=?", (row['id'],))
            conn.execute("DELETE FROM sessions WHERE user_id=?", (row['id'],))
            conn.execute("DELETE FROM login_limits WHERE identity=?", ('student:' + email,))
            self._audit(conn, row['id'], 'ACCOUNT_PASSWORD_SET', 'One-time code redeemed')

    @staticmethod
    def _local_account(conn, email):
        row = conn.execute("""SELECT u.*, a.code_hash, a.code_expires FROM users u
                              JOIN local_accounts a ON a.user_id=u.id
                              WHERE u.email=? AND u.active=1 AND u.blocked=0""", (email,)).fetchone()
        return row if row and row['role'] in _LPU_ROLES else None

    def account_login(self, session, email, password):
        self._require_live_accounts()
        email = self._lpu_email(email)
        if not isinstance(password, str) or len(password) > 128:
            raise DomainError("Invalid email or password.", 401)
        identity = 'student:' + email
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            now = time.time()
            limit = conn.execute("SELECT * FROM login_limits WHERE identity=?", (identity,)).fetchone()
            if limit and limit['locked_until'] > now:
                raise DomainError("Too many attempts. Try again in 15 minutes.", 429)
            row = self._local_account(conn, email)
            encoded = row['password_hash'] if row and row['password_hash'] else _DUMMY_PASSWORD_HASH
            if check_password(password, encoded) and row and row['password_hash']:
                conn.execute("DELETE FROM login_limits WHERE identity=?", (identity,))
                user = User.from_row(row)
                return user, self._start_session(conn, session, user)
            failures = (limit['failures'] if limit and not limit['locked_until'] else 0) + 1
            conn.execute("INSERT OR REPLACE INTO login_limits VALUES(?,?,?)", (identity, failures, now + 900 if failures >= 5 else 0))
        raise DomainError("Invalid email or password.", 401)

    def staff_login(self, email, password):
        email = str(email).strip().lower()
        error, user_id = None, None
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            limit = conn.execute("SELECT * FROM login_limits WHERE identity=?", (email,)).fetchone()
            if limit and limit["locked_until"] > time.time():
                error = "Too many attempts. Try again in 15 minutes."
            else:
                row = conn.execute("SELECT * FROM users WHERE lower(email)=?", (email,)).fetchone()
                valid = check_password(str(password), row["password_hash"] if row else hash_password("dummy-comparison"))
                if (not row or row["role"] != "admin" or not row["active"] or row["blocked"] or not valid
                        or (not self.demo_mode and email.endswith("@example.test"))):
                    failures = (limit["failures"] if limit else 0) + 1
                    conn.execute("INSERT OR REPLACE INTO login_limits VALUES(?,?,?)",
                                 (email, failures, time.time() + 900 if failures >= 5 else 0))
                    error = "Invalid staff credentials or inactive account."
                else:
                    conn.execute("DELETE FROM login_limits WHERE identity=?", (email,))
                    user_id = row["id"]
        if error:
            raise DomainError(error, 401)
        return self.get_user(user_id)

    def microsoft_start(self, session):
        if not self.msal_app:
            raise DomainError("Configure your university Microsoft tenant and application first.", 503)
        try:
            flow = self.msal_app.initiate_auth_code_flow(scopes=["User.Read"], redirect_uri=self.redirect)
        except Exception:
            raise DomainError("University sign-in is temporarily unavailable. Please try again later.", 503) from None
        with self.db.connect() as conn:
            conn.execute("UPDATE sessions SET oauth_flow=? WHERE token_hash=?", (json.dumps(flow), session["token_hash"]))
        return flow["auth_uri"]

    def microsoft_finish(self, session, query):
        if not self.msal_app:
            raise DomainError("This sign-in session is invalid. Please start again.", 401)
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            stored = conn.execute("SELECT oauth_flow FROM sessions WHERE token_hash=? AND expires>?", (session["token_hash"], time.time())).fetchone()
            flow = stored[0] if stored else None
            conn.execute("UPDATE sessions SET oauth_flow=NULL WHERE token_hash=?", (session["token_hash"],))
        if not flow:
            raise DomainError("This sign-in session is invalid. Please start again.", 401)
        try:
            result = self.msal_app.acquire_token_by_auth_code_flow(json.loads(flow), query)
        except (ValueError, RuntimeError):
            raise DomainError("Microsoft could not validate the sign-in response.", 401) from None
        except Exception:
            raise DomainError("University sign-in is temporarily unavailable. Please start again later.", 503) from None
        claims = result.get("id_token_claims", {})
        try:
            email = self._lpu_email(claims.get("preferred_username"))
        except DomainError:
            raise DomainError(f"Sign in with your @{LPU_EMAIL_DOMAIN} Microsoft account.", 403) from None
        if not result.get("access_token") or claims.get("tid", "").lower() != self.tenant.lower():
            raise DomainError("Sign in with an approved university Microsoft account.", 403)
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM users WHERE lower(email)=?", (email,)).fetchone()
            if row:
                if row["role"] not in ("student", "professor") or not row["active"] or row["blocked"]:
                    raise DomainError("This account cannot access the university dashboard.", 403)
                uid = row["id"]
            else:
                uid = conn.execute("INSERT INTO users(name,email,role,password_hash) VALUES(?,?,?,?)",
                                   (claims.get("name", email), email, "student", "")).lastrowid
        return self.get_user(uid)

    def demo_login(self, role):
        if not self.demo_mode:
            raise DomainError("Demonstration access is disabled.", 404)
        if not isinstance(role, str) or role not in {"admin", "student", "student2", "professor", "guest"}:
            raise DomainError("Choose a valid demonstration account.")
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE email=?", (f"demo.{role}@example.test",)).fetchone()
        if not row or not row["active"] or row["blocked"]:
            raise DomainError("This demonstration account is unavailable.", 403)
        return User.from_row(row)
