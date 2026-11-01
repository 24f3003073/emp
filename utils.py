import re
from datetime import date, datetime, time


class ApiError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


def require(data, *fields):
    """Raise ApiError if any field is missing or blank."""
    if not isinstance(data, dict):
        raise ApiError("JSON body required")
    missing = [f for f in fields if data.get(f) in (None, "")]
    if missing:
        raise ApiError("Missing required field(s): " + ", ".join(missing))


def as_int(value, label, minimum=None):
    try:
        v = int(value)
    except (TypeError, ValueError):
        raise ApiError(f"{label} must be a whole number")
    if minimum is not None and v < minimum:
        raise ApiError(f"{label} must be at least {minimum}")
    return v


def as_float(value, label, minimum=None):
    try:
        v = float(value)
    except (TypeError, ValueError):
        raise ApiError(f"{label} must be a number")
    if minimum is not None and v < minimum:
        raise ApiError(f"{label} must be at least {minimum}")
    return v


def parse_date(value):
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        raise ApiError("Dates must be in YYYY-MM-DD format")


def parse_time(value):
    s = str(value)
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).time()
        except ValueError:
            continue
    raise ApiError("Times must be in HH:MM format")


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def valid_email(email):
    return bool(EMAIL_RE.match(email or ""))


def iso(d):
    if isinstance(d, (date, datetime)):
        return d.isoformat()
    if isinstance(d, time):
        return d.strftime("%H:%M")
    return d
