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


def build_proposed_name(meta: dict[str, str], scheme: str) -> str:
    """Old-style replacement using fixed tokens, fallback if no scheme tokens used."""
    year, month, day = meta.get("year", ""), meta.get("month", ""), meta.get("day", "")
    date_str = f"{year}-{month.zfill(2)}-{day.zfill(2)}" if (year and month and day) else ""

    name = scheme
    name = name.replace("ARTIST", meta.get("artist", ""))
    name = name.replace("VENUE",  meta.get("venue",  ""))
    name = name.replace("DATE",   date_str)
    name = name.replace("CITY",   meta.get("city",   ""))
    name = name.replace("[FORMAT]",     f"[{meta.get('format','')}]"     if meta.get("format")     else "")
    name = name.replace("[ADDITIONAL]", f"[{meta.get('additional','')}]" if meta.get("additional") else "")
    name = " ".join(name.split()).strip()

    for sep in (" - ", "--", "- -"):
        if name.startswith(sep): name = name[len(sep):]
        if name.endswith(sep):   name = name[:-len(sep)]

    return name
