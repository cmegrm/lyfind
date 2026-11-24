"""Words people see.

The database still stores short status codes such as ``step1_pending``.
Those codes are the claim state machine and the SQL guards. Screens and
API labels use the phrases below instead.
"""

STATUS_LABELS = {
    "available": "In the office",
    "under_verification": "Being checked",
    "released": "Handed back",
    "unclaimed": "Not claimed",
    "step1_pending": "Under review",
    "step2_pending": "Office visit next",
    "verified": "Ready to approve",
    "approved": "Ready to hand over",
    "rejected": "Not approved",
    "awaiting_turn_in": "Bring it to the office",
    "received": "Received at the office",
    "suggested": "Needs a staff review",
    "confirmed": "Owner invited",
    "dismissed": "Not a match",
    "open": "Still looking",
    "closed": "Closed",
    "active": "Active",
    "inactive": "Inactive",
}

STAGES = ("Reported", "Matched", "Verified", "Released")

CATEGORIES = {
    "electronics", "bags", "wallets", "keys",
    "documents", "clothing", "accessories", "other",
    "id", "phone", "laptop", "charger", "earphones", "usb", "calculator",
    "cards", "cash", "watch", "glasses", "jewelry", "shoes", "uniform",
    "books", "umbrella", "bottle", "sports", "medicine",
}

FIELDS = {
    "category": "a category",
    "description": "a description",
    "color": "a color",
    "brand": "a brand",
    "place": "a place",
    "identifying_marks": "distinctive marks",
    "date_lost": "the date you lost it",
    "date_found": "the date it was found",
    "turn_in_deadline": "the day you will bring it to the office",
    "private_details": "private details only the owner would know",
    "photo_id": "a photo",
    "name": "a name",
    "first_name": "a first name",
    "middle_name": "a middle name",
    "last_name": "a last name",
    "suffix": "a suffix",
    "phone": "a phone number",
    "email": "an email address",
    "password": "a password",
    "purpose": "what you told the owner",
    "reason": "a reason",
    "handover_note": "a handover note",
}

PERMISSIONS = {
    "report_lost": "report a lost item",
    "report_found": "report a found item",
    "submit_claim": "submit a claim",
    "view_own": "open this page",
    "view_inventory": "view items in the office",
    "receive_item": "add a found item",
    "run_matching": "find matches",
    "decide_match": "invite or dismiss a match",
    "verify_online": "pass or reject the online check",
    "verify_in_person": "pass or reject the office check",
    "approve_claim": "approve a claim",
    "release_item": "hand an item over",
    "manage_staff": "manage staff accounts",
    "view_audit": "view the activity log",
    "expire_items": "clean up old items",
    "view_hidden_photo": "view private photos",
    "record_consent": "start the office check",
    "moderate": "check, hide or block",
    "manage_roster": "change the allowed school emails",
}


def field_name(field):
    return FIELDS.get(field, str(field).replace("_", " "))


def missing(field):
    return f"Add {field_name(field)}."


def invalid_text(field):
    return f"Check {field_name(field)} and try again."


def too_long(field, maximum):
    name = field_name(field)
    titled = name[:1].upper() + name[1:]
    return f"{titled} is too long. Use {maximum} characters or fewer."


def bad_date(field):
    return f"Choose a real date for {field_name(field)}."


def future_date():
    return "That date is still in the future. Choose today or an earlier day."


def old_date():
    return "That date is more than 3 months ago. Choose a more recent day."


def permission_denied(action):
    what = PERMISSIONS.get(action, "do that")
    return f"Your account cannot {what}. Ask the CSA office if you need access."


def known_category(value):
    value = str(value or "").strip().casefold()
    return value if value in CATEGORIES else ""


def claim_stage(status):
    """Index of the current step: 0 reported, 1 matched, 2 verified, 3 released."""
    if status == "rejected":
        return None
    if status == "released":
        return 3
    if status in {"verified", "approved"}:
        return 2
    if status in {"step1_pending", "step2_pending"}:
        return 1
    return 0


def decorate(payload):
    """Add plain labels beside the stored codes. Does not remove the codes."""
    if not isinstance(payload, dict):
        return payload
    for key in ("items", "reports", "found_reports", "claims", "matches"):
        for row in payload.get(key) or []:
            if not isinstance(row, dict) or "status" not in row:
                continue
            row["status_label"] = STATUS_LABELS.get(row["status"], "Update")
            if key == "claims":
                row["stage"] = claim_stage(row.get("status"))
                row["stage_names"] = list(STAGES)
    return payload
