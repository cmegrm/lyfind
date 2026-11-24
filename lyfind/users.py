"""Application-owned role hierarchy and password helpers."""
import hashlib
import hmac
import re
import secrets

from lyfind.language import permission_denied
from lyfind.passwords import MIN_LENGTH, counted_length

_SUFFIX = {"jr", "jr.", "sr", "sr.", "ii", "iii", "iv", "v"}


def split_display_name(name):
    """Turn a single display name into first, middle, last, and suffix."""
    parts = str(name or "").replace(",", " ").split()
    if not parts:
        return "", "", "", ""
    suffix = ""
    if len(parts) > 1 and parts[-1].lower().rstrip(".") in {item.rstrip(".") for item in _SUFFIX}:
        suffix = parts.pop()
    if len(parts) == 1:
        return parts[0], "", "", suffix
    if len(parts) == 2:
        return parts[0], "", parts[1], suffix
    return parts[0], " ".join(parts[1:-1]), parts[-1], suffix


def join_display_name(first, middle="", last="", suffix=""):
    return " ".join(part for part in (first, middle, last, suffix) if str(part or "").strip())


def _tidy(value):
    return " ".join(str(value or "").split())


def person_name(first="", middle="", last="", suffix="", name=""):
    """Return display, first, middle, last, suffix, and a field-error dict.

    The four parts are what the database stores. A single full name is only a
    fallback for older callers: it is split, then the display name is rebuilt
    from those parts so the two cannot disagree.
    """
    problems = {}
    using_parts = any(_tidy(value) for value in (first, middle, last, suffix))
    if using_parts or not _tidy(name):
        first, middle, last, suffix = (_tidy(value) for value in (first, middle, last, suffix))
        if len(first) < 2:
            problems["first_name"] = "Enter at least two letters."
        elif len(first) > 40:
            problems["first_name"] = "Use 40 characters or fewer."
        if len(last) < 2:
            problems["last_name"] = "Enter at least two letters."
        elif len(last) > 40:
            problems["last_name"] = "Use 40 characters or fewer."
        if len(middle) > 40:
            problems["middle_name"] = "Use 40 characters or fewer."
        if len(suffix) > 12:
            problems["suffix"] = "Use 12 characters or fewer."
    else:
        source = _tidy(name)
        if len(source) > 120:
            problems["name"] = "Use 120 characters or fewer for your name."
        first, middle, last, suffix = split_display_name(source)
        if not first:
            problems["name"] = "Add your name."
    return join_display_name(first, middle, last, suffix), first, middle, last, suffix, problems


def optional_phone(value):
    """A phone for pickup, or blank. Returns (phone, field errors)."""
    phone = _tidy(value)
    if not phone:
        return "", {}
    if not re.fullmatch(r"\+?[\d\s\-().]+", phone):
        return "", {"phone": "Use numbers only in the phone field."}
    digits = re.sub(r"\D", "", phone)
    if not 10 <= len(digits) <= 15:
        return "", {"phone": "Enter a phone number with 10 to 15 digits, like 0917 123 4567."}
    return phone, {}


class DomainError(Exception):
    def __init__(self, message, status=400, field=None, fields=None):
        super().__init__(message)
        self.status = status
        # `fields` maps a form field name to its own plain-language message.
        self.fields = dict(fields or ({field: message} if field else {}))
        self.field = field or next(iter(self.fields), None)


class User:
    role = "guest"

    def __init__(self, id, name, email, active=True, blocked=False, role=None):
        self.id, self.name, self.email = int(id), name, email
        self.active, self.blocked = bool(active), bool(blocked)
        if role is not None:
            self.role = role

    @classmethod
    def from_row(cls, row):
        data = dict(row)
        if "email_verified" in data and not data["email_verified"]:
            data["active"] = False  # an unconfirmed sign-up cannot do anything yet
        kind = {"student": Student, "professor": Professor, "guest": Guest,
                "admin": CSAAdministrator}.get(data["role"], Guest)
        person = kind(data["id"], data["name"], data["email"],
                      data.get("active", True), data.get("blocked", False))
        person.phone = data.get("phone") or ""
        person.student_number = data.get("student_number") or ""
        person.first_name = data.get("first_name") or ""
        person.middle_name = data.get("middle_name") or ""
        person.last_name = data.get("last_name") or ""
        person.suffix = data.get("suffix") or ""
        if not person.first_name and person.name:
            person.first_name, person.middle_name, person.last_name, person.suffix = split_display_name(person.name)
        return person

    def permissions(self):
        """Overridden by role classes; callers use one shared interface."""
        return {"report_lost", "submit_claim", "view_own"}

    def public(self):
        return {"id": self.id, "name": self.name, "email": self.email,
                "role": self.role, "active": self.active, "blocked": self.blocked,
                "phone": getattr(self, "phone", ""),
                "student_number": getattr(self, "student_number", ""),
                "first_name": getattr(self, "first_name", ""),
                "middle_name": getattr(self, "middle_name", ""),
                "last_name": getattr(self, "last_name", ""),
                "suffix": getattr(self, "suffix", ""),
                "permissions": sorted(self.permissions())}


class Guest(User):
    role = "guest"

    def permissions(self):
        return super().permissions()


class Student(User):
    role = "student"

    def permissions(self):
        return super().permissions() | {"report_found", "view_found_board"}


class Professor(Student):
    role = "professor"


class CSAAdministrator(User):
    role = "admin"

    def permissions(self):
        return {"view_own", "view_inventory", "receive_item", "run_matching",
                "decide_match", "verify_online", "verify_in_person", "approve_claim",
                "release_item", "manage_staff", "view_audit", "expire_items",
                "view_hidden_photo", "record_consent", "moderate", "manage_roster"}


def require_permission(user, action):
    if not user or not user.active or user.blocked:
        raise DomainError("This account is inactive or blocked.", 403)
    if action not in user.permissions():
        raise DomainError(permission_denied(action), 403)


def hash_password(password):
    if counted_length(password) < MIN_LENGTH:
        raise DomainError(f"Use a password with at least {MIN_LENGTH} characters. Spaces do not count.")
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 310000).hex()
    return f"pbkdf2_sha256$310000${salt}${digest}"


def check_password(password, encoded):
    try:
        algorithm, rounds, salt, digest = encoded.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(rounds)).hex()
        return hmac.compare_digest(actual, digest)
    except (ValueError, TypeError, AttributeError):
        return False
