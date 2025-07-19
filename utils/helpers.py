import os
import re
import time
import logging
from datetime import datetime
from constants import STATE_ABBR, RES_RE   # ← single source of truth

logger = logging.getLogger("vidforge")

# ----------------------------------------------------------------------
# compiled regexes that need the imported STATE_ABBR
TOKEN_SPLIT_RE = re.compile(r"[^\w']+")
CITY_STATE_RE = re.compile(
    r"(?P<city>[A-Za-z ]+)[,.\s]+(?P<st>[A-Za-z]{2})(?!\w)",
    re.IGNORECASE,
)
STATE_SET = {s.lower() for s in STATE_ABBR}
# ----------------------------------------------------------------------

def normalize_name(s: str) -> str:
    """Return a lowercase, alphanumeric‑only key for fuzzy matching."""
    return re.sub(r"[^\w]", "", s.lower())

def split_tokens(txt: str):
    """Break a string into lowercase word tokens (non‑word chars removed)."""
    return [x for x in TOKEN_SPLIT_RE.split(txt.lower()) if x]

def find_state(tok):
    """
    Look backwards through tokens to find a US‑state abbreviation.
    Returns (index_from_start, 'ST') or None.
    """
    for i, t in enumerate(tok):
        if t in STATE_SET:
            return i, t.upper()
    return None

def extract_date(text: str) -> str:
    """Return YYYY‑MM‑DD if a date pattern is found, else ''. """
    patterns = (
        (re.compile(r"(\d{4})[-./](\d{2})[-./](\d{2})"), "%Y-%m-%d"),
        (re.compile(r"(\d{2})[-./](\d{2})[-./](\d{4})"), "%m-%d-%Y"),
        (re.compile(r"(\d{2})[-./](\d{2})[-./](\d{2})"), "%y-%m-%d"),
    )
    for pat, fmt in patterns:
        m = pat.search(text)
        if m:
            try:
                return datetime.strptime("-".join(m.groups()), fmt)\
                               .strftime("%Y-%m-%d")
            except Exception:
                pass
    return ""

def extract_venue(base: str, venues: dict[str, str]) -> str:
    """
    Identify venue in file/folder name.

    Priority:
    1. Dashed slot (“Artist – Venue – …”)
    2. 4‑word → 1‑word sliding window match
    3. substring fallback
    4. ‘‘ if nothing recognised
    """
    def in_dict(cand: str) -> str:
        return venues.get(normalize_name(cand), "")
    # 1 – dash slot
    parts = [p.strip() for p in base.split(" - ")]
    if len(parts) >= 3:
        hit = in_dict(parts[2])
        if hit:
            return hit
    # 2 – window search
    tokens = re.split(r"[.\s_\-]+", base)
    for w in range(4, 0, -1):
        for i in range(len(tokens) - w + 1):
            chunk = " ".join(tokens[i:i + w])
            hit = in_dict(chunk)
            if hit:
                return hit
    # 3 – substring fallback
    norm_base = normalize_name(base)
    for k, v in venues.items():
        if k in norm_base:
            return v
    return ""

def infer_resolution(text: str) -> str:
    """Return '2160p', '1080p', etc. or ''. Uses RES_RE from constants."""
    m = RES_RE.search(text)
    return f"{m.group(1)}p" if m else ""

def touch(path, ymd=None, override=True, logger=None):
    """
    Update file's modified and accessed time.
    If ymd is None, uses current time.
    If override=False, does nothing.
    If logger provided, logs success/errors.
    """
    if not override:
        if logger:
            logger.debug(f"Override not enabled, skipping timestamp update for {path}")
        return

    try:
        if ymd:
            dt = datetime.strptime(ymd, "%Y-%m-%d")
            ts = dt.timestamp()
        else:
            ts = time.time()
        os.utime(path, (ts, ts))
        if logger:
            logger.debug(f"Updated modified date for {path} to {ymd or 'now'}")
    except Exception as e:
        if logger:
            logger.error(f"Error updating timestamp for {path}: {e}")