import os
import tkinter as tk
from tkinter import ttk
from utils.metadata_manager import reload_metadata
from utils.theme_manager import select_and_load_theme
from constants import CONFIG_FILE
from utils.file_helpers import _browse, _open_txt_file
from utils.tree_manager import fast_populate_tree as populate_tree

def build_menu_bar(app):
    """Builds the menu bar for the application."""
    menubar = tk.Menu(app)
    app.config(menu=menubar)

    # ── File ─────────────────────────────────
    file_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="File", menu=file_menu)
    file_menu.add_command(
        label="Open Root Folder",
        command=lambda: _browse(app)  # Changed to use _browse from file_helpers
    )

    # ── Edit ────────────────────────────────
    edit_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="Edit", menu=edit_menu)
    edit_menu.add_command(
        label="Edit Artists.txt",
        command=lambda: _open_txt_file(app.assets_dir, "Artists.txt")
    )
    edit_menu.add_command(
        label="Edit Cities.txt",
        command=lambda: _open_txt_file(app.assets_dir, "Cities.txt")
    )
    edit_menu.add_command(
        label="Edit Venues.txt",
        command=lambda: _open_txt_file(app.assets_dir, "Venues.txt")
    )
    edit_menu.add_separator()
    edit_menu.add_command(
        label="Change Naming Scheme",
        command=lambda: app.open_naming_scheme_editor(app.naming_scheme)
    )
    edit_menu.add_command(label="Reset Naming Scheme to Default",
                        command=lambda: reset_naming_scheme_from_menu(app))

    # Add this line inside the Edit menu:
    edit_menu.add_separator()  # optional, to separate nicely
    edit_menu.add_command(label="Edit Artist Aliases",
                        command=lambda: app.open_alias_editor())

    # ── View ────────────────────────────────
    view_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="View", menu=view_menu)

    THEMES_DIR = os.path.join(os.getcwd(), "themes")
    view_menu.add_command(
        label="Select Theme",
        command=lambda: select_and_load_theme(
            app,
            app.config_parser,
            CONFIG_FILE,
            THEMES_DIR,
            app._log,
        )
    )
    view_menu.add_command(label="Use Default Theme", command=app._remove_theme)

    # ── Tools ───────────────────────────────
    tools_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="Tools", menu=tools_menu)
    tools_menu.add_command(label="Select Photoshop Location", command=app._select_photoshop_location)
    tools_menu.add_command(label="Re-scan Template Folder", command=app._scan_templates)

    # Add the Refresh Metadata command (calls reload_metadata from utils/metadata_manager.py)
    tools_menu.add_separator()
    tools_menu.add_command(label="Refresh Metadata", command=lambda: reload_metadata(app))

    # ── Help ────────────────────────────────
    help_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="Help", menu=help_menu)
    help_menu.add_command(label="Read Me", command=app._open_readme)
    help_menu.add_command(label="Useful Tips", command=app._open_tips)

    # Top bar (root path) section
    top = ttk.Frame(app)
    top.pack(fill="x", padx=4, pady=4)
    ttk.Label(top, text="Root Folder:").pack(side="left")
    style = ttk.Style(app)
    style.configure("Root.TEntry", padding=(4, 2), relief="flat")
    ttk.Entry(top, textvariable=app.root_dir, width=80,
              state="readonly", style="Root.TEntry").pack(side="left", fill="x", expand=True)
    ttk.Button(top, text="Browse", command=lambda: _browse(app)).pack(side="left", padx=4)
    ttk.Button(top, text="Refresh", command=lambda: populate_tree(app, app.root_dir.get())).pack(side="left", padx=4)

    return menubar
