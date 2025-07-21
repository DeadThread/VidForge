from constants import FORMAT_LIST  # Import FORMAT_LIST from constants
from utils.cache_manager import load_dropdown_cache, save_dropdown_cache
import tkinter as tk
from tkinter import ttk

def build_format(app, meta):
    
    # ───────────────── FORMAT setup (row 1, columns 2-4) ─────────────────
    # Load (or create) the persistent dropdown cache so user-entered values survive restarts
    _cache = load_dropdown_cache()
    app.format_history = _cache.get("format_history", []) or []  # Get from cache or default to empty list
    app.add_history = _cache.get("add_history", []) or []

    # Fallback to FORMAT_LIST if the cache is empty
    if not app.format_history:
        app.format_history = FORMAT_LIST  # Use FORMAT_LIST if cache doesn't provide anything

    # Set the combobox values
    app.v_format = tk.StringVar()
    tk.Label(meta, text="Format:").grid(row=1, column=2, sticky="w")

    app.ent_format = ttk.Combobox(
        meta,
        textvariable=app.v_format,
        values=app.format_history,  # Use the combined values from cache or default
        width=34,
        state="normal"              # editable combobox with history only
    )
    app.ent_format.grid(row=1, column=3, sticky="w")

    app.format_menubutton = tk.Menubutton(meta, text="Format", indicatoron=True, borderwidth=1, relief="raised")
    app.format_menubutton.grid(row=1, column=4, sticky="w", padx=4)
    app.format_menu = tk.Menu(app.format_menubutton, tearoff=False)
    app.format_menubutton.configure(menu=app.format_menu)

    app.format_choices = {}
    for choice in FORMAT_LIST:  # Ensure the fixed list for menu checkbuttons
        app.format_choices[choice] = tk.IntVar(value=0)
        app.format_menu.add_checkbutton(
            label=choice,
            variable=app.format_choices[choice],
            onvalue=1, offvalue=0,
            command=lambda c=choice: update_format_text()
        )

    def update_format_text():
        current_text = app.v_format.get()
        tokens = [t.strip() for t in current_text.split(",") if t.strip()]
        for name, var in app.format_choices.items():
            if var.get() == 1 and name not in tokens:
                tokens.append(name)
            elif var.get() == 0 and name in tokens:
                tokens.remove(name)
        new_text = ", ".join(tokens)
        if new_text != current_text:
            app.v_format.set(new_text)
        add_to_format_history(new_text)

    def add_to_format_history(text):
        text = text.strip()
        if text and text not in app.format_history:
            app.format_history.append(text)
            app.ent_format['values'] = app.format_history
            save_dropdown_cache(app.format_history, app.add_history)

    def sync_format_menu_with_text(*args):
        current_text = app.v_format.get()
        tokens = set(t.strip() for t in current_text.split(",") if t.strip())
        for name, var in app.format_choices.items():
            desired = 1 if name in tokens else 0
            if var.get() != desired:
                var.set(desired)

    app.v_format.trace_add("write", sync_format_menu_with_text)

    def on_format_selected(event):
        selected = app.ent_format.get()
        app.v_format.set(selected)
        add_to_format_history(selected)

    def on_format_focus_out(event):
        typed = app.ent_format.get()
        add_to_format_history(typed)

    app.ent_format.bind("<<ComboboxSelected>>", on_format_selected)
    app.ent_format.bind("<FocusOut>", on_format_focus_out)
