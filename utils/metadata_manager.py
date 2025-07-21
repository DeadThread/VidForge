#!/usr/bin/env python3
# utils/metadata_manager.py
# -------------------------------------------------------------
from utils.ref_file_manager import normalize_name
from constants import FORMAT_LIST, ADDITIONAL_LIST  # ADDITIONAL_LIST used
import os
import json

# -------------------------------------------------------------
def build_normalized_map(raw_list):
    """Return {normalized: original} for quick lookups."""
    return {normalize_name(item): item for item in raw_list}

# -------------------------------------------------------------
def gather_meta(app):
    """Collect current GUI-entered metadata from the app widgets."""

    def safe_int(value, min_val=None, max_val=None):
        try:
            iv = int(value)
            if (min_val is not None and iv < min_val) or (max_val is not None and iv > max_val):
                return ""
            return str(iv)
        except Exception:
            return ""

    year  = safe_int(app.v_year.get(),  1900, 2100)
    month = safe_int(app.v_month.get(), 1,    12)
    day   = safe_int(app.v_day.get(),   1,    31)

    date_str = ""
    if app.v_override_date.get():
        if year and month and day:
            date_str = f"{year.zfill(4)}-{month.zfill(2)}-{day.zfill(2)}"
        elif year and month:
            date_str = f"{year.zfill(4)}-{month.zfill(2)}"
        elif year:
            date_str = year.zfill(4)

    return {
        "artist":     app.v_artist.get().strip(),
        "venue":      app.v_venue.get().strip(),
        "city":       app.v_city.get().strip(),
        "format":     app.v_format.get().strip(),
        "additional": app.v_add.get().strip(),
        "date":       date_str,
        "year":       year,
        "month":      month,
        "day":        day,
        "make_poster": app.v_make_poster.get(),
        "template":    app.v_template.get(),
        "template_folder": app.tpl_artist or "",
    }

# -------------------------------------------------------------
def save_cache(app):
    """Save updated format / additional histories to the cache."""
    from utils.cache_utils import cache_add_value
    from utils.cache_manager import save_cache as save_cache_file

    # Reset keys before adding to avoid duplicates
    app.cache["Format"] = []
    app.cache["Additional"] = []

    for fmt in app.format_history:
        cache_add_value(app.cache, "Format", fmt)

    for add in app.additionals_history:
        cache_add_value(app.cache, "Additional", add)

    save_cache_file(app.cache, log_func=lambda *args: None)

# -------------------------------------------------------------
def refresh_dropdowns(app):
    """
    Refresh all Combobox dropdown values.
    • Merges cached history with defaults (from app or constants).
    • Keeps the most‑recently‑used choice on top.
    """
    from utils.cache_utils import load_cache, cache_get_list  # local import

    def sorted_with_last_on_top(cb, vals, last_used):
        vals = list(dict.fromkeys(vals))  # unique, preserve order
        if last_used and last_used in vals:
            vals.remove(last_used)
            cb["values"] = [last_used] + vals
        else:
            cb["values"] = vals

    # Load cache
    app.cache = load_cache()
    hist_fmt = cache_get_list(app.cache, "Format")
    hist_add = cache_get_list(app.cache, "Additional")

    # Use app's loaded lists or fallback to constants
    default_formats = getattr(app, "format_list", FORMAT_LIST)
    default_additionals = getattr(app, "additional_list", ADDITIONAL_LIST)

    # Merge defaults with history (defaults first)
    app.format_history = default_formats + [f for f in hist_fmt if f not in default_formats]
    app.additionals_history = default_additionals + [a for a in hist_add if a not in default_additionals]

    # Update combobox dropdown values
    sorted_with_last_on_top(app.ent_add, app.additionals_history, app.v_add.get())
    sorted_with_last_on_top(app.ent_format, app.format_history, app.v_format.get())

    # Ensure the Format combobox always has a valid selection
    if app.v_format.get() not in app.ent_format["values"]:
        if app.ent_format["values"]:
            app.v_format.set(app.ent_format["values"][0])

    # Save updated cache values
    save_cache(app)

# -------------------------------------------------------------
def clear_fields(app):
    """Reset all entry fields and template selection."""
    for v in (
        app.v_artist, app.v_format, app.v_venue, app.v_city,
        app.v_add, app.v_year, app.v_month, app.v_day
    ):
        v.set("")
    app.v_template.set("Default")
    app.tpl_stage, app.tpl_artist = "folders", None

# -------------------------------------------------------------
def reload_metadata(app):
    """
    Refresh metadata lists from text files in assets/
    """
    def read_txt_lines(filename):
        try:
            with open(os.path.join(app.assets_dir, filename), "r", encoding="utf-8") as f:
                return [line.strip() for line in f if line.strip()]
        except Exception as e:
            app._log(f"Error reading {filename}: {e}")
            return []

    # 1. Re-read all metadata files
    artist_list = read_txt_lines("Artists.txt")
    city_list   = read_txt_lines("Cities.txt")
    venue_list  = read_txt_lines("Venues.txt")

    # 2. Update internal dictionaries
    app.artist = {normalize_name(a): a for a in artist_list}
    app.city   = {normalize_name(c): c for c in city_list}
    app.venue  = {normalize_name(v): v for v in venue_list}

    # 4. Update dropdowns
    app.cb_artist["values"] = artist_list
    app.cb_city["values"]   = city_list
    app.cb_venue["values"]  = venue_list

    # 5. Clear invalid selections
    if app.v_artist.get() not in artist_list:
        app.v_artist.set("")
    if app.v_city.get() not in city_list:
        app.v_city.set("")
    if app.v_venue.get() not in venue_list:
        app.v_venue.set("")

    app._log("Reference metadata refreshed from text files.")

# -------------------------------------------------------------
def extract_root_folder(path_pattern: str) -> str:
    """Extract root folder from a path pattern."""
    # Normalize slashes for consistent splitting
    normalized = path_pattern.replace("\\", "/")

    token_pos = normalized.find("%")
    if token_pos == -1:
        # no tokens, whole path is root
        return normalized.rstrip("/")

    # Take substring before first token (literal path)
    root = normalized[:token_pos].rstrip("/")
    return root

# -------------------------------------------------------------
def replace_tokens_in_path(path_template: str, md: dict, artist: str, date: str) -> str:
    """Replace tokens in the given path template with metadata."""
    year = md.get("year", "") or (date[:4] if date else "")
    month = md.get("month", "")
    day = md.get("day", "")

    date_tok = ""
    if year and month and day:
        date_tok = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
    elif year and month:
        date_tok = f"{year}-{month.zfill(2)}"
    elif year:
        date_tok = year

    repl = {
        "%artist%": artist,
        "%year%": year,
        "%date%": date_tok or date,
        "%venue%": md.get("venue", ""),
        "%city%": md.get("city", ""),
        "%format%": md.get("format", ""),
        "%additional%": md.get("additional", ""),
    }
    out = path_template
    for token, val in repl.items():
        out = out.replace(token, val)
    return out

def evaluate_output_folder(naming_scheme, output_dir, metadata):
    folder_template = naming_scheme.get("folder", "")
    if not folder_template:
        return output_dir or os.getcwd()
    folder_path = replace_tokens_in_path(folder_template, metadata, metadata.get("artist", ""), metadata.get("date", ""))
    if os.path.isabs(folder_path):
        return folder_path
    else:
        return os.path.normpath(os.path.join(output_dir, folder_path))

def get_live_metadata(app) -> dict:
    """Gather live metadata from the app fields with default values."""
    artist  = app.v_artist.get()  or "Phish"
    year    = app.v_year.get()    or "2025"
    month   = app.v_month.get()   or "06"
    day     = app.v_day.get()     or "20"
    date    = f"{year}-{month}-{day}"  # Construct the date string
    venue   = app.v_venue.get()   or "SNHU Arena"
    city    = app.v_city.get()    or "Manchester, NH"
    fmt     = app.v_format.get()  or "2160p"
    addl    = app.v_add.get()     or "SBD"
    raw_root = app.output_dir.get() or "(Root)"
    
    return {
        "artist":     artist,
        "date":       date,
        "venue":      venue,
        "city":       city,
        "format":     fmt,
        "additional": addl,
        "output_folder": raw_root,  # Ensure this is passed as well
    }

def _clean_root(path: str) -> str:
    """Clean up the root path."""
    if path in {"(Root)", ""}:
        return ""
    return path.removeprefix("(Root)/")

def _extract_root(pattern: str) -> str | None:
    """Extract the root folder from a pattern."""
    if not pattern:
        return None
    norm = pattern.replace("\\", "/")
    cuts = [p for p in (norm.find("%"), norm.find("$")) if p >= 0]
    root = norm[:min(cuts)] if cuts else norm
    root = root.rstrip("/")
    return root or None

