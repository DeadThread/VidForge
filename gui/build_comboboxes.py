import tkinter as tk
from gui.naming_scheme_helpers import _row  # or wherever _row is defined

def build_metadata_fields(meta, app):
    """
    Build the artist, venue, and city comboboxes and attach them to the app.
    """
    app.v_artist = tk.StringVar()
    app.cb_artist = _row(meta, "Artist:", app.v_artist, 0)

    app.v_venue = tk.StringVar()
    app.cb_venue = _row(meta, "Venue:", app.v_venue, 1)

    app.v_city = tk.StringVar()
    app.cb_city = _row(meta, "City:", app.v_city, 2)
