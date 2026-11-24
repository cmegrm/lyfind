"""Application-owned role hierarchy and password helpers."""
import hashlib
import hmac
import secrets

QUICK_GUEST_EMAIL_SUFFIX = '@guest.lyfind.invalid'


class DomainError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


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
        kind = {"student": Student, "professor": Professor, "guest": Guest,
                "admin": CSAAdministrator}.get(data["role"], Guest)
        return kind(data["id"], data["name"], data["email"],
                    data.get("active", True), data.get("blocked", False))

    def permissions(self):
        """Overridden by role classes; callers use one shared interface."""
        return {"report_lost", "submit_claim", "view_own"}

    def public(self):
        return {"id": self.id, "name": self.name, "email": None if self.quick_guest else self.email,
                "quick_guest": self.quick_guest,
                "role": self.role, "active": self.active, "blocked": self.blocked,
                "permissions": sorted(self.permissions())}

    @property
    def quick_guest(self):
        return self.role == 'guest' and self.email.lower().endswith(QUICK_GUEST_EMAIL_SUFFIX)


class Guest(User):
    role = "guest"


class Student(User):
    role = "student"

    def permissions(self):
        return super().permissions() | {"report_found", "view_found_board"}


class Professor(Student):
    role = "professor"


class CSAAdministrator(User):
    role = "admin"

    def permissions(self):
        return {"view_own", "view_inventory", "receive_item", "report_for_guest", "run_matching",
                "decide_match", "verify_online", "verify_in_person", "approve_claim",
                "release_item", "manage_staff", "view_audit", "expire_items",
                "view_hidden_photo", "record_consent"}


def require_permission(user, action):
    if not user or not user.active or user.blocked:
        raise DomainError("This account is inactive or blocked.", 403)
    if action not in user.permissions():
        raise DomainError(f"Your account cannot perform {action.replace('_', ' ')}.", 403)


def hash_password(password, *, minimum=10):
    if len(password) < minimum:
        raise DomainError(f"Use a password with at least {minimum} characters.")
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
