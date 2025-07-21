from __future__ import annotations

import os
import logging
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from constants import CONFIG_FILE  # Import CONFIG_FILE from constants

log = logging.getLogger("vidforge")

_loaded_themes: set[str] = set()  # Cache of already-sourced .tcl themes

# ------------------------------------------------------------------
# small helpers
# ------------------------------------------------------------------
def _current_theme_colors(root: tk.Misc) -> tuple[str, str]:
    """Return (bg, fg) from the active ttk theme."""
    style = ttk.Style(root)
    bg = style.lookup("TFrame", "background") or style.lookup(".", "background") or "#FFFFFF"
    fg = style.lookup("TLabel", "foreground") or style.lookup(".", "foreground") or "#000000"
    return bg, fg


def _restyle_existing_tk_widgets(widget: tk.Misc, bg: str, fg: str) -> None:
    """Recursively apply bg/fg to *classic* Tk widgets so they match ttk."""
    try:
        cls = widget.winfo_class()
        if cls not in ("TFrame", "TLabel", "TButton", "Treeview", "TEntry", "TCombobox"):
            if "background" in widget.config():
                widget.config(background=bg)
            if "foreground" in widget.config():
                widget.config(foreground=fg)
    except Exception:
        pass

    for child in widget.winfo_children():
        _restyle_existing_tk_widgets(child, bg, fg)


# ------------------------------------------------------------------
# user-chosen .tcl themes
# ------------------------------------------------------------------
def load_ttk_theme(root: tk.Misc, tcl_path: str, log_func) -> str | None:
    """Source a .tcl theme file once and switch ttk to it."""
    try:
        abs_path = os.path.abspath(tcl_path)
        theme_name = os.path.splitext(os.path.basename(abs_path))[0]

        if theme_name not in _loaded_themes:
            try:
                root.tk.call("source", abs_path)
                _loaded_themes.add(theme_name)
                log_func(f"Sourced theme file: {theme_name}")
            except tk.TclError as e:
                if "already exists" not in str(e):
                    raise

        ttk.Style(root).theme_use(theme_name)
        bg, fg = _current_theme_colors(root)
        _restyle_existing_tk_widgets(root, bg, fg)
        log_func(f"Activated theme: {theme_name}")
        return abs_path

    except Exception as e:
        log.error("Failed to load theme %s: %s", tcl_path, e)
        return None


def select_and_load_theme(root, ini_parser, config_file, themes_dir, log_func) -> str | None:
    """Prompt user to choose a .tcl file and apply it."""
    fname = filedialog.askopenfilename(
        title="Select Theme File",
        filetypes=[("Tcl Theme Files", "*.tcl")],
        initialdir=os.path.abspath(themes_dir),
    )
    if not fname:
        return None

    path = load_ttk_theme(root, fname, log_func)
    if not path:
        return None

    ini_parser.setdefault("Theme", {})
    ini_parser.set("Theme", "file", path)
    with open(config_file, "w", encoding="utf-8") as f:
        ini_parser.write(f)
    return path



def save_current_theme(ini_parser, theme_path: str) -> None:
    """Save current theme path to config."""
    if theme_path:
        ini_parser.setdefault("Theme", {})
        ini_parser.set("Theme", "file", theme_path)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            ini_parser.write(f)


# ------------------------------------------------------------------
# Default / native theme helper
# ------------------------------------------------------------------
def _platform_default(root: tk.Misc) -> str:
    """Return 'vista', 'aqua', or 'clam' depending on platform."""
    win_sys = root.tk.call("tk", "windowingsystem")
    if win_sys == "win32":
        return "vista"
    if win_sys == "aqua":
        return "aqua"
    return "clam"  # Linux & others


# ------------------------------------------------------------------
# Load theme from config.ini if present
# ------------------------------------------------------------------
def restore_saved_theme(root, ini_parser, log_func) -> None:
    """Reload theme from config.ini if previously saved."""
    path = ini_parser.get("Theme", "file", fallback=None)
    
    if path:
        log_func(f"[DEBUG] Found theme path in config.ini: {path}")
        
        if path.startswith("builtin:"):
            # If it's a built-in theme, apply it
            builtin = path.removeprefix("builtin:")
            try:
                ttk.Style(root).theme_use(builtin)
            except tk.TclError:
                ttk.Style(root).theme_use("default")
            bg, fg = _current_theme_colors(root)
            _restyle_existing_tk_widgets(root, bg, fg)
            log_func(f"Restored built-in theme: {builtin}")
        elif os.path.isfile(path):
            # If it's a custom .tcl theme, apply it
            load_ttk_theme(root, path, log_func)
        else:
            log_func(f"[ERROR] Theme path is invalid: {path}")
    else:
        log_func("[DEBUG] No theme path found in config.ini.")


# ------------------------------------------------------------------
# Legacy fallback for removing theme
# ------------------------------------------------------------------
def remove_theme(root, ini_parser, config_file, log_func) -> None:
    _loaded_themes.clear()
    if ini_parser.has_section("Theme"):
        ini_parser.remove_section("Theme")
    use_default_theme(root, ini_parser, config_file, log_func)
    log_func("Custom theme cleared; reverted to native look.")

# ------------------------------------------------------------------
# Load theme from config.ini if present
# ------------------------------------------------------------------
def load_and_apply_theme(app, config_parser, log_func):
    if config_parser.has_option("Theme", "file"):  # Check in the Theme section
        theme_path = config_parser.get("Theme", "file").strip()  # Get the file path
        log_func(f"[DEBUG] Found theme file in config.ini: {theme_path!r}")
        try:
            load_ttk_theme(app, theme_path, log_func=log_func)  # Pass log_func here
            log_func(f"[INFO] Activated saved theme: {theme_path}")
        except Exception as e:
            log_func(f"[ERROR] Failed to load theme '{theme_path}': {e}")
            log_func("[INFO] Falling back to default theme.")
            use_default_theme(app, config_parser, CONFIG_FILE, log_func)  # Pass log_func here
    else:
        log_func("[DEBUG] No theme file found in config.ini, applying default theme.")
        use_default_theme(app, config_parser, CONFIG_FILE, log_func)  # Pass log_func here

# ------------------------------------------------------------------
# Default / native theme helper
# ------------------------------------------------------------------
def use_default_theme(root, ini_parser, config_file, log_func) -> None:
    """Switch to the platform’s built-in ttk theme and save that choice."""
    # Check if there is already a theme set in config.ini
    current_theme_path = ini_parser.get("Theme", "file", fallback=None)
    
    if current_theme_path:
        log_func(f"[DEBUG] Theme already set: {current_theme_path}")
        return  # Do not apply default theme if a theme is already set
    
    default_theme = _platform_default(root)
    style = ttk.Style(root)
    
    try:
        style.theme_use(default_theme)
    except tk.TclError:
        style.theme_use("default")
        default_theme = "default"

    bg, fg = _current_theme_colors(root)
    _restyle_existing_tk_widgets(root, bg, fg)

    # Save the default theme if no theme exists
    ini_parser.setdefault("Theme", {})
    ini_parser.set("Theme", "file", f"builtin:{default_theme}")
    with open(config_file, "w", encoding="utf-8") as f:
        ini_parser.write(f)

    log_func(f"Using default ttk theme: {default_theme}")
