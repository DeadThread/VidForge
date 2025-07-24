import tkinter as tk
import os
from tkinter import ttk, filedialog
from pathlib import Path
import random
from constants import ASSETS_DIR, GENERIC_DIR, CONFIG_FILE
from tkinter import messagebox
import re


def _load_template_from_path(app, template_path: str):
    """Function to load the template from the given path."""
    # Implement the logic to load the template, such as opening the file or applying it
    pass


def set_poster_controls_state(app, *, enabled: bool) -> None:
    """Enable/disable template dropdown and 'Make Poster?' combo."""
    if enabled:
        app.cb_template.config(state="readonly")
        app.cb_make_poster.config(state="readonly")
        if app.v_make_poster.get() == "No":
            app.v_make_poster.set("Yes")
    else:
        app.cb_template.config(state="disabled")
        app.v_make_poster.set("No")
        app.cb_make_poster.config(state="disabled")


def prompt_photoshop_path_if_first_boot(app) -> None:
    """Ask once per install if the user wants to set a Photoshop path."""
    cfg = app.config_parser
    ps_key = "photoshop_path"
    saved_path = cfg.get("Settings", ps_key, fallback="").strip()

    if saved_path == "DISABLED":
        app.photoshop_path = None
        set_poster_controls_state(app, enabled=False)
        app._log("Poster creation disabled (remembered from previous run).")
        return

    if saved_path:
        app.photoshop_path = saved_path
        set_poster_controls_state(app, enabled=True)
        app._log(f"Photoshop path loaded from config: {saved_path}")
        return

    want_path = messagebox.askyesno(
        title="Set Photoshop Path?",
        message="Would you like to set a Photoshop path for poster creation?"
    )

    if not want_path:
        app.photoshop_path = None
        set_poster_controls_state(app, enabled=False)
        cfg.setdefault("Settings", {})
        cfg.set("Settings", ps_key, "DISABLED")
    else:
        path = filedialog.askopenfilename(
            title="Select Photoshop Executable",
            filetypes=[("Executable files", "*.exe" if os.name == "nt" else "*"), ("All files", "*.*")]
        )
        if path:
            app.photoshop_path = path
            set_poster_controls_state(app, enabled=True)
            cfg.setdefault("Settings", {})
            cfg.set("Settings", ps_key, path)
        else:
            app.photoshop_path = None
            set_poster_controls_state(app, enabled=False)
            cfg.setdefault("Settings", {})
            cfg.set("Settings", ps_key, "DISABLED")

    with open(CONFIG_FILE, "w", encoding="utf-8") as fh:
        cfg.write(fh)


def _row(parent, lbl, var, r, col=0):
    """Helper to create a label and combobox on the same row."""
    tk.Label(parent, text=lbl).grid(row=r, column=col, sticky="w")
    cb = ttk.Combobox(parent, textvariable=var, width=34, state="normal")  # editable combobox
    cb.grid(row=r, column=col + 1, sticky="w", padx=4)
    return cb


def _normalize_name(name: str) -> str:
    """Normalize artist name for matching: lowercase, remove non-alphanum."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def on_template_selected(app, event=None):
    sel = app.v_template.get()
    root = Path(ASSETS_DIR) / "Photoshop Templates"

    if app.tpl_stage == "folders":
        if sel == "Random":
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
            artist_folder = root / artist

            if artist_folder.is_dir():
                psd_files = sorted(artist_folder.glob("*.psd"))
                if psd_files:
                    # Pick the first PSD file in artist folder
                    psd = psd_files[0]
                else:
                    psd = None
            else:
                psd = None

            # If no PSD found in artist folder, fallback to generic
            if not psd:
                generic_folder = root / "Generic"
                generic_psds = sorted(generic_folder.glob("*.psd"))
                if generic_psds:
                    psd = generic_psds[0]
                else:
                    psd = None

            if psd and psd.is_file():
                _load_template_from_path(app, str(psd))
                app._log(f"Template selected → {psd.name}")
            else:
                app._log("⚠️ No suitable PSD file found for Default template.")
            return

        else:
            app.tpl_artist = sel
            app.tpl_stage = "psds"
            psds = app.tpl_map.get(sel, [])
            app.cb_template["values"] = ["← Back", "Random"] + psds
            app.v_template.set("")
            app.after(10, lambda: app.cb_template.event_generate("<Button-1>"))

    else:  # PSD selection stage
        if sel == "← Back":
            app.cb_template["values"] = ["Default", "Random"] + sorted(app.tpl_map.keys(), key=str.casefold)
            app.v_template.set("Default")
            app.tpl_stage = "folders"
            app.tpl_artist = None
            app.after(10, lambda: app.cb_template.event_generate("<Button-1>"))
        elif sel == "Random":
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


def update_template_state(app, *_):
    app.cb_template.config(state="readonly" if app.v_make_poster.get() == "Yes" else "disabled")


def on_artist_selected(app, event=None):
    artist = app.v_artist.get()
    psds = app.tpl_map.get(artist, [])
    app.cb_template_psd['values'] = psds
    if psds:
        app.cb_template_psd.current(0)
        app.v_template_psd.set(psds[0])
    else:
        app.cb_template_psd.set('')


def build_template_dropdown(app, meta):
    app.v_template = tk.StringVar(value="Default")
    tk.Label(meta, text="Template:").grid(row=3, column=2, sticky="w")
    app.cb_template = ttk.Combobox(meta, textvariable=app.v_template, width=40, state="readonly")
    app.cb_template.grid(row=3, column=3, sticky="w")

    app.tpl_stage = "folders"
    app.tpl_artist = None

    # Poster toggle UI
    app.v_make_poster = tk.StringVar(value="Yes")
    poster_frame = tk.Frame(meta)
    poster_frame.grid(row=3, column=1, sticky="e")

    tk.Label(poster_frame, text="Make Poster?").pack(side="left")
    app.cb_make_poster = ttk.Combobox(
        poster_frame, textvariable=app.v_make_poster, values=["Yes", "No"], width=6, state="readonly"
    )
    app.cb_make_poster.pack(side="left")

    # Setup values and bind event handlers
    app.cb_template["values"] = ["Default", "Random"] + sorted(app.tpl_map.keys())
    app.cb_template.bind("<<ComboboxSelected>>", lambda e=None: on_template_selected(app, e))

    app.v_make_poster.trace_add("write", lambda *args: update_template_state(app))
    update_template_state(app)  # initial state

    # We assume app.cb_artist and app.v_artist exist (built elsewhere)
    app.cb_artist.bind("<<ComboboxSelected>>", lambda e=None: on_artist_selected(app, e))

    app.v_venue = tk.StringVar()
    app.cb_venue = _row(meta, "Venue:", app.v_venue, 1)

    app.v_city = tk.StringVar()
    app.cb_city = _row(meta, "City:", app.v_city, 2)


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


def bind_artist_to_template_dropdown(app):
    """
    Binds the artist combobox to update the PSD template combobox based on selection.
    Requires `app.cb_artist`, `app.v_artist`, `app.cb_template_psd`, `app.v_template_psd`, and `app.tpl_map`.
    """

    def on_artist_selected(event=None):
        artist = app.v_artist.get()
        psds = app.tpl_map.get(artist, [])
        app.cb_template_psd['values'] = psds
        if psds:
            app.cb_template_psd.current(0)
            app.v_template_psd.set(psds[0])
        else:
            app.cb_template_psd.set('')
            app.v_template_psd.set('')

    app.cb_artist.bind("<<ComboboxSelected>>", on_artist_selected)
