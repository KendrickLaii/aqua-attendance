"""Helpers for safe SQL LIKE / ILIKE patterns."""


def escape_ilike(term: str) -> str:
    """Escape ``%``, ``_``, and ``\\`` for use with SQLAlchemy ``.ilike(..., escape='\\\\')``."""
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def ilike_contains(column, term: str):
    """Case-insensitive contains match with wildcard characters escaped."""
    pattern = f"%{escape_ilike(term.strip())}%"
    return column.ilike(pattern, escape="\\")
