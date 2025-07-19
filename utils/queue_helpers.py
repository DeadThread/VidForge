"""
utils.queue_helpers
───────────────────
All helpers that touch the queue‑tree, caching, and path/filename
evaluation.  Nothing else in the codebase imports this module except
**VidForge.py**, so you can edit freely here without breaking other
utilities.
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from tkinter import messagebox
from typing import Dict, List

import tkinter as tk

from utils.cache_manager import load_cache, cache_add_value, cache_get_list
from utils.metadata_manager import gather_meta
from utils.ref_file_manager import add_to_reference

logger = logging.getLogger("vidforge")

# ──────────────────────────────────────────────────────────────────────
# 1.  Template evaluator
# ──────────────────────────────────────────────────────────────────────
class SchemeEvaluator:
    """
    Substitute %tokens% (and a few $functions()) in a template string.

    • Supported %tokens% (case‑sensitive):
        %artist%  %venue%  %date%  %city%  %format%  %additional%

    • $year(date)   → four‑digit year pulled from meta['year']
      (you can add more $funcs later if needed).

    • %date% is produced from y/m/d parts if present.  Empty tokens are
      removed neatly (no leftover “[]”, doubled separators, etc.).
    """

    _TOKEN_KEYS = (
        "artist",
        "venue",
        "date",
        "city",
        "format",
        "additional",
    )

    def __init__(self, meta: Dict[str, str] | None):
        self.meta = meta or {}

    # ------------------------------------------------------------------
    def _build_date(self) -> str:
        """Return YYYY‑MM‑DD / YYYY‑MM / YYYY (or '') depending on meta."""
        y = self.meta.get("year", "").strip()
        m = self.meta.get("month", "").strip()
        d = self.meta.get("day", "").strip()
        if y and m and d:
            return f"{y}-{m.zfill(2)}-{d.zfill(2)}"
        if y and m:
            return f"{y}-{m.zfill(2)}"
        return y

    # ------------------------------------------------------------------
    def evaluate(self, template: str) -> str:
        if not template:
            return ""

        # ── token → value table ───────────────────────────────────────
        date_str = self._build_date()
        replacements = {
            "%artist%":     self.meta.get("artist", "").strip(),
            "%venue%":      self.meta.get("venue", "").strip(),
            "%date%":       date_str,
            "%city%":       self.meta.get("city", "").strip(),
            "%format%":     self.meta.get("format", "").strip(),
            "%additional%": self.meta.get("additional", "").strip(),
        }

        # ── literal %token% replacement ───────────────────────────────
        out = template
        for ph, value in replacements.items():
            out = out.replace(ph, value)

        # ── simple $functions() ───────────────────────────────────────
        #   currently only $year(date) is needed
        def repl_year(match: re.Match) -> str:
            # match.group(1) == 'date' but kept generic for future use
            return self.meta.get("year", "").strip()

        out = re.sub(r"\$year\(\s*date\s*\)", repl_year, out, flags=re.I)

        # ── tidy pass ────────────────────────────────────────────────
        out = re.sub(r"\[\s*]", "", out)           # empty [...]
        out = re.sub(r"\s{2,}", " ", out)          # duplicate spaces
        out = re.sub(r"(?:\s*-\s*){2,}", " - ", out)  # repeated ' - '
        out = out.strip(" -")                      # leading/trailing seps
        return out


# ──────────────────────────────────────────────────────────────────────
# 2.  Resolve full output folder
# ──────────────────────────────────────────────────────────────────────
def _folder_template_from_scheme(naming_scheme) -> str:
    """
    Extract ``folder`` template from naming_scheme, tolerant of:
       • dict   → naming_scheme["folder"]
       • JSON   → json.loads(str)["folder"]
       • other  → fallback
    """
    default = "%artist%/$year(date)"
    if isinstance(naming_scheme, dict):
        return naming_scheme.get("folder", default)
    if isinstance(naming_scheme, str):
        try:
            return json.loads(naming_scheme).get("folder", default)
        except Exception:
            return default
    return default


def get_full_output_folder(app, meta: dict) -> str:
    """Return absolute folder path for this file, given current scheme."""
    base_folder = (app.output_dir.get() or "").strip() or \
                  (os.path.dirname(app.current_fp) if app.current_fp else os.getcwd())

    folder_tpl = _folder_template_from_scheme(app.naming_scheme)
    evaluated  = SchemeEvaluator(meta).evaluate(folder_tpl)

    logger.debug("base_folder          : %s", base_folder)
    logger.debug("folder_tpl           : %s", folder_tpl)
    logger.debug("evaluated folder tpl : %s", evaluated)

    return os.path.normpath(evaluated if os.path.isabs(evaluated)
                            else os.path.join(base_folder, evaluated))


# ──────────────────────────────────────────────────────────────────────
# 3.  Queue‑tree helpers VidForge imports
# ──────────────────────────────────────────────────────────────────────
def save_current(app):
    """Called by the Save / Add‑to‑Queue button in the main window."""
    if not app.current_fp:
        messagebox.showinfo("No file", "Pick a video file first.")
        return

    # gather meta --------------------------------------------
    meta = gather_meta(app)
    meta["override_date"] = bool(getattr(app, "v_override_date", tk.IntVar()).get())

    app.meta[app.current_fp] = meta  # save per‑file in app state

    # keep .txt ref lists fresh -------------------------------
    for cat in ("artist", "venue", "city", "additional"):
        val = meta.get(cat, "").strip()
        if val:
            add_to_reference(cat, val, app.artist, app.venue, app.city, app.hist["additional"])

    # output‑folder logic -------------------------------------
    meta["output_folder_base"] = app.output_dir.get().strip()
    meta["full_output_folder"] = get_full_output_folder(app, meta)
    app._log(f"Output folder → {meta['full_output_folder']}")

    # build proposed filename --------------------------------
    if isinstance(app.naming_scheme, dict):
        fname_tpl = app.naming_scheme.get("filename", "%artist% - %date%")
    else:
        try:
            fname_tpl = json.loads(app.naming_scheme).get("filename", "%artist% - %date%")
        except Exception:
            fname_tpl = app.naming_scheme  # legacy flat string

    proposed_name = SchemeEvaluator(meta).evaluate(fname_tpl)
    original_name = os.path.basename(app.current_fp)

    # queue‑tree update --------------------------------------
    if app.current_fp not in app.queue:
        app.queue.append(app.current_fp)
        app.queue_tree.insert("", "end", values=(original_name, proposed_name))
    else:
        for item in app.queue_tree.get_children():
            vals = app.queue_tree.item(item, "values")
            if vals and vals[0] == original_name:
                app.queue_tree.item(item, values=(original_name, proposed_name))
                break

    app._log(f"Queued: {original_name}  →  {proposed_name}")

    # cache history ------------------------------------------
    if meta.get("format"):
        cache_add_value(app.cache, "Format", meta["format"])  # singular key
    if meta.get("additional"):
        cache_add_value(app.cache, "Additional", meta["additional"])  # singular key
        
    meta = gather_meta(app)
    print(f"[DEBUG save_current] format raw: {repr(meta.get('format'))}")
    print(f"[DEBUG save_current] additional raw: {repr(meta.get('additional'))}")


def remove_selected(app):
    """Remove selected rows from the queue & internal structures."""
    for item in app.queue_tree.selection():
        orig_name = app.queue_tree.item(item, "values")[0]
        for path in list(app.queue):
            if Path(path).name == orig_name:
                app.queue.remove(path)
                app.meta.pop(path, None)
        app.queue_tree.delete(item)
        app._log(f"Removed: {orig_name}")


def clear_queue(app):
    """Complete wipe of queue & metadata."""
    app.queue.clear()
    app.meta.clear()
    for item in app.queue_tree.get_children():
        app.queue_tree.delete(item)
    app._log("Queue cleared.")


# ──────────────────────────────────────────────────────────────────────
# 4.  Cache bootstrap (call once at app start)
# ──────────────────────────────────────────────────────────────────────
def initialize_cache(app):
    """Load persistent history (Format, Additional) into the app instance."""
    app.cache               = load_cache()
    app.formats_history     = cache_get_list(app.cache, "Format")       # singular key
    app.additionals_history = cache_get_list(app.cache, "Additional")   # singular key
