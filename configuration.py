"""Read-only integration readiness checks; credentials are never printed."""
import importlib.util
import os
from pathlib import Path


def smtp_password():
    password = os.environ.get("SMTP_PASSWORD", "")
    filename = os.environ.get("SMTP_PASSWORD_FILE", "").strip()
    if not password and filename:
        try:
            password = Path(os.path.expandvars(filename)).expanduser().read_text(encoding="utf-8").strip()
        except (OSError, UnicodeError):
            return ""
    return password


def smtp_missing_settings():
    required = ("SMTP_HOST", "SMTP_FROM")
    missing = [name for name in required if not os.environ.get(name, "").strip()]
    if os.environ.get("SMTP_USER", "").strip() and not smtp_password().strip():
        missing.append("SMTP_PASSWORD")
    return missing


def check_configuration():
    groups = {
        "University Microsoft sign-in": ("MICROSOFT_TENANT_ID", "MICROSOFT_CLIENT_ID", "MICROSOFT_CLIENT_SECRET"),
    }
    result = {}
    for label, names in groups.items():
        missing = [name for name in names if not os.environ.get(name, "").strip()]
        result[label] = {"configured": not missing, "missing": missing}
    missing = smtp_missing_settings()
    result["Guest email delivery"] = {"configured": not missing, "missing": missing}
    sdk = importlib.util.find_spec("msal") is not None
    result["University Microsoft sign-in"]["sdk_installed"] = sdk
    result["University Microsoft sign-in"]["configured"] &= sdk
    return result
