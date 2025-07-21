import tkinter as tk
from tkinter import ttk

def build_metadata(meta, app):
    """
    Build the metadata section with artist, venue, and city comboboxes.
    Also, set up the artist selection logic for template PSDs.

    Args:
    - meta: The parent frame where the widgets will be placed.
    - app: The main app instance, used to bind comboboxes and manage state.
    """
    
    def _row(lbl, var, r):
        """Helper function to create a label and combobox on the same row."""
        tk.Label(meta, text=lbl).grid(row=r, column=0, sticky="w")
        cb = ttk.Combobox(meta, textvariable=var, width=34, state="normal")  # editable
        cb.grid(row=r, column=1, sticky="w", padx=4)
        return cb

    # Artist Combobox
    app.v_artist = tk.StringVar()
    app.cb_artist = _row("Artist:", app.v_artist, 0)

    def on_artist_selected(event=None):
        """Handle artist selection and update the PSD template options."""
        artist = app.v_artist.get()
        psds = app.tpl_map.get(artist, [])
        app.cb_template_psd['values'] = psds
        if psds:
            app.cb_template_psd.current(0)
            app.v_template_psd.set(psds[0])
        else:
            app.cb_template_psd.set('')

    # Bind artist combobox selection event
    app.cb_artist.bind("<<ComboboxSelected>>", on_artist_selected)

    # Venue Combobox
    app.v_venue = tk.StringVar()
    app.cb_venue = _row("Venue:", app.v_venue, 1)

    # City Combobox
    app.v_city = tk.StringVar()
    app.cb_city = _row("City:", app.v_city, 2)
