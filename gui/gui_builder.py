#!/usr/bin/env python3
import json
import os
import random
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from constants import CONFIG_FILE, ASSETS_DIR, FORMAT_LIST, ADDITIONAL_LIST, SAMPLE_META, CACHE_FILE, CACHE_DROPDOWN_FILE, TXT_FILES
from gui.build_additional import build_additional
from gui.build_folder_tree import build_folder_tree  # Import the build_folder_tree function
from gui.build_date import build_date
from gui.build_format import build_format
from gui.build_menu_bar import build_menu_bar
from gui.build_metadata import build_metadata
from gui.gui_build_queue import setup_queue_tree
from gui.gui_build_logs import setup_log_panel
from gui.gui_helpers import setup_autocomplete, setup_custom_tab_order, setup_context_menu, prompt_photoshop_path_if_first_boot
from gui.menu_actions import rename_item, delete_item, open_item, open_file_location, setup_tree_context_menu
from gui.naming_scheme_helpers import (
    get_naming_scheme_from_config,
    _clean_root,
    _extract_root,
    handle_special_tokens,
    get_live_metadata,
    save_naming_scheme,
    reset_naming_scheme_from_menu
)
from gui.template_dropdown import build_template_dropdown, _select_random_template, build_template_dropdown_values
from utils.cache_manager import (
    load_naming_scheme,
    load_cache,
    cache_get_list,
    load_format_values,
    load_additional_values,
    save_selected_files,
    load_dropdown_cache,
    save_dropdown_cache
)
from utils.evaluator import Evaluator
from utils.file_helpers import _browse, _open_txt_file
from utils.pane_persistence import install_pane_persistence
from utils.queue_helpers import save_current, remove_selected, clear_queue, initialize_cache
from utils.template_manager import choose_psd, _load_template_from_path
from utils.theme_manager import select_and_load_theme
from utils.tree_manager import fast_populate_tree as populate_tree
from utils.metadata_manager import clear_fields, reload_metadata

# ───────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = PROJECT_ROOT / "assets" / "Photoshop Templates"
GENERIC_DIR  = TEMPLATE_DIR / "Generic"

# ───────────────────────────────────────────────────────────────────────
#                       cached dropdown helpers
# ───────────────────────────────────────────────────────────────────────

# Directly use the functions from cache_manager.py
cache = load_cache()

# Ensure the app is initialized here before using the naming scheme functions
def initialize_app():
    """Initialize the Tkinter app window."""
    app = tk.Tk()  # Create the Tkinter root window if not created elsewhere
    # Initialize any other components here
    return app

# ═══════════════════════════════════════════════════════════════════════
#                        naming‑scheme helpers
# ═══════════════════════════════════════════════════════════════════════

# Setup naming scheme
def setup_naming_scheme(app):
    """Set up the naming scheme for the app."""
    naming_scheme = get_naming_scheme_from_config(app)
    reset_naming_scheme_from_menu(app)

# ───────────────────────────────────────────────────────────────────────
# Now you can call the setup_naming_scheme function within your GUI builder
def build_gui(app) -> None:
    """Build the entire VidForge window: menus, metadata, file tree, etc."""
    # Initialize app and setup naming scheme
    setup_naming_scheme(app)
    initialize_cache(app)

    # ─────────────── Menu bar & Root Folder ────────────────
    menubar = build_menu_bar(app)
    app.config(menu=menubar)

    # ─────────────── Main paned window (LEFT / RIGHT) ────────────────
    app.main = ttk.PanedWindow(app, orient="horizontal")
    app.main.pack(fill="both", expand=True)
    left = tk.Frame(app.main)
    right = tk.Frame(app.main)
    app.main.add(left, weight=3)
    app.main.add(right, weight=2)

    # ─────────────── Metadata pane ────────────────
    meta = tk.Frame(left)  # Define 'meta' before using it
    meta.pack(fill="x", pady=(0, 2))
    build_metadata(meta, app)

    # ───────────────── FORMAT setup (row 1, columns 2-4) ─────────────────
    build_format(app, meta)

    # ───────────── ADDITIONAL setup (row 2, columns 2-4) ─────────────
    build_additional(app, meta, ADDITIONAL_LIST)

    # --- Date widgets (row 0, columns 2 and 3) -----------------------------------------
    build_date(meta, app)

    # ───────────── Make Poster & Template Dropdown ─────────────
    build_template_dropdown(app, meta)


    # ─────────────── LEFT vertical PanedWindow (files / queue) ────────────────
    app.left_pane = ttk.PanedWindow(left, orient="vertical"); app.left_pane.pack(fill="both", expand=True)
    app.files_frame = tk.Frame(app.left_pane)
    app.frame_queue = tk.Frame(app.left_pane)        # CHANGED – only one queue pane
    app.left_pane.add(app.files_frame,     weight=2)
    app.left_pane.add(app.frame_queue, weight=1)

    tk.Label(app.files_frame, text="Video Files:").pack(anchor="w")

    # ───── persist both splitters ─────
    install_pane_persistence(app.left_pane, app.config_parser, str(CONFIG_FILE),
                            section="Panes", option="video_queue_split", log_func=app._log)
    install_pane_persistence(app.main,      app.config_parser, str(CONFIG_FILE),
                            section="Panes", option="left_right_split", log_func=app._log)


    # ────────────────────────── Folder Tree ─────────────────────────
    build_folder_tree(app)  # This replaces the old tree + scrollbar code

    # ───────────────────────── Buttons row ────────────────────────────────
    btn_row = tk.Frame(left)
    btn_row.pack(anchor="w", pady=4)

    ttk.Button(btn_row, text="Save Selected",
            command=lambda: save_selected_files(app)).pack(side="left", padx=4)
    ttk.Button(btn_row, text="Process Queue",
            command=app._process_queue).pack(side="left", padx=4)
    ttk.Button(btn_row, text="Remove Selected",
            command=lambda: remove_selected(app)).pack(side="left", padx=4)
    ttk.Button(btn_row, text="Clear Queue",
            command=lambda: clear_queue(app)).pack(side="left", padx=4)

    # ─────────────── Queue tree inside app.frame_queue ────────────────
    setup_queue_tree(app)

    # ─────────────── Log panel on the right ────────────────
    setup_log_panel(right, app)

    # ─────────────── Autocomplete, multi‑select, tab‑order (unchanged) ────────────────
    setup_autocomplete(app)

    # ───────────────────────── Context-menu helpers ───────────────────────
    setup_context_menu(app)

    # ───────────────────────── Prompt Photoshop First Boot ───────────────────────
    prompt_photoshop_path_if_first_boot(app)

    # Use build_template_dropdown_values to construct the dropdown values
    dropdown_values = build_template_dropdown_values(app)
