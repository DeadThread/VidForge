import tkinter as tk
from tkinter import ttk

def setup_buttons(parent_frame, app):
    """Setup the button row with necessary actions."""
    
    # ───────────────────────── Buttons row ────────────────────────────────
    btn_row = tk.Frame(parent_frame)
    btn_row.pack(anchor="w", pady=4)

    ttk.Button(btn_row, text="Save Selected", command=lambda: save_selected_files(app)).pack(side="left", padx=4)
    ttk.Button(btn_row, text="Process Queue", command=app._process_queue).pack(side="left", padx=4)
    ttk.Button(btn_row, text="Remove Selected", command=lambda: remove_selected(app)).pack(side="left", padx=4)
    ttk.Button(btn_row, text="Clear Queue", command=lambda: clear_queue(app)).pack(side="left", padx=4)
