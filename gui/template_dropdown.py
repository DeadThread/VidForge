import tkinter as tk
from tkinter import ttk, filedialog
from pathlib import Path
import random
from constants import ASSETS_DIR, GENERIC_DIR, CONFIG_FILE

def _load_template_from_path(app, template_path: str):
    """Function to load the template from the given path."""
    # Implement the logic to load the template, such as opening the file or applying it
    pass

def build_template_dropdown(app, meta):
    """
    Builds and configures the template dropdown UI component for template selection.
    """
    # Set the default selected template value to "Default"
    app.v_template = tk.StringVar(value="Default")  # Set to "Default" to select it initially

    # Label and combobox for template selection
    tk.Label(meta, text="Template:").grid(row=3, column=2, sticky="w")
    app.cb_template = ttk.Combobox(
        meta, textvariable=app.v_template, width=40, state="readonly"
    )
    app.cb_template.grid(row=3, column=3, sticky="w")

    # Initialize state for double dropdown (folder/psd)
    app.tpl_stage = "folders"
    app.tpl_artist = None

    # Make Poster Button
    app.v_make_poster = tk.StringVar(value="Yes")

    poster_frame = tk.Frame(meta)
    poster_frame.grid(row=3, column=1, sticky="e")

    tk.Label(poster_frame, text="Make Poster?").pack(side="left")
    app.cb_make_poster = ttk.Combobox(
        poster_frame, textvariable=app.v_make_poster,
        values=["Yes", "No"], width=6, state="readonly"
    )
    app.cb_make_poster.pack(side="left", padx=0)

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
                app.v_make_poster.set("Yes")  # or leave as-is if you prefer
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

    def _on_template_selected(event=None):
        """Handles template selection logic for both folder and PSD stages."""
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
                app.v_template.set("")  # Clear selection to stop auto-selecting
                app.after(10, lambda: app.cb_template.event_generate("<Button-1>"))
        else:  # in PSD selection stage
            if sel == "← Back":
                app.cb_template["values"] = ["Default", "Random"] + sorted(app.tpl_map.keys(), key=str.casefold)
                app.v_template.set("Default")  # Reset back to Default
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

    # Setup values and bind the combobox selection event
    # Always include "Default", "Random", and the artist list
    app.cb_template["values"] = ["Default", "Random"] + sorted(app.tpl_map.keys())
    app.cb_template.bind("<<ComboboxSelected>>", _on_template_selected)

    # Enable/disable based on poster toggle
    def _template_state(*_):
        app.cb_template.config(state="readonly" if app.v_make_poster.get() == "Yes" else "disabled")

    app.v_make_poster.trace_add("write", _template_state)
    _template_state()  # Set the initial state

    # Handle Artist Change (now in template_dropdown.py)
    def on_artist_changed(*args):
        artist = app.v_artist.get()
        psds = app.tpl_map.get(artist, [])
        values = ["Random"] + psds if psds else []
        app.cb_template['values'] = ["Default", "Random"] + sorted(app.tpl_map.keys())  # Always include artists
        app.v_template.set('')  # Don't auto-select first PSD
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
