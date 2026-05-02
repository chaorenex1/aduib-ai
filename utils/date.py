import datetime


def now_local() -> datetime.datetime:
    """Return the current local timezone-aware datetime."""
    return datetime.datetime.now().astimezone()

