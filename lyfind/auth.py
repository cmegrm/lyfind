"""Persistent sessions, school-email and sign-up codes, passwords, rate limits, and optional Microsoft sign-in."""
import hashlib
import hmac
import json
import os
import re
import secrets
import smtplib
import ssl
import time
from datetime import date
from email.message import EmailMessage
from email_templates import code_email

from lyfind.domain import DomainError
from lyfind.passwords import first_problem
from lyfind.users import User, check_password, hash_password, optional_phone, person_name, split_display_name


DENIED = "We could not sign you in with that email. Contact the CSA office."
# LPU student emails are year-digit-five digits at lpunetwork.edu.ph. Screens only show @lpunetwork.edu.ph.
STUDENT_DOMAIN = "lpunetwork.edu.ph"
STUDENT_EXAMPLE = "@" + STUDENT_DOMAIN
STUDENT_LOCAL = re.compile(r"(\d{4})-(\d)-(\d{5})", re.ASCII)
FORMAT_ERROR = "That does not look like a student email. Use your @lpunetwork.edu.ph address."


def student_number(email, campus_codes=(), this_year=None):
    """The local part of a valid lpunetwork.edu.ph student email, otherwise ''."""
    local, _, domain = str(email or "").strip().lower().partition("@")
    match = STUDENT_LOCAL.fullmatch(local)
    if domain != STUDENT_DOMAIN or not match:
        return ""
    if not 2000 <= int(match.group(1)) <= (this_year or date.today().year):
        return ""
    if campus_codes and match.group(2) not in campus_codes:
        return ""
    return local
DISPOSABLE_DOMAINS = frozenset("""mailinator.com guerrillamail.com guerrillamail.net sharklasers.com 10minutemail.com 10minutemail.net
tempmail.com temp-mail.org temp-mail.io tempmailo.com yopmail.com yopmail.net trashmail.com trashmail.net getnada.com nada.email
throwawaymail.com maildrop.cc dispostable.com fakeinbox.com mintemail.com mohmal.com emailondeck.com burnermail.io spamgourmet.com
mailnesia.com mytemp.email tempail.com discard.email moakt.com inboxkitten.com""".split())


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
        self.smtp_enabled = bool(os.environ.get("SMTP_HOST") and os.environ.get("SMTP_FROM"))
        self.msal_app = None
        if self.tenant and self.client_id and self.client_secret and self.domains:
            if not re.fullmatch(r"[0-9a-fA-F-]{36}", self.tenant):
                raise ValueError("MICROSOFT_TENANT_ID must be your university tenant UUID.")
            try:
                import msal
            except ImportError:
                raise RuntimeError("Install requirements/live.txt to enable Microsoft sign-in.") from None
            self.msal_app = msal.ConfidentialClientApplication(
                self.client_id, authority=f"https://login.microsoftonline.com/{self.tenant}",
                client_credential=self.client_secret,
            )
        # Students use lpunetwork.edu.ph. lpu.edu.ph stays allowed for professors and staff. Override with UNIVERSITY_EMAIL_DOMAINS.
        self.school_domains = self.domains or {STUDENT_DOMAIN}
        # Optional anti-prank list for the middle digit of a student email (empty = any digit). We do not assume what it means.
        self.campus_codes = frozenset(v.strip() for v in os.environ.get("CAMPUS_CODES", "").split(",") if v.strip())
        self.resend_seconds = int(os.environ.get("CODE_RESEND_SECONDS", "60"))
        self.code_minutes = 10

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
                      "user_id": None, "expires": time.time() + 8 * 3600, "oauth_flow": None}
            conn.execute("INSERT INTO sessions(token_hash,csrf,expires) VALUES(?,?,?)",
                         (record["token_hash"], record["csrf"], record["expires"]))
            return record, raw

    def current_user(self, session):
        if not session.get("user_id"):
            return None
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()
            if row and row["active"] and not row["blocked"] and row["email_verified"]:
                if not self.demo_mode and row["email"].endswith("@example.test"):
                    return None
                return User.from_row(row)
        return None

    def sign_in(self, session, user, lifetime=8 * 3600):
        # Rotate both the authentication token and anti-forgery token after login.
        raw, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        with self.db.connect() as conn:
            conn.execute("DELETE FROM sessions WHERE token_hash=?", (session["token_hash"],))
            conn.execute("INSERT INTO sessions(token_hash,user_id,csrf,expires) VALUES(?,?,?,?)",
                         (self.digest(raw), user.id, csrf, time.time() + lifetime))
            self._audit(conn, user.id, "SIGNED_IN", f"Role {user.role}")
        session.update(token_hash=self.digest(raw), csrf=csrf, user_id=user.id)
        return raw

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

    # ---- rate limits -------------------------------------------------------------------------------
    @staticmethod
    def _hit(conn, bucket, limit, window, message):
        """Count one event in a sliding window. Raises 429 with a plain message once the limit is reached."""
        now = time.time()
        conn.execute("DELETE FROM rate_events WHERE at < ?", (now - 86400,))
        used = conn.execute("SELECT COUNT(*) FROM rate_events WHERE bucket=? AND at>?", (bucket, now - window)).fetchone()[0]
        if used >= limit:
            raise DomainError(message, 429)
        conn.execute("INSERT INTO rate_events(bucket,at) VALUES(?,?)", (bucket, now))

    @staticmethod
    def _count(conn, bucket, window):
        return conn.execute("SELECT COUNT(*) FROM rate_events WHERE bucket=? AND at>?", (bucket, time.time() - window)).fetchone()[0]

    def _code_caps(self):
        """Demo needs headroom for retries. Live stays tight against pranks."""
        if self.demo_mode:
            return 20, 60, 3600, "Too many codes. Wait a few minutes, then try again."
        return 5, 20, 3600, "Too many codes for this email. Try again in an hour."

    # ---- one-time codes ------------------------------------------------------------------------------
    @property
    def can_send_codes(self):
        """Live mode needs real email. Demo mode may show the code on screen when email is not set up."""
        return self.smtp_enabled or self.demo_mode

    def _issue_code(self, conn, email, purpose, secret=None):
        """Store a salted hash of a fresh code; earlier unused codes for this email and purpose stop working."""
        code, salt, now = secret or f"{secrets.randbelow(1000000):06d}", secrets.token_hex(8), time.time()
        conn.execute("UPDATE email_codes SET used=1 WHERE email=? AND purpose=? AND used=0", (email, purpose))
        conn.execute("INSERT INTO email_codes(email,purpose,salt,code_hash,expires,requested) VALUES(?,?,?,?,?,?)",
                     (email, purpose, salt, self.digest(f"{salt}:{email}:{code}"), now + self.code_minutes * 60, now))
        return code

    def _cooldown(self, conn, email, purpose):
        row = conn.execute("SELECT requested FROM email_codes WHERE email=? AND purpose=? ORDER BY id DESC LIMIT 1", (email, purpose)).fetchone()
        if row and self.resend_seconds:
            wait = int(self.resend_seconds - (time.time() - row["requested"])) + 1
            if wait > 0:
                raise DomainError(f"Please wait {wait} seconds before asking for another code.", 429)

    def _deliver(self, conn, email, code, purpose):
        """Email the code. Returns the code only when demo mode has no email set up; never in live mode."""
        if self.smtp_enabled:
            try:
                self._send_email(email, code)
            except (OSError, smtplib.SMTPException):
                conn.execute("DELETE FROM email_codes WHERE email=? AND purpose=? AND used=0", (email, purpose))
                conn.commit()
                raise DomainError("We could not send the email. Please try again in a few minutes.", 503) from None
            return None
        return code if self.demo_mode else None

    def _send_email(self, email, code):
        msg = code_email(email, code, subject="Your LyFind code", heading="Your sign-in code",
                         intro="Use this code to continue to LyFind.", instructions="Enter the code on the page where you requested it.",
                         expiry=f"{self.code_minutes} minutes", security_note="If you did not request this code, ignore this email.")
        msg["From"] = os.environ["SMTP_FROM"]
        host, port = os.environ["SMTP_HOST"], int(os.environ.get("SMTP_PORT", "587"))
        try:
            import certifi
            context = ssl.create_default_context(cafile=certifi.where())
        except ImportError:
            context = ssl.create_default_context()
        if os.environ.get("SMTP_SSL", "0") == "1":
            client = smtplib.SMTP_SSL(host, port, timeout=15, context=context)
        else:
            client = smtplib.SMTP(host, port, timeout=15)
        with client:
            if os.environ.get("SMTP_SSL", "0") != "1":
                client.starttls(context=context)
            if os.environ.get("SMTP_USER"):
                from lyfind.configuration import smtp_password
                client.login(os.environ["SMTP_USER"], smtp_password())
            client.send_message(msg)

    def _check_code(self, conn, email, purpose, code, ip):
        """Validate a code: single use, 10 minutes, 5 tries, and a per-address and per-email limit on wrong tries."""
        wrong = "Too many wrong codes. Wait 15 minutes, or ask for a new code."
        if self._count(conn, "wrong:ip:" + ip, 900) >= 20 or self._count(conn, "wrong:email:" + email, 900) >= 10:
            raise DomainError(wrong, 429)
        row = conn.execute("SELECT * FROM email_codes WHERE email=? AND purpose=? ORDER BY id DESC LIMIT 1", (email, purpose)).fetchone()
        if not row or row["used"] or row["expires"] < time.time() or row["attempts"] >= 5:
            raise DomainError("That code has expired or was already used. Ask for a new code.", 401)
        if not hmac.compare_digest(row["code_hash"], self.digest(f"{row['salt']}:{email}:{code}")):
            conn.execute("UPDATE email_codes SET attempts=attempts+1 WHERE id=?", (row["id"],))
            conn.execute("INSERT INTO rate_events(bucket,at) VALUES(?,?)", ("wrong:ip:" + ip, time.time()))
            conn.execute("INSERT INTO rate_events(bucket,at) VALUES(?,?)", ("wrong:email:" + email, time.time()))
            left = 4 - row["attempts"]
            conn.commit()
            raise DomainError(f"That code is not right. You have {left} {'try' if left == 1 else 'tries'} left." if left > 0
                              else "That code is not right and has been cancelled. Ask for a new code.", 401)
        conn.execute("UPDATE email_codes SET used=1 WHERE id=?", (row["id"],))

    # ---- school email sign-in (students and professors) ----------------------------------------------
    def student_number_of(self, email):
        return student_number(email, self.campus_codes) if STUDENT_DOMAIN in self.school_domains else ""

    def _school_entry(self, conn, email):
        """The roster row (or a default student) allowed to sign in with this email, otherwise None.

        A lpunetwork.edu.ph address that is not a valid student email and is not on the roster
        (a professor may be) gets a friendly format message instead."""
        domain = email.rsplit("@", 1)[-1]
        row = conn.execute("SELECT * FROM roster WHERE lower(email)=?", (email,)).fetchone()
        if domain == STUDENT_DOMAIN and not row and not self.student_number_of(email):
            raise DomainError(FORMAT_ERROR, 400, field="email")
        if row:
            return dict(row) if row["active"] else None
        if domain not in self.school_domains:
            return None
        # Live mode: a non-empty roster is an allowlist. Demo mode still lets any valid school email in,
        # because CSA may not have a full student list yet; the roster then only sets the role.
        if not self.demo_mode and conn.execute("SELECT COUNT(*) FROM roster").fetchone()[0]:
            return None
        return {"role": "student", "name": ""}

    def _school_account_ok(self, conn, email):
        user = conn.execute("SELECT * FROM users WHERE lower(email)=?", (email,)).fetchone()
        return not user or (user["role"] in ("student", "professor", "guest") and user["active"] and not user["blocked"])

    def request_school_code(self, email, ip="local"):
        email = str(email or "").strip().lower()
        if (not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) or len(email) > 254
                or (email.rsplit('@',1)[-1] != STUDENT_DOMAIN and not (self.demo_mode and email.endswith('@example.test')))):
            raise DomainError("Use your @lpunetwork.edu.ph school email.", 400, field="email")
        if not self.can_send_codes:
            raise DomainError("Email sign-in is not set up yet. Contact the CSA office.", 503)
        code = None
        email_limit, ip_limit, window, busy = self._code_caps()
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            self._hit(conn, "code:ip:" + ip, ip_limit, window, busy)
            self._hit(conn, "code:email:" + email, email_limit, window, busy)
            conn.commit()
            conn.execute("BEGIN IMMEDIATE")
            entry = self._school_entry(conn, email)
            if not entry or not self._school_account_ok(conn, email):
                conn.commit()
                raise DomainError(DENIED, 403, field="email")
            existing = conn.execute("SELECT password_hash FROM users WHERE lower(email)=?", (email,)).fetchone()
            if existing and existing["password_hash"]:
                conn.commit()
                raise DomainError("This email already has an account. Sign in with your email and password.", 400, field="email")
            self._cooldown(conn, email, "school")
            code = self._issue_code(conn, email, "school")
            shown = self._deliver(conn, email, code, "school")
            conn.commit()
        result = {"email": email, "expires_in": self.code_minutes * 60, "resend_in": self.resend_seconds}
        if shown:
            result["demo_code"] = shown
        return result

    def verify_school_code(self, email, code, ip="local"):
        """Check the emailed code. It does not sign anyone in: the next step chooses a password."""
        email, code = str(email or "").strip().lower(), re.sub(r"\D", "", str(code or ""))
        if len(code) != 6:
            raise DomainError("Enter the 6 digits from your email.", 400, field="code")
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            self._check_code(conn, email, "school", code, ip)
            entry = self._school_entry(conn, email)
            if not entry or not self._school_account_ok(conn, email):
                conn.commit()
                raise DomainError(DENIED, 403)
            row = conn.execute("SELECT password_hash FROM users WHERE lower(email)=?", (email,)).fetchone()
            if row and row["password_hash"]:
                conn.commit()
                raise DomainError("This email already has an account. Sign in with your email and password.", 400, field="email")
            token = self._issue_code(conn, email, "school", secrets.token_urlsafe(32))
            conn.commit()
        return {"email": email, "setup_token": token, "name": (entry.get("name") or "").strip(),
                "expires_in": self.code_minutes * 60}

    def set_school_password(self, email, token, password, confirm=None, name="", ip="local",
                            first_name="", middle_name="", last_name="", suffix="", phone=""):
        """Create the student or professor account once the emailed code has been checked."""
        email, token = str(email or "").strip().lower(), str(token or "").strip()
        password = str(password or "")
        display, first, middle, last, suffix, problems = person_name(
            first_name, middle_name, last_name, suffix, name)
        phone, phone_problems = optional_phone(phone)
        problems.update(phone_problems)
        weak = first_problem(password, display, email)
        if weak:
            problems["password"] = weak
        if confirm is not None and str(confirm) != password:
            problems["confirm"] = "The two passwords are not the same."
        if problems:
            raise DomainError(next(iter(problems.values())), 400, fields=problems)
        if not token:
            raise DomainError("That code has expired or was already used. Ask for a new code.", 401)
        user_id = None
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            self._check_code(conn, email, "school", token, ip)
            entry = self._school_entry(conn, email)
            if not entry or not self._school_account_ok(conn, email):
                conn.commit()
                raise DomainError(DENIED, 403)
            row = conn.execute("SELECT * FROM users WHERE lower(email)=?", (email,)).fetchone()
            if row and row["password_hash"]:
                conn.commit()
                raise DomainError("This email already has an account. Sign in with your email and password.", 400, field="email")
            role = entry.get("role", "student")
            parsed = self.student_number_of(email)
            number = parsed or (entry.get("student_number") or "") if role == "student" else ""
            if row:
                user_id = row["id"]
                conn.execute("UPDATE users SET first_name=?, middle_name=?, last_name=?, suffix=?, role=?, password_hash=?, email_verified=1, student_number=?, phone=? WHERE id=?",
                             (first, middle, last, suffix, role, hash_password(password), number, phone, user_id))
            else:
                user_id = conn.execute(
                    "INSERT INTO users(email,role,password_hash,email_verified,student_number,phone,first_name,middle_name,last_name,suffix) VALUES(?,?,?,1,?,?,?,?,?,?)",
                    (email, role, hash_password(password), number, phone, first, middle, last, suffix)).lastrowid
            self._audit(conn, user_id, "ACCOUNT_CREATED", f"{role.title()} account opened with a school email code and a password")
            conn.commit()
        return self.get_user(user_id)

    def get_user(self, user_id):
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
            return User.from_row(row)

    def staff_login(self, email, password, ip="local"):
        return self._password_login(email, password, {"admin"}, ip)

    def password_login(self, email, password, ip="local"):
        """Email and password for every role. Staff and public accounts share one form."""
        return self._password_login(email, password, {"admin", "student", "professor", "guest"}, ip)

    def _password_login(self, email, password, roles, ip="local"):
        email = str(email).strip().lower()
        error, user_id, status = None, None, 401
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if self._count(conn, "login:ip:" + ip, 900) >= 40:
                error, status = "Too many tries from this device. Wait 15 minutes, then try again.", 429
            limit = conn.execute("SELECT * FROM login_limits WHERE identity=?", (email,)).fetchone()
            if error:
                pass
            elif limit and limit["locked_until"] > time.time():
                error = "Too many tries. Wait 15 minutes, then sign in again."
            else:
                row = conn.execute("SELECT * FROM users WHERE lower(email)=?", (email,)).fetchone()
                valid = check_password(str(password), row["password_hash"] if row and row["password_hash"] else hash_password("dummy-comparison"))
                if (not row or row["role"] not in roles or not row["active"] or not valid
                        or (not self.demo_mode and email.endswith("@example.test"))):
                    failures = (limit["failures"] if limit else 0) + 1
                    conn.execute("INSERT OR REPLACE INTO login_limits VALUES(?,?,?)",
                                 (email, failures, time.time() + 900 if failures >= 5 else 0))
                    conn.execute("INSERT INTO rate_events(bucket,at) VALUES(?,?)", ("login:ip:" + ip, time.time()))
                    error = "That email or password is not right. Check both and try again."
                elif row["blocked"]:
                    error, status = "We could not sign you in. Contact the CSA office.", 403
                elif not row["email_verified"]:
                    error = "Confirm your email first. Choose Sign up and enter the 6-digit code we sent."
                else:
                    conn.execute("DELETE FROM login_limits WHERE identity=?", (email,))
                    user_id = row["id"]
            conn.commit()
        if error:
            raise DomainError(error, status)
        return self.get_user(user_id)

    def is_school_email(self, email):
        """School domains (UNIVERSITY_EMAIL_DOMAINS, default lpunetwork.edu.ph and lpu.edu.ph) plus, when none are set, any .edu / .edu.ph address."""
        domain = email.rsplit("@", 1)[-1]
        if domain in self.school_domains:
            return True
        return not self.domains and (domain.endswith((".edu", ".edu.ph")) or domain in {"edu", "edu.ph"})

    # ---- guest sign-up: personal email, one code, then name and password ---------------------------
    def _guest_email(self, email):
        email = str(email or "").strip().lower()
        problems = {}
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) or len(email) > 254:
            problems["email"] = "Enter a valid email address, like you@example.com."
        elif self.is_school_email(email):
            problems["email"] = ("That is a school email. Students and professors open an account with a code sent to "
                                 "that email, then choose a password. After that, sign in with the email and password.")
        elif email.rsplit("@", 1)[-1] in DISPOSABLE_DOMAINS:
            problems["email"] = "Use an email address you keep, not a temporary one."
        return email, problems

    def register(self, email, ip="local", website="", **_ignored):
        """Send one code to a personal email. The name and password come after the code."""
        if str(website or "").strip():  # honeypot: people never see or fill this field
            raise DomainError("We could not create that account. Please try again later.", 400)
        email, problems = self._guest_email(email)
        if problems:
            raise DomainError(next(iter(problems.values())), 400, fields=problems)
        if not self.can_send_codes:
            raise DomainError("Sign-up by email is not set up yet. Contact the CSA office.", 503)
        email_limit, _, window, busy = self._code_caps()
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            self._hit(conn, "signup:ip:" + ip, 10, 3600, "Too many sign-ups from this device. Try again in an hour.")
            self._hit(conn, "code:email:" + email, email_limit, window, busy)
            conn.commit()
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM users WHERE lower(email)=?", (email,)).fetchone()
            if row and row["password_hash"]:
                conn.commit()
                raise DomainError("An account with that email already exists. Sign in instead.", 400, field="email")
            self._cooldown(conn, email, "signup")
            code = self._issue_code(conn, email, "signup")
            shown = self._deliver(conn, email, code, "signup")
            conn.commit()
        result = {"email": email, "expires_in": self.code_minutes * 60, "resend_in": self.resend_seconds}
        if shown:
            result["demo_code"] = shown
        return result

    def resend_signup_code(self, email, ip="local"):
        email = str(email or "").strip().lower()
        if not self.can_send_codes:
            raise DomainError("Sign-up by email is not set up yet. Contact the CSA office.", 503)
        email_limit, ip_limit, window, busy = self._code_caps()
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            self._hit(conn, "code:ip:" + ip, ip_limit, window, busy)
            self._hit(conn, "code:email:" + email, email_limit, window, busy)
            conn.commit()
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT password_hash FROM users WHERE lower(email)=?", (email,)).fetchone()
            if row and row["password_hash"]:
                conn.commit()
                raise DomainError("An account with that email already exists. Sign in instead.", 400, field="email")
            pending = conn.execute("SELECT 1 FROM email_codes WHERE lower(email)=? AND purpose='signup'", (email,)).fetchone()
            if not pending:
                conn.commit()
                raise DomainError("There is no sign-up waiting for that email. Start again.", 404)
            self._cooldown(conn, email, "signup")
            code = self._issue_code(conn, email, "signup")
            shown = self._deliver(conn, email, code, "signup")
            conn.commit()
        result = {"email": email, "expires_in": self.code_minutes * 60, "resend_in": self.resend_seconds}
        if shown:
            result["demo_code"] = shown
        return result

    def verify_signup(self, email, code, ip="local"):
        """Check the emailed code. It does not sign anyone in: the next step chooses a name and password."""
        email, code = str(email or "").strip().lower(), re.sub(r"\D", "", str(code or ""))
        if len(code) != 6:
            raise DomainError("Enter the 6 digits from your email.", 400, field="code")
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            self._check_code(conn, email, "signup", code, ip)
            row = conn.execute("SELECT password_hash FROM users WHERE lower(email)=?", (email,)).fetchone()
            if row and row["password_hash"]:
                conn.commit()
                raise DomainError("An account with that email already exists. Sign in instead.", 400, field="email")
            token = self._issue_code(conn, email, "signup", secrets.token_urlsafe(32))
            conn.commit()
        return {"email": email, "setup_token": token, "expires_in": self.code_minutes * 60}

    def finish_guest(self, email, token, password, confirm=None, ip="local", phone="",
                     first_name="", middle_name="", last_name="", suffix="", name=""):
        """Create the guest once the personal email has been checked."""
        email, token = str(email or "").strip().lower(), str(token or "").strip()
        password = str(password or "")
        _, problems = self._guest_email(email)
        display, first, middle, last, suffix, name_problems = person_name(
            first_name, middle_name, last_name, suffix, name)
        problems.update(name_problems)
        phone, phone_problems = optional_phone(phone)
        problems.update(phone_problems)
        weak = first_problem(password, display, email)
        if weak:
            problems["password"] = weak
        if confirm is not None and str(confirm) != password:
            problems["confirm"] = "The two passwords are not the same."
        if problems:
            raise DomainError(next(iter(problems.values())), 400, fields=problems)
        if not token:
            raise DomainError("That code has expired or was already used. Ask for a new code.", 401)
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            self._check_code(conn, email, "signup", token, ip)
            row = conn.execute("SELECT * FROM users WHERE lower(email)=?", (email,)).fetchone()
            if row and row["password_hash"]:
                conn.commit()
                raise DomainError("An account with that email already exists. Sign in instead.", 400, field="email")
            if row:
                user_id = row["id"]
                conn.execute("UPDATE users SET first_name=?, middle_name=?, last_name=?, suffix=?, role='guest', password_hash=?, email_verified=1, phone=? WHERE id=?",
                             (first, middle, last, suffix, hash_password(password), phone, user_id))
            else:
                user_id = conn.execute(
                    "INSERT INTO users(email,role,password_hash,email_verified,phone,first_name,middle_name,last_name,suffix) VALUES(?,'guest',?,1,?,?,?,?,?)",
                    (email, hash_password(password), phone, first, middle, last, suffix)).lastrowid
            self._audit(conn, user_id, "ACCOUNT_CREATED", "Guest account opened with a personal email code and a password")
            conn.commit()
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
        email = claims.get("preferred_username", "").lower()
        if (not result.get("access_token") or claims.get("tid", "").lower() != self.tenant.lower()
                or email.rsplit('@', 1)[-1] not in self.domains):
            raise DomainError("Sign in with an approved university Microsoft account.", 403)
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            roster = conn.execute("SELECT * FROM roster WHERE lower(email)=?", (email,)).fetchone()
            if roster and not roster["active"]:
                raise DomainError("This account cannot access the university dashboard.", 403)
            row = conn.execute("SELECT * FROM users WHERE lower(email)=?", (email,)).fetchone()
            if row:
                if row["role"] not in ("student", "professor") or not row["active"] or row["blocked"]:
                    raise DomainError("This account cannot access the university dashboard.", 403)
                uid = row["id"]
            else:
                role = roster["role"] if roster and roster["role"] in ("student", "professor") else "student"
                derived = self.student_number_of(email)
                number = (derived or (roster["student_number"] if roster else "")) if role == "student" else ""
                first, middle, last, suffix = split_display_name(claims.get("name") or (roster["name"] if roster else "") or email)
                uid = conn.execute(
                    "INSERT INTO users(first_name,middle_name,last_name,suffix,email,role,password_hash,student_number) VALUES(?,?,?,?,?,?,?,?)",
                    (first, middle, last, suffix, email, role, "", number)).lastrowid
        return self.get_user(uid)

    # ---- self-service password reset via one-time email code --------------------------------------
    def request_password_reset(self, email, ip="local"):
        email = str(email or "").strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) or len(email) > 254:
            raise DomainError("Enter the email address for your account.", 400, field="email")
        if not self.can_send_codes:
            raise DomainError("Email delivery is not set up yet. Visit the CSA office with a valid ID.", 503)
        email_limit, ip_limit, window, busy = self._code_caps()
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            self._hit(conn, "code:ip:" + ip, ip_limit, window, busy)
            self._hit(conn, "code:email:" + email, email_limit, window, busy)
            conn.commit()
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM users WHERE lower(email)=?", (email,)).fetchone()
            if not row or (not self.demo_mode and email.endswith("@example.test")):
                conn.commit()
                raise DomainError("No password account was found for that email.", 404, field="email")
            if row["role"] == "admin":
                conn.commit()
                raise DomainError("CSA staff passwords must be reset by another administrator.", 403, field="email")
            if not row["active"] or row["blocked"]:
                conn.commit()
                raise DomainError("This account cannot reset its password. Contact the CSA office.", 403, field="email")
            if not row["password_hash"]:
                conn.commit()
                raise DomainError("This account does not have a password yet. Use Sign up or Guest email code instead.", 400, field="email")
            self._cooldown(conn, email, "reset")
            code = self._issue_code(conn, email, "reset")
            shown = self._deliver(conn, email, code, "reset")
            conn.commit()
        result = {"email": email, "expires_in": self.code_minutes * 60, "resend_in": self.resend_seconds}
        if shown:
            result["demo_code"] = shown
        return result

    def verify_password_reset(self, email, code, ip="local"):
        email, code = str(email or "").strip().lower(), re.sub(r"\D", "", str(code or ""))
        if len(code) != 6:
            raise DomainError("Enter the 6 digits from your email.", 400, field="code")
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            self._check_code(conn, email, "reset", code, ip)
            row = conn.execute("SELECT * FROM users WHERE lower(email)=?", (email,)).fetchone()
            if not row or row["role"] not in ("student", "professor", "guest") or not row["active"] or row["blocked"]:
                conn.commit()
                raise DomainError(DENIED, 403)
            token = self._issue_code(conn, email, "reset", secrets.token_urlsafe(32))
            conn.commit()
        return {"email": email, "setup_token": token, "expires_in": self.code_minutes * 60}

    def finish_password_reset(self, email, token, password, confirm=None, ip="local"):
        email, token = str(email or "").strip().lower(), str(token or "").strip()
        password = str(password or "")
        if not token:
            raise DomainError("That code has expired or was already used. Ask for a new code.", 401)
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM users WHERE lower(email)=?", (email,)).fetchone()
            if not row or row["role"] not in ("student", "professor", "guest") or not row["active"] or row["blocked"]:
                conn.commit()
                raise DomainError(DENIED, 403)
            problems = {}
            weak = first_problem(password, row["name"] or "", email)
            if weak:
                problems["password"] = weak
            if confirm is not None and str(confirm) != password:
                problems["confirm"] = "The two passwords are not the same."
            if problems:
                conn.commit()
                raise DomainError(next(iter(problems.values())), 400, fields=problems)
            self._check_code(conn, email, "reset", token, ip)
            conn.execute("UPDATE users SET password_hash=?, email_verified=1 WHERE id=?", (hash_password(password), row["id"]))
            conn.execute("DELETE FROM sessions WHERE user_id=?", (row["id"],))
            conn.execute("DELETE FROM login_limits WHERE identity=?", (email,))
            self._audit(conn, row["id"], "PASSWORD_RESET", "Password reset with a verified email code")
            conn.commit()
            user_id = row["id"]
        return self.get_user(user_id)

    def demo_login(self, role):
        if not self.demo_mode:
            raise DomainError("Demonstration access is disabled.", 404)
        if not isinstance(role, str) or role not in {"admin", "student", "student2", "professor", "guest"}:
            raise DomainError("Choose a valid demonstration role.")
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE email=?", (f"demo.{role}@example.test",)).fetchone()
        if not row or not row["active"] or row["blocked"]:
            raise DomainError("This demonstration account is unavailable.", 403)
        return User.from_row(row)

    def has_admin(self):
        with self.db.connect() as conn:
            return conn.execute("SELECT 1 FROM users WHERE role='admin' AND email NOT LIKE '%@example.test'").fetchone() is not None

    def setup_first_admin(self, data):
        display, first, middle, last, suffix, errors = person_name(name=data.get('name', ''))
        email = str(data.get('email', '')).strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
            errors['email'] = 'Enter a valid CSA email.'
        password = data.get('password', '')
        weak = first_problem(password, display, email, minimum=12)
        if weak:
            errors['password'] = weak
        if password != data.get('confirm'):
            errors['confirm'] = 'The passwords do not match.'
        if errors:
            raise DomainError(next(iter(errors.values())), fields=errors)
        with self.db.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            if conn.execute("SELECT 1 FROM users WHERE role='admin' AND email NOT LIKE '%@example.test'").fetchone():
                raise DomainError('A CSA administrator has already been created.', 409)
            uid = conn.execute("INSERT INTO users(first_name,middle_name,last_name,suffix,email,role,password_hash) VALUES(?,?,?,?,?,'admin',?)",
                               (first, middle, last, suffix, email, hash_password(password))).lastrowid
            self._audit(conn, uid, 'ADMIN_CREATED', 'First CSA administrator created')
            return User.from_row(conn.execute('SELECT * FROM users WHERE id=?', (uid,)).fetchone())

    def request_guest_code(self, email, ip='local'):
        email, errors = self._guest_email(email)
        if errors:
            raise DomainError(next(iter(errors.values())), fields=errors)
        if not self.can_send_codes:
            raise DomainError('Guest email delivery is unavailable. Contact CSA for help signing in.', 503)
        with self.db.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute('SELECT * FROM users WHERE lower(email)=?', (email,)).fetchone()
            if row and row['role'] != 'guest':
                raise DomainError('Use LPU or CSA sign-in for this account.', 403)
            if row and (not row['active'] or row['blocked']):
                raise DomainError('This account cannot sign in. Contact CSA.', 403)
            email_limit, ip_limit, window, busy = self._code_caps()
            self._hit(conn, 'code:ip:' + ip, ip_limit, window, busy)
            self._hit(conn, 'code:email:' + email, email_limit, window, busy)
            conn.commit()
            conn.execute('BEGIN IMMEDIATE')
            self._cooldown(conn, email, 'signup')
            code = self._issue_code(conn, email, 'signup')
            shown = self._deliver(conn, email, code, 'signup')
        return dict(email=email, expires_in=self.code_minutes*60, resend_in=self.resend_seconds,
                    **({'demo_code': shown} if shown else {}))

    def verify_guest_code(self, email, code, ip='local'):
        email, errors = self._guest_email(email)
        if errors:
            raise DomainError(next(iter(errors.values())), fields=errors)
        if not re.fullmatch(r'[0-9]{6}', str(code)):
            raise DomainError('Enter the six digits from your email.', field='code')
        with self.db.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            self._check_code(conn, email, 'signup', code, ip)
            row = conn.execute('SELECT * FROM users WHERE lower(email)=?', (email,)).fetchone()
            if row and (row['role'] != 'guest' or not row['active'] or row['blocked']):
                raise DomainError('This account cannot use Guest access.', 403)
            if row is None:
                uid = conn.execute("INSERT INTO users(email,role,first_name,last_name,email_verified) VALUES(?,'guest','Guest','Visitor',1)", (email,)).lastrowid
                self._audit(conn, uid, 'ACCOUNT_CREATED', 'Guest email verified')
            else:
                uid = row['id']
                conn.execute('UPDATE users SET email_verified=1 WHERE id=?', (uid,))
            return User.from_row(conn.execute('SELECT * FROM users WHERE id=?', (uid,)).fetchone())
