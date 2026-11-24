"""Portable upload references, restricted to the application's upload directory."""
from pathlib import Path, PureWindowsPath
from users import DomainError


def resolve_upload(directory, reference, must_exist=False):
    root = Path(directory).resolve()
    if not isinstance(reference, str) or not reference.strip():
        raise DomainError("This image is unavailable.", 404)
    windows = PureWindowsPath(reference)
    original = Path(reference)
    # Earlier releases saved absolute paths. Use the local filename after a move.
    if original.is_absolute() or windows.is_absolute():
        relative = windows.name if "\\" in reference else original.name
    else:
        if "\\" in reference or ".." in original.parts:
            raise DomainError("This image reference is invalid.", 404)
        relative = reference
    target = (root / relative).resolve()
    if not target.is_relative_to(root):
        raise DomainError("This image reference is invalid.", 404)
    if must_exist and not target.is_file():
        raise DomainError("A required image is missing. Restore the required image before continuing.", 404)
    return target
