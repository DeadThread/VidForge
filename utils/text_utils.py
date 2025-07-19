import os
import re
import time
import logging
import json
from datetime import datetime
from typing import Optional, Dict, List, Tuple
from constants import STATE_ABBR, RES_RE, ADDITIONAL_LIST, FORMAT_LIST
from utils.helpers import CITY_STATE_RE

logger = logging.getLogger("vidforge")

TOKEN_SPLIT_RE = re.compile(r"[^\w']+")
STATE_SET = {s.lower() for s in STATE_ABBR}

CACHE_PATH = os.path.join("config", "normalized_cache.json")

# Load normalize cache safely
try:
    with open(CACHE_PATH, "r", encoding="utf-8") as f:
        _normalize_cache: Dict[str, str] = json.load(f)
    logger.info(f"Loaded normalize cache from {CACHE_PATH} ({len(_normalize_cache)} entries)")
except (FileNotFoundError, json.JSONDecodeError):
    _normalize_cache = {}
    logger.info("No valid normalize cache found, starting fresh")

def save_normalize_cache() -> None:
    try:
        os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(_normalize_cache, f)
        logger.info(f"Saved normalize cache to {CACHE_PATH}")
    except Exception as e:
        logger.error(f"Failed to save normalize cache: {e}")

def normalize_name(s: str) -> str:
    if s in _normalize_cache:
        return _normalize_cache[s]
    out = re.sub(r"[^\w]", "", s.lower())
    _normalize_cache[s] = out
    return out

def split_tokens(txt: str) -> List[str]:
    t = [x for x in TOKEN_SPLIT_RE.split(txt.lower()) if x]
    logger.debug("split_tokens(%r) -> %s", txt, t)
    return t

def extract_date(text: str) -> str:
    date_patterns = [
        (re.compile(r"(\d{4})[-./](\d{2})[-./](\d{2})"), "%Y-%m-%d"),
        (re.compile(r"(\d{2})[-./](\d{2})[-./](\d{4})"), "%m-%d-%Y"),
        (re.compile(r"(\d{2})[-./](\d{2})[-./](\d{2})"), "%y-%m-%d"),
    ]
    for pat, fmt in date_patterns:
        m = pat.search(text)
        if m:
            try:
                out = datetime.strptime("-".join(m.groups()), fmt).strftime("%Y-%m-%d")
                logger.debug("extract_date(%r) -> %r", text, out)
                return out
            except Exception:
                continue
    logger.debug("extract_date(%r) -> ''", text)
    return ""

def match_venue(base: str, venues: Dict[str, str]) -> str:
    norm_base = normalize_name(base)
    # Exact match
    if norm_base in venues:
        logger.debug("Matched venue exactly: %s", venues[norm_base])
        return venues[norm_base]
    # Substring match
    for k, v in venues.items():
        if k in norm_base:
            logger.debug("Matched venue substring: %s", v)
            return v
    # Window match (up to 4 words)
    toks = re.split(r"[.\s_\-]+", base)
    for w in range(4, 0, -1):
        for i in range(len(toks) - w + 1):
            chunk = " ".join(toks[i : i + w])
            norm_chunk = normalize_name(chunk)
            if norm_chunk in venues:
                logger.debug("Matched venue window: %s", venues[norm_chunk])
                return venues[norm_chunk]
    return ""

def match_city(base: str, cities: Dict[str, str]) -> str:
    norm_base = normalize_name(base)
    if norm_base in cities:
        logger.debug("Matched city exactly: %s", cities[norm_base])
        return cities[norm_base]

    # city,state fallback regex
    m = CITY_STATE_RE.search(base)
    if m:
        city = m.group("city").title()
        st = m.group("st").upper()

        # Try with comma first
        city_full = f"{city}, {st}"
        norm_city_full = normalize_name(city_full)
        if norm_city_full in cities:
            logger.debug("Matched city by city,state regex fallback: %s", cities[norm_city_full])
            return cities[norm_city_full]

        # Also try without comma and space (in case city.txt has no comma)
        city_full_no_comma = f"{city} {st}"
        norm_city_no_comma = normalize_name(city_full_no_comma)
        if norm_city_no_comma in cities:
            logger.debug("Matched city by city state no comma fallback: %s", cities[norm_city_no_comma])
            return cities[norm_city_no_comma]

        logger.debug("Discarded city,state regex fallback: %s (not in city list)", city_full)

    return ""
    
def match_format_and_additional(tokens: List[str]) -> Tuple[str, str]:
    format_candidates = []
    additional_candidates = []
    format_set = set(f.lower() for f in FORMAT_LIST)

    # Build dict of lowercase additional -> original capitalization
    additional_map = {a.lower(): a for a in ADDITIONAL_LIST}

    for t in tokens:
        t_lower = t.lower()

        # Format match (exact or e.g. 2160p)
        if re.match(r"^\d{3,4}p$", t_lower) or t_lower in format_set:
            if t not in format_candidates:
                format_candidates.append(t)
        else:
            # Substring match for additional, case-insensitive
            for add_lower, add_orig in additional_map.items():
                if add_lower in t_lower:
                    if add_orig not in additional_candidates:
                        additional_candidates.append(add_orig)
                    break

    return ", ".join(format_candidates), ", ".join(additional_candidates)


def infer_from_name(
    fname: str,
    artists: Dict[str, str],
    cities: Dict[str, str],
    venues: Dict[str, str],
    artist_aliases: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    # Normalize keys for artists and aliases
    artists_norm = {normalize_name(k): v for k, v in artists.items()}
    aliases_norm = {normalize_name(k): v for k, v in (artist_aliases or {}).items()}

    base = os.path.splitext(fname)[0]
    base_norm = normalize_name(base)

    info = {"artist": "", "date": "", "venue": "", "city": "", "format": "", "additional": ""}

    try:
        logger.debug(f"Attempting artist extraction from filename: '{base}'")

        # Extract date
        info["date"] = extract_date(base)

        # Extract venue
        venue = match_venue(base, venues)
        if venue:
            info["venue"] = venue

        # Extract city
        city = match_city(base, cities)
        if city:
            info["city"] = city

        # Tokenize base filename
        tokens = split_tokens(base)
        logger.debug(f"Filename tokens: {tokens}")

        # Match format and additional
        format_str, additional_str = match_format_and_additional(tokens)
        info["format"] = format_str
        info["additional"] = additional_str

        # Build exclusion set
        exclude_tokens = set()
        if info["date"]:
            exclude_tokens.update(split_tokens(info["date"]))
        if info["venue"]:
            exclude_tokens.update(split_tokens(info["venue"]))
        if info["city"]:
            exclude_tokens.update(split_tokens(info["city"]))
        exclude_tokens.update(t.lower() for t in format_str.split(", ") if t)
        exclude_tokens.update(t.lower() for t in additional_str.split(", ") if t)

        logger.debug(f"Tokens to exclude from artist: {exclude_tokens}")

        # -------- Artist Extraction --------
        found_artist = ""

        # 1. Exact normalized match from artists.txt
        for norm_artist, full_artist in artists_norm.items():
            if norm_artist in base_norm:
                found_artist = full_artist
                logger.debug(f"[ARTIST] Matched from artists.txt: '{norm_artist}' → '{full_artist}'")
                break
        else:
            logger.debug("[ARTIST] No match in artists.txt")

        # 2. If no match in artists.txt, check artist_aliases
        if not found_artist and aliases_norm:
            for norm_alias, full_artist in aliases_norm.items():
                if norm_alias in base_norm:
                    found_artist = full_artist
                    logger.debug(f"[ARTIST] Matched alias: '{norm_alias}' → '{full_artist}'")
                    break

        # 3. Fallback: use leftover tokens as artist name
        if not found_artist:
            candidate_artist_tokens = [t for t in tokens if t.lower() not in exclude_tokens]
            found_artist = " ".join(candidate_artist_tokens).title()
            logger.debug(f"[ARTIST] Fallback artist: '{base}' → '{found_artist}'")

        info["artist"] = found_artist

        logger.debug(f"Inferred info: {info}")
        return info

    except Exception as e:
        logger.error(f"[infer_from_name] Error while parsing '{fname}': {e}")
        return {"artist": "", "date": "", "venue": "", "city": "", "format": "", "additional": ""}
