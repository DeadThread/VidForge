#!/usr/bin/env python3
# utils/metadata_manager.py
# -------------------------------------------------------------
from utils.ref_file_manager import normalize_name
from constants import FORMAT_LIST, ADDITIONAL_LIST  # ADDITIONAL_LIST used

# -------------------------------------------------------------
def build_normalized_map(raw_list):
    """Return {normalized: original} for quick‑ups."""
    return {normalize_name(item): item for item in raw_list}

# -------------------------------------------------------------
def gather_meta(app):
    """Collect current GUI‑entered metadata from the app widgets."""

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
