# utils/naming_renderer.py
import re
from datetime import datetime as _dt

_TOKEN_RE = re.compile(r"""
    %(\w+)%                 |   # %artist%
    \$year\(([^)]+)\)           # $year(date)  (captures inside the parentheses)
""", re.VERBOSE)

def render_scheme(scheme: str, meta: dict[str, str]) -> str:
    """Replace %tokens% and $year(date) with values from meta."""
    def _sub(m):
        token, year_arg = m.groups()

        # Plain %token%
        if token:
            return str(meta.get(token, f"<{token}>"))

        # $year(date) → pull year from meta['date'] unless overridden
        date_str = year_arg or meta.get("date")
        try:
            year = _dt.strptime(date_str, "%Y-%m-%d").year
        except Exception:
            year = str(date_str)[:4]  # crude fallback
        return str(year)

    return _TOKEN_RE.sub(_sub, scheme)
