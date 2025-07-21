import os
import logging
import configparser
from tkinter import filedialog, messagebox
from constants import CONFIG_FILE

log = logging.getLogger("vidforge")

def get_photoshop_path() -> str:
    """Return the Photoshop executable path from config.ini or ''."""
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE, encoding="utf-8")

    path = config.get("Settings", "photoshop_path", fallback="").strip()
    if path and os.path.isfile(path):
        log.info(f'Loaded Photoshop path: "{path}"')
        return path

    if path:
        log.warning(f'Photoshop path in config.ini is invalid: "{path}"')
    return ""

def save_photoshop_path(path: str) -> None:
    """Save the Photoshop path to config.ini under [Settings]."""
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE, encoding="utf-8")

    if "Settings" not in config:
        config["Settings"] = {}

    config.set("Settings", "photoshop_path", path)

    with open(CONFIG_FILE, "w", encoding="utf-8") as fh:
        config.write(fh)

    log.info(f'Saved Photoshop path to config.ini: "{path}"')

def _select_photoshop_location(app):
    """Menu‑bar handler: let the user pick / change the Photoshop exe."""
    path = filedialog.askopenfilename(
        title="Select Photoshop Executable",
        filetypes=[("Executable files", "*.exe" if os.name == "nt" else "*"),
                  ("All files", "*.*")]
    )
    if not path:  # user hit Cancel
        app._log("Photoshop location unchanged.")
        return

    # ── Persist ───────────────────────────────────────────────────────
    app.photoshop_path = path
    app.config_parser.setdefault("Settings", {})
    app.config_parser.set("Settings", "photoshop_path", path)
    with open(CONFIG_FILE, "w", encoding="utf-8") as fh:
        app.config_parser.write(fh)

    # ── Log & Re-enable UI for poster settings ────────────────────────
    app._log(f"Photoshop location set to: {path}")
    _set_poster_controls_state(app, enabled=True)  # Ensure the UI controls are enabled
    app.update_idletasks()  # Update UI

def prompt_photoshop_path_if_first_boot(app) -> None:
    """
    Ask once per install if the user wants to set a Photoshop path.
    Stores “DISABLED” in Settings→photoshop_path when the user declines
    so the question never re‑appears.
    """
    # Delay the import here to avoid circular import issue
    from gui.gui_builder import get_naming_scheme_from_config  # <-- Move here

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
