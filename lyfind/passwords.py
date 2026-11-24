"""One password rulebook. The sign-up checklist in static/app.js mirrors these four rules."""

MIN_LENGTH = 8
MAX_LENGTH = 128

# Each rule has a short checklist label (shown live on the form) and a full sentence for errors.
RULES = (
    ("length", "{n} to 128 characters, spaces not counted", "Use {n} to 128 characters. Spaces do not count."),
    ("identity", "Not your name or email", "Do not use your name or email in your password."),
    ("letter", "Uppercase and lowercase letters", "Include an uppercase and a lowercase letter."),
    ("mix", "A number and a symbol", "Include a number and a symbol."),
)


def counted_length(password):
    """How many characters count. Spaces never count."""
    return sum(1 for ch in str(password or "") if not ch.isspace())


def _clean(text):
    return "".join(ch for ch in str(text or "").lower() if ch.isalnum())


def checklist(password, name="", email="", minimum=MIN_LENGTH):
    """Return {rule: True/False} for the four rules."""
    password = str(password or "")
    flat = _clean(password)
    local = _clean(str(email or "").split("@")[0])
    words = [_clean(part) for part in str(name or "").split()]
    uses_identity = (len(local) >= 3 and local in flat) or any(len(word) >= 3 and word in flat for word in words)
    size = counted_length(password)
    return {
        "length": minimum <= size <= MAX_LENGTH and len(password) <= MAX_LENGTH,
        "identity": not uses_identity,
        "letter": any(ch.isupper() for ch in password) and any(ch.islower() for ch in password),
        "mix": any(ch.isdigit() for ch in password) and any(not ch.isalnum() and not ch.isspace() for ch in password),
    }


def first_problem(password, name="", email="", minimum=MIN_LENGTH):
    """The first rule that fails, as a plain sentence, or None when the password is fine."""
    password = str(password or "")
    if counted_length(password) > MAX_LENGTH or len(password) > MAX_LENGTH:
        return f"Use {MAX_LENGTH} characters or fewer. Spaces do not count."
    result = checklist(password, name, email, minimum)
    for key, _label, sentence in RULES:
        if not result[key]:
            return sentence.format(n=minimum)
    return None
