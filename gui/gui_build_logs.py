import tkinter as tk
from tkinter import ttk

def setup_log_panel(right, app):
    """Setup the log panel and its functionalities."""

    # ─────────────── Log panel on the right ────────────────
    tk.Label(right, text="Log:").pack(anchor="w")
    log_frame = tk.Frame(right)
    log_frame.pack(fill="both", expand=True)

    app.log = tk.Text(log_frame, wrap="none")
    app.log.pack(side="left", fill="both", expand=True)

    vbar_log = ttk.Scrollbar(log_frame, orient="vertical", command=app.log.yview)
    hbar_log = ttk.Scrollbar(right, orient="horizontal", command=app.log.xview)
    vbar_log.pack(side="right", fill="y")
    hbar_log.pack(fill="x")
    app.log.config(yscrollcommand=vbar_log.set, xscrollcommand=hbar_log.set)

    # Add Clear Logs button
    ttk.Button(right, text="Clear Logs", command=lambda: app.log.delete("1.0", "end")).pack(anchor="e", pady=2)

    # Setup right-click Copy context menu for the log
    def _setup_log_context_menu(app):
        app.log_context_menu = tk.Menu(app.log, tearoff=0)
        app.log_context_menu.add_command(label="Copy", command=_copy_log_selection)

        app.log.bind("<Button-3>", _show_log_context_menu)
        app.log.bind("<Button-2>", _show_log_context_menu)

    def _show_log_context_menu(event):
        try:
            app.log_context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            app.log_context_menu.grab_release()

    def _copy_log_selection():
        try:
            selected_text = app.log.selection_get()
        except tk.TclError:
            selected_text = app.log.get("1.0", "end-1c")
        app.clipboard_clear()
        app.clipboard_append(selected_text)
        app._log("Log text copied to clipboard.")

    # Call the setup function after defining the log widget
    _setup_log_context_menu(app)
