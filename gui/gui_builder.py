#!/usr/bin/env python3
import sys
import os
import json
import shutil
import subprocess
import random
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk, filedialog

# Add parent directory to sys.path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Utils imports
from utils.template_manager import choose_psd
from utils.theme_manager import select_and_load_theme
from utils.metadata_manager import clear_fields
from utils.queue_helpers import save_current, remove_selected, clear_queue, initialize_cache
from utils.pane_persistence import install_pane_persistence
from utils.cache_manager import load_cache, cache_get_list

# Autocomplete and GUI imports
from autocomplete_tabnav import enable_inline_autocomplete, setup_global_tab_order
from gui.naming_editor import NamingEditor, SAMPLE_META

# Constants
from constants import CONFIG_FILE, ASSETS_DIR, FORMAT_LIST, ADDITIONAL_LIST

# Tree manager import - using fast_populate_tree alias as populate_tree
from utils.tree_manager import fast_populate_tree as populate_tree

# ───────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = PROJECT_ROOT / "assets" / "Photoshop Templates"
GENERIC_DIR  = TEMPLATE_DIR / "Generic"
# ═══════════════════════════════════════════════════════════════════════
#                       cached dropdown helpers
# ═══════════════════════════════════════════════════════════════════════
cache                = load_cache()
DEFAULT_FORMATS      = FORMAT_LIST
DEFAULT_ADDITIONALS  = ADDITIONAL_LIST



def load_format_values() -> list[str]:
    cached = cache_get_list(cache, "Format")
    merged = list(DEFAULT_FORMATS)
    for fmt in cached:
        if fmt not in merged:
            merged.append(fmt)
    return merged

def load_additional_values() -> list[str]:
    vals = cache_get_list(cache, "Additional")
    return vals if vals else DEFAULT_ADDITIONALS

def _load_template_from_path(app, path):
    # Placeholder: implement loading logic here
    app._log(f"Loading template from: {path}")
    # TODO: implement actual loading of the PSD template


def save_selected_files(app):
    selected_ids = app.tree.selection()
    if not selected_ids:
        app._log("No files selected to add to the queue.")
        return

    for item_id in selected_ids:
        file_path = app.tree.set(item_id, "filepath")
        if not file_path:
            continue
        app.current_fp = file_path  # set current file context
        save_current(app)           # call your existing queue_helpers save_current()


# ═══════════════════════════════════════════════════════════════════════
#                        naming‑scheme helpers
# ═══════════════════════════════════════════════════════════════════════
def get_naming_scheme_from_config(app):
    """Read naming_scheme from config → return dict or raw string."""
    try:
        scheme_str = app.config_parser.get("Settings", "naming_scheme", fallback=None)
    except Exception:
        return None
    if scheme_str:
        try:
            return json.loads(scheme_str)
        except json.JSONDecodeError:
            return scheme_str
    return None

def open_naming_editor_popup(app):
    """
    Opens the Naming‑Scheme Editor modal, seeds it with live metadata,
    and keeps the GUI log + config.ini in sync.
    """
    import re
    from datetime import datetime

    def _clean_root(path: str) -> str:
        if path in {"(Root)", ""}:
            return ""
        return path.removeprefix("(Root)/")

    def _extract_root(pattern: str) -> str | None:
        if not pattern:
            return None
        norm = pattern.replace("\\", "/")
        cuts = [p for p in (norm.find("%"), norm.find("$")) if p >= 0]
        root = norm[:min(cuts)] if cuts else norm
        root = root.rstrip("/")
        return root or None

    def get_live_metadata() -> dict:
        artist  = app.v_artist.get()  or "Phish"
        year    = app.v_year.get()    or "2025"
        month   = app.v_month.get()   or "06"
        day     = app.v_day.get()     or "20"
        date    = f"{year}-{month}-{day}"
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
            "output_folder": raw_root,
        }

    def handle_special_tokens(template: str, sample_meta: dict) -> str:
        def repl_year(match):
            date_key = match.group(1)
            date_str = sample_meta.get(date_key, "")
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                return str(dt.year)
            except Exception:
                return ""
        template = re.sub(r"\$year\((\w+)\)", repl_year, template)
        for key, value in sample_meta.items():
            template = template.replace(f"%{key}%", str(value))
        return template

    # ------------------------------------------------------------------
    #  callback when the user presses “Save” in the Naming‑Scheme editor
    # ------------------------------------------------------------------
    def on_save(new_scheme: dict[str, str]):
        # 1. persist to config.ini
        scheme_str = json.dumps(new_scheme, ensure_ascii=False)
        app.naming_scheme = scheme_str
        app.config_parser.setdefault("Settings", {})
        app.config_parser.set("Settings", "naming_scheme", scheme_str)

        # 2. root‑folder handling
        root_folder = _extract_root(new_scheme.get("folder", "")) or "(Root)"
        if root_folder != "(Root)":
            app.config_parser.set("Settings", "output_folder", root_folder)
            app.output_dir.set(root_folder)
        else:
            if app.config_parser.has_option("Settings", "output_folder"):
                app.config_parser.remove_option("Settings", "output_folder")
            app.output_dir.set("")

        with open(CONFIG_FILE, "w", encoding="utf-8") as fh:
            app.config_parser.write(fh)

        # 3. build sample meta and evaluate the schemes
        sample_meta = get_live_metadata()

        # ── 3a: evaluate the filename first
        filename_eval = handle_special_tokens(
            new_scheme.get("filename", ""), sample_meta
        )

        # ── 3b: inject it into meta so %filename% works in folder scheme
        sample_meta_with_fn = dict(sample_meta, filename=filename_eval)

        # ── 3c: now evaluate the folder scheme
        folder_eval = handle_special_tokens(
            new_scheme.get("folder", ""), sample_meta_with_fn
        )

        # 4. log everything
        app._log(f"Current Folder Scheme (evaluated): {folder_eval}")
        app._log(f"Current Filename Scheme (evaluated): {filename_eval}")
        app._log(f"Output Folder: {root_folder}")

    # ------------------------------------------------------------------
    #  open the modal editor, seeded with current scheme / metadata
    # ------------------------------------------------------------------
    saved = get_naming_scheme_from_config(app) or {
        "folder":   "%artist%/$year(date)",
        "filename": "%artist% - %date% - %venue% - %city% [%format%] [%additional%]",
    }
    init_root = (
        _extract_root(saved.get("folder", "")) or
        _clean_root(app.output_dir.get() or "(Root)") or
        "(Root)"
    )

    editor = NamingEditor(
        master            = app,
        root_path         = init_root,
        get_live_metadata = get_live_metadata,
        initial_scheme    = saved,
        on_save           = on_save,
    )
    editor.grab_set()
    editor.focus_set()
    app.wait_window(editor)

def reset_naming_scheme_from_menu(app):
    """Restore the built‑in defaults for folder / filename scheme."""

    # ── canonical defaults ──────────────────────────────────────────
    default_folder   = "%artist%/$year(date)"
    default_filename = "%artist% - %date% - %venue% - %city% [%format%] [%additional%]"

    # ── update in‑memory settings ──────────────────────────────────
    app.naming_scheme = {
        "folder":   default_folder,
        "filename": default_filename,
    }
    app.folder_scheme   = default_folder
    app.filename_scheme = default_filename

    # reset output‑folder field
    app.output_dir.set("(Root)")
    if hasattr(app, "output_folder_var"):
        app.output_folder_var.set("(Root)")

    # ── persist to config.ini ───────────────────────────────────────
    cfg = app.config_parser
    if not cfg.has_section("Settings"):
        cfg.add_section("Settings")

    cfg.set("Settings", "naming_scheme", json.dumps(app.naming_scheme, ensure_ascii=False))
    cfg.set("Settings", "output_folder", "")

    config_path = Path(app.assets_dir, "config", "config.ini")
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w", encoding="utf-8") as f:
        cfg.write(f)

    # ── update open naming scheme editor (if any) ───────────────────
    if getattr(app, "scheme_editor", None) and hasattr(app.scheme_editor, "_reset"):
        app.scheme_editor._reset()

    # ── log what happened ───────────────────────────────────────────
    if hasattr(app, "_log"):
        app._log(
            "Naming scheme and output folder reset to default:\n"
            f"  Folder scheme : {default_folder}\n"
            f"  Filename scheme: {default_filename}\n"
            f"  Output folder  : (Root)"
        )
            
def _select_random_template(app):
    """
    Pick a random .psd from /assets/Photoshop Templates/Generic and
    treat it as the current template.
    """
    psd_files = list(GENERIC_DIR.glob("*.psd"))
    if not psd_files:
        app._log("⚠️  No PSD files found in the Generic templates folder.")
        return

    choice = random.choice(psd_files)

    # Update whatever your app expects for template selection
    app.v_template.set(choice.stem)
    app.current_template_path = choice
    app._log(f"🎲 Random template selected → {choice.name}")

    # You may want to trigger actual template loading here if applicable
    # e.g. _load_template_from_path(app, choice)

def build_template_dropdown_values(app):
    """
    Constructs a nested dropdown list for templates:
    - Default
    - Random
    - Artist
      - PSDs for that artist (indented)
    """
    values = ["Default", "Random"]
    if not hasattr(app, "tpl_map"):
        return values

    for artist, psds in sorted(app.tpl_map.items()):
        values.append(artist)
        values.extend([f"  {psd}" for psd in psds if psd.lower().endswith(".psd")])
        values.append(f"  Random")  # optional per-artist random

    return values



# ═══════════════════════════════════════════════════════════════════════
#           Poster‑creation helpers (Photoshop path & UI toggling)
# ═══════════════════════════════════════════════════════════════════════
def _set_poster_controls_state(app, *, enabled: bool) -> None:
    """
    Turn poster‑creation widgets on/off.
    • When disabled → force “Make Poster?” to “No” and grey it out.
    • When enabled  → widgets are editable (readonly) again.
    """
    if enabled:
        # Template picker & “Make Poster?” become active
        app.cb_template.config(state="readonly")
        app.cb_make_poster.config(state="readonly")
        if app.v_make_poster.get() == "No":
            app.v_make_poster.set("Yes")       # or leave as‑is if you prefer
    else:
        # Disable and lock to “No”
        app.cb_template.config(state="disabled")
        app.v_make_poster.set("No")
        app.cb_make_poster.config(state="disabled")

def prompt_photoshop_path_if_first_boot(app) -> None:
    """
    Ask once per install if the user wants to set a Photoshop path.
    Stores “DISABLED” in Settings→photoshop_path when the user declines
    so the question never re‑appears.
    """
    cfg = app.config_parser
    ps_key = "photoshop_path"
    saved_path = cfg.get("Settings", ps_key, fallback="").strip()

    # ── Already decided earlier ──────────────────────────
    if saved_path == "DISABLED":
        app.photoshop_path = None
        _set_poster_controls_state(app, enabled=False)
        app._log("Poster creation disabled (remembered from previous run).")
        return
    if saved_path:
        app.photoshop_path = saved_path
        _set_poster_controls_state(app, enabled=True)
        app._log(f"Photoshop path loaded from config: {saved_path}")
        return

    # ── First run: ask the question ──────────────────────
    want_path = messagebox.askyesno(
        title="Set Photoshop Path?",
        message="Would you like to set a Photoshop path for poster creation?"
    )

    if not want_path:
        # User said “No” – remember that choice
        app.photoshop_path = None
        _set_poster_controls_state(app, enabled=False)
        cfg.setdefault("Settings", {})
        cfg.set("Settings", ps_key, "DISABLED")
        with open(CONFIG_FILE, "w", encoding="utf-8") as fh:
            cfg.write(fh)
        app._log("User declined to set Photoshop path – poster creation disabled.")
        return

    # User said “Yes” – ask for the path
    path = filedialog.askopenfilename(
        title="Select Photoshop Executable",
        filetypes=[("Executable files",
                    "*.exe" if os.name == "nt" else "*"),
                   ("All files", "*.*")]
    )

    if path:
        app.photoshop_path = path
        _set_poster_controls_state(app, enabled=True)
        cfg.setdefault("Settings", {})
        cfg.set("Settings", ps_key, path)
        app._log(f"Photoshop path set to: {path}")
    else:
        # Treat a cancel as a decline
        app.photoshop_path = None
        _set_poster_controls_state(app, enabled=False)
        cfg.setdefault("Settings", {})
        cfg.set("Settings", ps_key, "DISABLED")
        app._log("No Photoshop path selected – poster creation disabled.")

    with open(CONFIG_FILE, "w", encoding="utf-8") as fh:
        cfg.write(fh)

    def on_format_select(event):
        selected = app.ent_format.get()
        if selected and selected not in app.format_history:
            app.format_history.append(selected)
            app.ent_format['values'] = app.format_history

    app.ent_format.bind("<<ComboboxSelected>>", on_format_select)


    def on_add_select(event):
        selected = app.ent_add.get()
        if selected and selected not in app.add_history:
            app.add_history.append(selected)
            app.ent_add['values'] = app.add_history

    app.ent_add.bind("<<ComboboxSelected>>", on_add_select)

    # ------------------------------------------------------------------
    #  callback when the user presses “Save” in the Naming‑Scheme editor
    # ------------------------------------------------------------------
    def on_save(new_scheme: dict[str, str]):
        # 1. persist to config.ini
        scheme_str = json.dumps(new_scheme, ensure_ascii=False)
        app.naming_scheme = scheme_str
        app.config_parser.setdefault("Settings", {})
        app.config_parser.set("Settings", "naming_scheme", scheme_str)

        # 2. root‑folder handling
        root_folder = _extract_root(new_scheme.get("folder", "")) or "(Root)"
        if root_folder != "(Root)":
            app.config_parser.set("Settings", "output_folder", root_folder)
            app.output_dir.set(root_folder)
        else:
            if app.config_parser.has_option("Settings", "output_folder"):
                app.config_parser.remove_option("Settings", "output_folder")
            app.output_dir.set("")

        with open(CONFIG_FILE, "w", encoding="utf-8") as fh:
            app.config_parser.write(fh)

        # 3. build sample meta and evaluate the schemes
        sample_meta = get_live_metadata()

        # ── 3a: evaluate the filename first
        filename_eval = handle_special_tokens(
            new_scheme.get("filename", ""), sample_meta
        )

        # ── 3b: inject it into meta so %filename% works in folder scheme
        sample_meta_with_fn = dict(sample_meta, filename=filename_eval)

        # ── 3c: now evaluate the folder scheme
        folder_eval = handle_special_tokens(
            new_scheme.get("folder", ""), sample_meta_with_fn
        )

        # 4. log everything
        app._log(f"Current Folder Scheme (evaluated): {folder_eval}")
        app._log(f"Current Filename Scheme (evaluated): {filename_eval}")
        app._log(f"Output Folder: {root_folder}")

    # ------------------------------------------------------------------
    #  open the modal editor, seeded with current scheme / metadata
    # ------------------------------------------------------------------
    saved = get_naming_scheme_from_config(app) or {
        "folder":   "%artist%/$year(date)",
        "filename": "%artist% - %date% - %venue% - %city% [%format%] [%additional%]",
    }
    init_root = (
        _extract_root(saved.get("folder", "")) or
        _clean_root(app.output_dir.get() or "(Root)") or
        "(Root)"
    )

    editor = NamingEditor(
        master            = app,
        root_path         = init_root,
        get_live_metadata = get_live_metadata,
        initial_scheme    = saved,
        on_save           = on_save,
    )
    editor.grab_set()
    editor.focus_set()
    app.wait_window(editor)

CONFIG_DIR = "config"
CACHE_FILE = os.path.join(CONFIG_DIR, "dropdown_cache.json")

def initialize_dropdown_cache():
    if not os.path.exists(CONFIG_DIR):
        os.makedirs(CONFIG_DIR)
    if not os.path.exists(CACHE_FILE):
        # Save initial cache with constants as history
        data = {
            "format_history": FORMAT_LIST.copy(),
            "add_history": ADDITIONAL_LIST.copy(),
        }
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    else:
        # Cache file exists, check if keys exist or empty and fill if needed
        with open(CACHE_FILE, "r+", encoding="utf-8") as f:
            data = json.load(f)
            changed = False
            if not data.get("format_history"):
                data["format_history"] = FORMAT_LIST.copy()
                changed = True
            if not data.get("add_history"):
                data["add_history"] = ADDITIONAL_LIST.copy()
                changed = True
            if changed:
                f.seek(0)
                json.dump(data, f, indent=2)
                f.truncate()
                
def load_dropdown_cache():
    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_dropdown_cache(format_history, add_history):
    data = {
        "format_history": format_history,
        "add_history": add_history,
    }
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

# ═══════════════════════════════════════════════════════════════════════
#                           GUI builder
# ═══════════════════════════════════════════════════════════════════════
def build_gui(app) -> None:
    initialize_cache(app)
    """
    Build the entire VidForge window: menus, metadata, file tree,
    queue tree, log panel, and install pane-split persistence.
    """
    # ─────────────── Menu bar ────────────────
    menubar = tk.Menu(app)
    app.config(menu=menubar)

    # ── File ─────────────────────────────────
    file_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="File", menu=file_menu)
    file_menu.add_command(
        label="Open Root Folder",
        command=app._browse
    )

    # ── Edit ────────────────────────────────
    edit_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="Edit", menu=edit_menu)
    edit_menu.add_command(label="Edit Artists.txt",
                        command=lambda: app._open_txt_file("Artists.txt"))
    edit_menu.add_command(label="Edit Cities.txt",
                        command=lambda: app._open_txt_file("Cities.txt"))
    edit_menu.add_command(label="Edit Venues.txt",
                        command=lambda: app._open_txt_file("Venues.txt"))
    edit_menu.add_separator()
    edit_menu.add_command(label="Change Naming Scheme",
                        command=lambda: open_naming_editor_popup(app))
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
    tools_menu.add_command(label="Refresh Metadata", command=app._reload_metadata)

    # ── Help ────────────────────────────────
    help_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="Help", menu=help_menu)
    help_menu.add_command(label="Read Me", command=app._open_readme)
    help_menu.add_command(label="Useful Tips", command=app._open_tips)

    # ─────────────── Top bar (root path) ────────────────
    top = ttk.Frame(app)
    top.pack(fill="x")
    ttk.Label(top, text="Root Folder:").pack(side="left")
    style = ttk.Style(app)
    style.configure("Root.TEntry", padding=(4, 2), relief="flat")
    ttk.Entry(top, textvariable=app.root_dir, width=80,
              state="readonly", style="Root.TEntry").pack(side="left", fill="x", expand=True)
    ttk.Button(top, text="Browse", command=app._browse).pack(side="left", padx=4)
    ttk.Button(top, text="Refresh", command=lambda: populate_tree(app, app.root_dir.get())).pack(side="left", padx=4)

    # ─────────────── Main paned window (LEFT / RIGHT) ────────────────
    app.main = ttk.PanedWindow(app, orient="horizontal")
    app.main.pack(fill="both", expand=True)
    left = tk.Frame(app.main)
    right = tk.Frame(app.main)
    app.main.add(left, weight=3)
    app.main.add(right, weight=2)

    # ─────────────── Metadata pane ────────────────
    meta = tk.Frame(left)
    meta.pack(fill="x", pady=(0, 2))

    def _row(lbl, var, r):
        tk.Label(meta, text=lbl).grid(row=r, column=0, sticky="w")
        cb = ttk.Combobox(meta, textvariable=var, width=34, state="normal")  # editable
        cb.grid(row=r, column=1, sticky="w", padx=4)
        return cb

    app.v_artist = tk.StringVar()
    app.cb_artist = _row("Artist:", app.v_artist, 0)

    def on_artist_selected(event=None):
        artist = app.v_artist.get()
        psds = app.tpl_map.get(artist, [])
        app.cb_template_psd['values'] = psds
        if psds:
            app.cb_template_psd.current(0)
            app.v_template_psd.set(psds[0])
        else:
            app.cb_template_psd.set('')

    app.cb_artist.bind("<<ComboboxSelected>>", on_artist_selected)

    app.v_venue = tk.StringVar()
    app.cb_venue = _row("Venue:", app.v_venue, 1)

    app.v_city = tk.StringVar()
    app.cb_city = _row("City:", app.v_city, 2)

    # If you still want this function for another combobox named 'cb_template', place it below (if not needed, you can remove it)
    def on_artist_changed(*args):
        artist = app.v_artist.get()
        psds = app.tpl_map.get(artist, [])
        values = ["Random"] + psds if psds else []
        if hasattr(app, 'cb_template'):
            app.cb_template['values'] = values
            app.v_template.set('')  # Clear selection, do NOT auto-select first PSD

    # If you want to use on_artist_changed as a trace callback:
    # app.v_artist.trace_add("write", on_artist_changed)

    # ───────────────── FORMAT setup (row 1, columns 2-4) ─────────────────
    # Load (or create) the persistent dropdown cache so user-entered values survive restarts
    initialize_dropdown_cache()
    _cache = load_dropdown_cache()
    app.format_history = _cache.get("format_history", []) or []
    app.add_history = _cache.get("add_history", []) or []

    app.v_format = tk.StringVar()
    tk.Label(meta, text="Format:").grid(row=1, column=2, sticky="w")

    app.ent_format = ttk.Combobox(
        meta,
        textvariable=app.v_format,
        values=app.format_history,  # starts with cached list of full strings
        width=34,
        state="normal"              # editable combobox with history only
    )
    app.ent_format.grid(row=1, column=3, sticky="w")

    app.format_menubutton = tk.Menubutton(meta, text="Format", indicatoron=True, borderwidth=1, relief="raised")
    app.format_menubutton.grid(row=1, column=4, sticky="w", padx=4)
    app.format_menu = tk.Menu(app.format_menubutton, tearoff=False)
    app.format_menubutton.configure(menu=app.format_menu)

    app.format_choices = {}
    for choice in FORMAT_LIST:  # fixed list for the menu checkbuttons
        app.format_choices[choice] = tk.IntVar(value=0)
        app.format_menu.add_checkbutton(
            label=choice,
            variable=app.format_choices[choice],
            onvalue=1, offvalue=0,
            command=lambda c=choice: update_format_text()
        )

    def update_format_text():
        current_text = app.v_format.get()
        tokens = [t.strip() for t in current_text.split(",") if t.strip()]
        for name, var in app.format_choices.items():
            if var.get() == 1 and name not in tokens:
                tokens.append(name)
            elif var.get() == 0 and name in tokens:
                tokens.remove(name)
        new_text = ", ".join(tokens)
        if new_text != current_text:
            app.v_format.set(new_text)
        add_to_format_history(new_text)

    def add_to_format_history(text):
        text = text.strip()
        if text and text not in app.format_history:
            app.format_history.append(text)
            app.ent_format['values'] = app.format_history
            save_dropdown_cache(app.format_history, app.add_history)

    def sync_format_menu_with_text(*args):
        current_text = app.v_format.get()
        tokens = set(t.strip() for t in current_text.split(",") if t.strip())
        for name, var in app.format_choices.items():
            desired = 1 if name in tokens else 0
            if var.get() != desired:
                var.set(desired)

    app.v_format.trace_add("write", sync_format_menu_with_text)

    def on_format_selected(event):
        selected = app.ent_format.get()
        app.v_format.set(selected)
        add_to_format_history(selected)

    def on_format_focus_out(event):
        typed = app.ent_format.get()
        add_to_format_history(typed)

    app.ent_format.bind("<<ComboboxSelected>>", on_format_selected)
    app.ent_format.bind("<FocusOut>", on_format_focus_out)


    # ───────────── ADDITIONAL setup (row 2, columns 2-4) ─────────────
    app.v_add = tk.StringVar()
    tk.Label(meta, text="Additional:").grid(row=2, column=2, sticky="w")

    app.ent_add = ttk.Combobox(
        meta,
        textvariable=app.v_add,
        values=app.add_history,  # cached list of full strings
        width=34,
        state="normal"
    )
    app.ent_add.grid(row=2, column=3, sticky="w")

    app.add_menubutton = tk.Menubutton(meta, text="Additional", indicatoron=True, borderwidth=1, relief="raised")
    app.add_menubutton.grid(row=2, column=4, sticky="w", padx=4)
    app.add_menu = tk.Menu(app.add_menubutton, tearoff=False)
    app.add_menubutton.configure(menu=app.add_menu)

    app.add_choices = {}
    for choice in ADDITIONAL_LIST:  # fixed list for the menu checkbuttons
        app.add_choices[choice] = tk.IntVar(value=0)
        app.add_menu.add_checkbutton(
            label=choice,
            variable=app.add_choices[choice],
            onvalue=1, offvalue=0,
            command=lambda c=choice: update_add_text()
        )

    def add_additional_to_history(app):
        new_val = app.v_add.get().strip()
        if new_val and new_val not in app.add_history:
            app.add_history.append(new_val)
            app.ent_add['values'] = app.add_history
            save_dropdown_cache(app.format_history, app.add_history)

    # Bind saving logic on focus out and Enter keypress
    app.ent_add.bind("<FocusOut>", lambda e: add_additional_to_history(app))
    app.ent_add.bind("<Return>", lambda e: add_additional_to_history(app))

    def update_add_text():
        current_text = app.v_add.get()
        tokens = [t.strip() for t in current_text.split(",") if t.strip()]
        for name, var in app.add_choices.items():
            if var.get() == 1 and name not in tokens:
                tokens.append(name)
            elif var.get() == 0 and name in tokens:
                tokens.remove(name)
        new_text = ", ".join(tokens)
        if new_text != current_text:
            app.v_add.set(new_text)
        add_to_add_history(new_text)

    def add_to_add_history(text):
        text = text.strip()
        if text and text not in app.add_history:
            app.add_history.append(text)
            app.ent_add['values'] = app.add_history
            save_dropdown_cache(app.format_history, app.add_history)

    def sync_add_menu_with_text(*args):
        current_text = app.v_add.get()
        tokens = set(t.strip() for t in current_text.split(",") if t.strip())
        for name, var in app.add_choices.items():
            desired = 1 if name in tokens else 0
            if var.get() != desired:
                var.set(desired)

    app.v_add.trace_add("write", sync_add_menu_with_text)

    def on_add_selected(event):
        selected = app.ent_add.get()
        app.v_add.set(selected)
        add_to_add_history(selected)

    def on_add_focus_out(event):
        typed = app.ent_add.get()
        add_to_add_history(typed)

    app.ent_add.bind("<<ComboboxSelected>>", on_add_selected)
    app.ent_add.bind("<FocusOut>", on_add_focus_out)

    # --- Date widgets (row 0, columns 2 and 3) -----------------------------------------
    tk.Label(meta, text="Date:").grid(row=0, column=2, sticky="w")
    dt = tk.Frame(meta)
    dt.grid(row=0, column=3, sticky="w")
    yrs  = [str(y) for y in range(datetime.now().year, 1999, -1)]
    mths = [f"{m:02d}" for m in range(1, 13)]
    dys  = [f"{d:02d}" for d in range(1, 32)]
    app.v_year  = tk.StringVar()
    app.cb_year  = ttk.Combobox(dt, textvariable=app.v_year,  values=yrs,  width=6, state="readonly")
    app.v_month = tk.StringVar()
    app.cb_month = ttk.Combobox(dt, textvariable=app.v_month, values=mths, width=4, state="readonly")
    app.v_day   = tk.StringVar()
    app.cb_day   = ttk.Combobox(dt, textvariable=app.v_day,   values=dys,  width=4, state="readonly")
    app.cb_year.grid(row=0, column=0)
    app.cb_month.grid(row=0, column=1)
    app.cb_day.grid(row=0, column=2)

    # Override date checkbox (moved to row 0, column 4 next to Date selectors)
    app.v_override_date = tk.BooleanVar()
    ttk.Checkbutton(meta, text="Override Modified Date",
                    variable=app.v_override_date).grid(row=0, column=4, sticky="w")
    

    # Make Poster combo inside poster_frame aligned right
    app.v_make_poster = tk.StringVar(value="Yes")

    poster_frame = tk.Frame(meta)
    poster_frame.grid(row=3, column=1, sticky="e")

    tk.Label(poster_frame, text="Make Poster?").pack(side="left")
    app.cb_make_poster = ttk.Combobox(
        poster_frame, textvariable=app.v_make_poster,
        values=["Yes", "No"], width=6, state="readonly"
    )
    app.cb_make_poster.pack(side="left", padx=0)      
    
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

       
    # ───────────── Template Dropdown (combined logic) ─────────────
    app.v_template = tk.StringVar(value="Default")

    tk.Label(meta, text="Template:").grid(row=3, column=2, sticky="w")
    app.cb_template = ttk.Combobox(
        meta, textvariable=app.v_template, width=40, state="readonly"
    )
    app.cb_template.grid(row=3, column=3, sticky="w")

    # Initialize state for double dropdown
    app.tpl_stage = "folders"
    app.tpl_artist = None

    def _on_template_selected(event=None):
        sel = app.v_template.get()
        root = Path(ASSETS_DIR) / "Photoshop Templates"

        if app.tpl_stage == "folders":
            if sel == "Random":
                import random
                artist = app.v_artist.get()
                folder = artist if (root / artist).is_dir() else "Generic"
                psds = list((root / folder).glob("*.psd"))
                if not psds:
                    psds = list((root / "Generic").glob("*.psd"))
                    folder = "Generic"
                if psds:
                    chosen = random.choice(psds)
                    _load_template_from_path(app, str(chosen))
                    app._log(f"Template selected → {chosen.name}")
                else:
                    app._log("⚠️ No PSDs found to randomize.")
                return
            elif sel == "Default":
                artist = app.v_artist.get()
                psd = root / (artist if (root / artist).is_dir() else "Generic") / f"{artist}.psd"
                if not psd.is_file():
                    psd = root / "Generic" / "Generic.psd"
                _load_template_from_path(app, str(psd))
                app._log(f"Template selected → {psd.name}")
                return
            else:
                app.tpl_artist = sel
                app.tpl_stage = "psds"
                psds = app.tpl_map.get(sel, [])
                app.cb_template["values"] = ["← Back", "Random"] + psds
                app.v_template.set("")
                app.after(10, lambda: app.cb_template.event_generate("<Button-1>"))
        else:  # in PSD selection stage
            if sel == "← Back":
                app.cb_template["values"] = ["Default", "Random"] + sorted(app.tpl_map.keys(), key=str.casefold)
                app.v_template.set("Default")
                app.tpl_stage = "folders"
                app.tpl_artist = None
                app.after(10, lambda: app.cb_template.event_generate("<Button-1>"))
            elif sel == "Random":
                import random
                psds = app.tpl_map.get(app.tpl_artist, [])
                if psds:
                    chosen = random.choice(psds)
                    path = root / app.tpl_artist / chosen
                    _load_template_from_path(app, str(path))
                    app._log(f"Template selected → {chosen}")
                else:
                    app._log("⚠️ No PSDs found to randomize.")
            else:
                path = root / app.tpl_artist / sel
                if path.is_file():
                    _load_template_from_path(app, str(path))
                    app._log(f"Template selected → {sel}")
                else:
                    app._log(f"⚠️ Template not found: {sel}")

    # Setup values and bind
    app.cb_template["values"] = ["Default", "Random"] + sorted(app.tpl_map.keys())
    app.cb_template.bind("<<ComboboxSelected>>", _on_template_selected)

    # Enable/disable based on poster toggle
    def _template_state(*_):
        app.cb_template.config(state="readonly" if app.v_make_poster.get() == "Yes" else "disabled")

    app.v_make_poster.trace_add("write", _template_state)
    _template_state()  # set initial state


    # ────────────────────────── Tree + Scrollbars ─────────────────────────
    tree_frame = tk.Frame(app.files_frame)
    tree_frame.pack(fill="both", expand=True)

    vbar_tree = ttk.Scrollbar(tree_frame, orient="vertical")
    vbar_tree.pack(side="right", fill="y")

    hbar_tree = ttk.Scrollbar(tree_frame, orient="horizontal")
    hbar_tree.pack(side="bottom", fill="x")

    app.tree = ttk.Treeview(
        tree_frame,
        columns=("filepath",),
        show="tree headings",
        yscrollcommand=vbar_tree.set,
        xscrollcommand=hbar_tree.set,
    )
    app.tree.heading("#0", text="Name")
    app.tree.column("#0", width=450, anchor="w", stretch=False)
    app.tree.heading("filepath", text="File Path")
    app.tree.column("filepath", width=450, anchor="w", stretch=False)
    app.tree.pack(fill="both", expand=True)

    vbar_tree.config(command=app.tree.yview)
    hbar_tree.config(command=app.tree.xview)

    app.tree.bind("<<TreeviewSelect>>", app._select_node)


    def resize_tree_columns(event):
        tree = event.widget
        total_width = tree.winfo_width()
        
        # Divide width evenly between two columns, minimum 100 px each
        col_width = max(int(total_width / 2), 100)
        
        tree.column("#0", width=col_width, stretch=False)
        tree.column("filepath", width=col_width, stretch=False)

    app.tree.bind("<Configure>", resize_tree_columns)

    # ───────────────────────── Context-menu helpers ───────────────────────
    def setup_tree_context_menu(app):
        menu = tk.Menu(app, tearoff=0)
        menu.add_command(label="Rename",  command=lambda: rename_item(app))
        menu.add_command(label="Delete",  command=lambda: delete_item(app))
        menu.add_command(label="Open",    command=lambda: open_item(app))
        # placeholder label—will be adjusted on-the-fly
        menu.add_command(label="Open File Location",
                        command=lambda: open_file_location(app))

        loc_idx = menu.index("end")  # index of the last item (open-location)

        def on_right_click(event):
            iid = app.tree.identify_row(event.y)
            if not iid:
                return
            app.tree.selection_set(iid)

            path  = app.tree.item(iid, "values")[0]
            label = "Open Folder Location" if os.path.isdir(path) \
                    else "Open File Location"
            menu.entryconfig(loc_idx, label=label)   # update label

            menu.tk_popup(event.x_root, event.y_root)

        app.context_menu = menu
        app.tree.bind("<Button-3>",         on_right_click)  # Win/Linux
        app.tree.bind("<Control-Button-1>", on_right_click)  # macOS

    # ───────────────────────── Menu actions ───────────────────────────────
    def rename_item(app):
        selected = app.tree.selection()
        if not selected:
            return
        iid = selected[0]
        old_path = app.tree.item(iid, "values")[0]
        old_name = os.path.basename(old_path)

        new_name = simpledialog.askstring("Rename", f"Rename '{old_name}' to:", initialvalue=old_name)
        if not new_name or new_name == old_name:
            return

        new_path = os.path.join(os.path.dirname(old_path), new_name)
        try:
            os.rename(old_path, new_path)
            app.tree.item(iid, text=new_name, values=(new_path,))
            app._log(f"Renamed '{old_name}' → '{new_name}'")
        except Exception as e:
            messagebox.showerror("Error", f"Rename failed: {e}")

    def delete_item(app):
        sel = app.tree.selection()
        if not sel:
            return
        iid  = sel[0]
        path = app.tree.item(iid, "values")[0]
        if not messagebox.askyesno("Delete", f"Delete '{path}'?"):
            return
        try:
            (shutil.rmtree if os.path.isdir(path) else os.remove)(path)
            app.tree.delete(iid)
            app._log(f"Deleted '{path}'")
        except Exception as e:
            messagebox.showerror("Error", f"Delete failed: {e}")

    def open_item(app):
        sel = app.tree.selection()
        if not sel:
            return
        path = app.tree.item(sel[0], "values")[0]
        try:
            if sys.platform.startswith("win"):
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            messagebox.showerror("Error", f"Open failed: {e}")

    def open_file_location(app):
        sel = app.tree.selection()
        if not sel:
            return
        path = app.tree.item(sel[0], "values")[0]
        if not os.path.exists(path):
            messagebox.showerror("Error", "Path no longer exists.")
            return
        try:
            if sys.platform.startswith("win"):
                args = ["explorer"]
                args += ["/select,", os.path.normpath(path)] if os.path.isfile(path) \
                        else [os.path.normpath(path)]
                subprocess.Popen(args)

            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-R" if os.path.isfile(path) else "", path])

            else:  # Linux / *nix
                folder = path if os.path.isdir(path) else os.path.dirname(path)
                fm_cmds = [
                    ("nautilus", ["nautilus", "--select", path]),
                    ("dolphin",  ["dolphin",  "--select", path]),
                    ("thunar",   ["thunar",   "--select", path]),
                    ("nemo",     ["nemo",     "--no-desktop", folder]),
                ]
                for exe, cmd in fm_cmds:
                    if shutil.which(exe):
                        subprocess.Popen(cmd)
                        break
                else:
                    subprocess.Popen(["xdg-open", folder])
        except Exception as e:
            messagebox.showerror("Error", f"Open File Location failed: {e}")

    # Attach context-menu
    setup_tree_context_menu(app)

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
    tk.Label(app.frame_queue, text="Queue:").pack(anchor="w")
    queue_frame = tk.Frame(app.frame_queue); queue_frame.pack(fill="both", expand=True)
    app.queue_tree = ttk.Treeview(queue_frame, columns=("original", "proposed"),
                                show="headings", selectmode="extended")
    app.queue_tree.heading("original", text="Original Filename")
    app.queue_tree.heading("proposed", text="Proposed Filename")
    app.queue_tree.column("original", width=450, anchor="w", stretch=False)
    app.queue_tree.column("proposed", width=450, anchor="w", stretch=False)
    vbar_q = ttk.Scrollbar(queue_frame, orient="vertical",   command=app.queue_tree.yview)
    hbar_q = ttk.Scrollbar(queue_frame, orient="horizontal", command=app.queue_tree.xview)
    app.queue_tree.configure(yscrollcommand=vbar_q.set, xscrollcommand=hbar_q.set)
    app.queue_tree.grid(row=0, column=0, sticky="nsew")
    vbar_q.grid(row=0, column=1, sticky="ns")
    hbar_q.grid(row=1, column=0, sticky="ew")
    queue_frame.grid_rowconfigure(0, weight=1); queue_frame.grid_columnconfigure(0, weight=1)

    def resize_queue_columns(event):
        tree = event.widget
        total_width = tree.winfo_width()

        # Let's split evenly between the two columns:
        col_width = max(int(total_width / 2), 100)  # minimum 100 px each

        tree.column("original", width=col_width, stretch=False)
        tree.column("proposed", width=col_width, stretch=False)

    app.queue_tree.bind("<Configure>", resize_queue_columns)
    # ─────────────── Log panel on the right ────────────────
    tk.Label(right, text="Log:").pack(anchor="w")
    log_frame = tk.Frame(right); log_frame.pack(fill="both", expand=True)
    app.log = tk.Text(log_frame, wrap="none"); app.log.pack(side="left", fill="both", expand=True)
    vbar_log = ttk.Scrollbar(log_frame, orient="vertical",   command=app.log.yview)
    hbar_log = ttk.Scrollbar(right,       orient="horizontal", command=app.log.xview)
    vbar_log.pack(side="right", fill="y"); hbar_log.pack(fill="x")
    app.log.config(yscrollcommand=vbar_log.set, xscrollcommand=hbar_log.set)
    ttk.Button(right, text="Clear Logs", command=lambda: app.log.delete("1.0", "end")).pack(anchor="e", pady=2)

    # ─────────────── Autocomplete, multi‑select, tab‑order (unchanged) ────────────────
    enable_inline_autocomplete(app.cb_artist, lambda: app.cb_artist["values"])
    enable_inline_autocomplete(app.cb_venue,  lambda: app.cb_venue["values"])
    enable_inline_autocomplete(app.cb_city,   lambda: app.cb_city["values"])

    # ------------------------------------------------------------------
    # Custom Tab order (skip Clear Fields button & Override Date checkbox)
    # ------------------------------------------------------------------
    tab_order = [
        app.cb_artist,
        app.cb_venue,
        app.cb_city,
        app.v_add,
        app.v_format,
        app.cb_year,
        app.cb_month,
        app.cb_day,
        app.cb_make_poster,
        app.cb_template,
    ]

    setup_global_tab_order(app, tab_order)

    # Function to cycle focus back to the first widget on Tab pressed at last widget
    def on_tab_press(event):
        if event.widget == tab_order[-1]:
            tab_order[0].focus_set()
            return "break"  # Prevent default behavior to avoid losing focus cycle

    # Bind on last widget for both Tab and Shift+Tab
    tab_order[-1].bind("<Tab>", on_tab_press)
    prompt_photoshop_path_if_first_boot(app)