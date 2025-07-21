from __future__ import annotations
import os
from typing import Dict, List, Optional
import logging
import random
from tkinter import messagebox, filedialog

__all__ = ["scan_templates", "choose_psd", "update_template_dropdown", "on_template_selected"]

log = logging.getLogger("vidforge")


def scan_templates(root: str) -> Dict[str, List[str]]:
    """
    Walk the <root> directory and return a dict mapping:
      { artist_or_generic_folder_name: [sorted list of PSD filenames] }

    Only first-level subfolders are scanned. PSD files directly under root or in
    deeper subfolders are ignored.
    """
    tpl_map: Dict[str, List[str]] = {}

    for dirpath, _, files in os.walk(root):
        rel_path = os.path.relpath(dirpath, root)
        path_parts = rel_path.split(os.sep)

        # Skip PSD files directly inside root or subfolders deeper than first-level
        if rel_path == ".":
            continue

        if len(path_parts) != 1:
            continue  # skip deeper than first-level folders

        folder_name = path_parts[0]

        # Filter PSD files in this folder
        psd_files = sorted(f for f in files if f.lower().endswith(".psd"))

        if psd_files:
            tpl_map[folder_name] = psd_files
            log.debug(f"Found {len(psd_files)} PSD(s) in folder '{folder_name}'")

    total_psds = sum(len(files) for files in tpl_map.values())
    log.info(f"Template scan complete: {total_psds} PSD(s) in {len(tpl_map)} folders")
    for folder, psds in tpl_map.items():
        log.debug(f"Template folder '{folder}': {psds}")

    return tpl_map


def update_template_dropdown(app):
    """
    Update the app's template dropdown to show:
    - Top-level entries: Default, Random, then Artist folders
    - If an artist folder is selected, show its PSD files with a '← Back' and 'Random' option

    Uses app._current_mode and app._current_artist to determine the view.

    Assumes the following exist on app:
    - tpl_map (dict[str, list[str]])
    - cb_template (ttk.Combobox)
    - v_template (tk.StringVar)
    - _current_mode (str): "top" or "psd"
    - _current_artist (str or None)
    """
    TOP = "top"
    PSD = "psd"

    if not hasattr(app, "_current_mode") or not hasattr(app, "_current_artist"):
        # Initialize mode if missing
        app._current_mode = TOP
        app._current_artist = None

    if app._current_mode == TOP:
        # Top-level: Default, Random, artist folders
        artist_folders = sorted(app.tpl_map.keys())
        values = ["Default", "Random"] + artist_folders
        app.cb_template["values"] = values
        # Reset selection if invalid
        if app.v_template.get() not in values:
            app.v_template.set("Default")

    elif app._current_mode == PSD and app._current_artist:
        # PSD-level: ← Back, Random, PSD files for selected artist
        psds = app.tpl_map.get(app._current_artist, [])
        values = ["← Back", "Random"] + psds
        app.cb_template["values"] = values
        if app.v_template.get() not in values:
            app.v_template.set("Random")

    else:
        # Fallback: reset to top-level
        app._current_mode = TOP
        app._current_artist = None
        update_template_dropdown(app)  # recursive call to set correctly


def _normalize(s: str) -> str:
    return "".join(c for c in s.lower() if c.isalnum())


def choose_psd(
    poster_artist: str,
    template_sel: str,
    template_folder: Optional[str],
    tpl_map: Dict[str, List[str]],
    templates_root: str,
    generic_key: str = "Generic",
) -> Optional[str]:
    """
    Return the *absolute* PSD path to use, or None to skip.
    """

    norm_artist = _normalize(poster_artist)
    log.debug(f"choose_psd called with poster_artist={poster_artist} (normalized={norm_artist})")
    log.debug(f"Available template folders: {list(tpl_map.keys())}")

    # If the user selected an explicit PSD filename (not Default, Random, or ← Back)
    if template_sel not in ("Default", "Random", "← Back"):
        folder = template_folder or poster_artist
        candidate = os.path.join(templates_root, folder, template_sel)
        if os.path.isfile(candidate):
            return candidate
        log.warning(f"Template not found: {candidate}")
        return None

    # Random selection
    if template_sel == "Random":
        folder_to_use = template_folder or generic_key
        if folder_to_use in tpl_map and tpl_map[folder_to_use]:
            chosen_psd = random.choice(tpl_map[folder_to_use])
            log.debug(f"Randomly picked PSD '{chosen_psd}' from folder '{folder_to_use}'")
            return os.path.join(templates_root, folder_to_use, chosen_psd)
        else:
            # fallback to generic_key
            if generic_key in tpl_map and tpl_map[generic_key]:
                chosen_psd = random.choice(tpl_map[generic_key])
                log.debug(f"Fallback random pick PSD '{chosen_psd}' from '{generic_key}'")
                return os.path.join(templates_root, generic_key, chosen_psd)
            log.warning("No templates available for random selection.")
            return None

    # Default selection: try to match artist folder by normalized name
    for artist_folder in tpl_map:
        if artist_folder == generic_key:
            continue
        norm_folder = _normalize(artist_folder)
        if norm_folder == norm_artist:
            psd = tpl_map[artist_folder][0]
            log.debug(f"Matched artist folder '{artist_folder}' with PSD '{psd}'")
            return os.path.join(templates_root, artist_folder, psd)

    # Fall back to Generic if no match found
    if generic_key in tpl_map and tpl_map[generic_key]:
        psd = tpl_map[generic_key][0]
        log.debug(f"No artist match found, falling back to generic PSD '{psd}'")
        return os.path.join(templates_root, generic_key, psd)

    log.warning("No suitable PSD found (even Generic missing).")
    return None

def _load_template_from_path(app, path):
    """Load template from given path."""
    app._log(f"Loading template from: {path}")
    # TODO: Implement actual loading of the PSD template