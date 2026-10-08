"""Normalization and validation helpers for personnel identities."""

import re

_IDENTIFIER_PATTERN = re.compile(r"^[A-Z0-9](?:[A-Z0-9_/-]{0,48}[A-Z0-9])?$")
_PHONE_SEPARATORS = re.compile(r"[\s().-]+")


def normalize_person_name(value: str) -> str:
    """Collapse whitespace and reject names containing unsafe or implausible characters."""

    normalized = " ".join(value.strip().split())
    if len(normalized) < 2 or sum(character.isalpha() for character in normalized) < 2:
        raise ValueError("Enter a valid name containing at least two letters")
    if any(not (character.isalpha() or character in " '-.") for character in normalized):
        raise ValueError("Names may only contain letters, spaces, apostrophes, hyphens, and periods")
    return normalized


def normalize_personnel_code(value: str) -> str:
    """Return a canonical, comparison-safe employee or participant code."""

    normalized = value.strip().upper()
    if not 2 <= len(normalized) <= 50 or not _IDENTIFIER_PATTERN.fullmatch(normalized):
        raise ValueError(
            "Use 2-50 letters or numbers; hyphens, underscores, and slashes may appear between them"
        )
    return normalized


def normalize_phone_number(value: str) -> str:
    """Normalize Kenyan/local or international phone numbers to E.164 form."""

    raw = value.strip()
    if not raw:
        raise ValueError("Phone number is required")
    if raw.startswith("00"):
        raw = f"+{raw[2:]}"
    compact = _PHONE_SEPARATORS.sub("", raw)
    if compact.startswith("0") and compact[1:].isdigit() and len(compact) == 10:
        compact = f"+254{compact[1:]}"
    elif compact.startswith("254") and compact.isdigit() and len(compact) == 12:
        compact = f"+{compact}"
    if not re.fullmatch(r"\+[1-9]\d{7,14}", compact):
        raise ValueError("Enter a valid phone number, including the country code")
    if compact.startswith("+254") and not re.fullmatch(r"\+254[17]\d{8}", compact):
        raise ValueError("Enter a valid Kenyan mobile number")
    return compact
