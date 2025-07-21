import tkinter as tk
from tkinter import ttk
from datetime import datetime

def build_date(meta, app):
    """
    Build and place the date picker (year, month, day) and the override checkbox
    on the given meta frame.

    Args:
    - meta: The parent frame where the widgets will be placed.
    - app: The main app instance, used to bind comboboxes.
    """
    # Label for Date
    tk.Label(meta, text="Date:").grid(row=0, column=2, sticky="w")

    # Frame to hold the comboboxes
    dt = tk.Frame(meta)
    dt.grid(row=0, column=3, sticky="w")

    # Generate year, month, and day values
    yrs  = [str(y) for y in range(datetime.now().year, 1999, -1)]
    mths = [f"{m:02d}" for m in range(1, 13)]
    dys  = [f"{d:02d}" for d in range(1, 32)]

    # Year Combobox
    app.v_year = tk.StringVar()
    app.cb_year = ttk.Combobox(dt, textvariable=app.v_year, values=yrs, width=6, state="readonly")
    app.cb_year.grid(row=0, column=0)

    # Month Combobox
    app.v_month = tk.StringVar()
    app.cb_month = ttk.Combobox(dt, textvariable=app.v_month, values=mths, width=4, state="readonly")
    app.cb_month.grid(row=0, column=1)

    # Day Combobox
    app.v_day = tk.StringVar()
    app.cb_day = ttk.Combobox(dt, textvariable=app.v_day, values=dys, width=4, state="readonly")
    app.cb_day.grid(row=0, column=2)

    # Override Date Checkbox (row 0, column 4 next to Date selectors)
    app.v_override_date = tk.BooleanVar()
    ttk.Checkbutton(meta, text="Override Modified Date", variable=app.v_override_date).grid(row=0, column=4, sticky="w")
