import tkinter as tk
import os
from tkinter import ttk, filedialog
from pathlib import Path
import random
from constants import ASSETS_DIR, GENERIC_DIR, CONFIG_FILE
from tkinter import messagebox

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


def build_template_dropdown(app, meta):
    """Main UI builder for template dropdown and poster toggle."""
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

    def _on_template_selected(event=None):
        # internal logic...
        pass  # keep your on_template_selected() logic here

    app.cb_template["values"] = ["Default", "Random"] + sorted(app.tpl_map.keys())
    app.cb_template.bind("<<ComboboxSelected>>", _on_template_selected)

    def _template_state(*_):
        app.cb_template.config(state="readonly" if app.v_make_poster.get() == "Yes" else "disabled")

    app.v_make_poster.trace_add("write", _template_state)
    _template_state()

    def on_artist_changed(*_):
        app.cb_template["values"] = ["Default", "Random"] + sorted(app.tpl_map.keys())
        app.v_template.set("")

    app.v_artist.trace_add("write", on_artist_changed)


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
