from constants import FORMAT_LIST  # Import FORMAT_LIST from constants
from utils.cache_manager import load_dropdown_cache, save_dropdown_cache
import tkinter as tk
from tkinter import ttk

def build_additional(app, meta, ADDITIONAL_LIST):
    """
    Sets up the 'Additional' combobox, menu with checkbuttons, and related history-saving logic.

    :param app: The main application object.
    :param meta: The parent tkinter widget (typically a frame).
    :param ADDITIONAL_LIST: The fixed list of choices for the checkbuttons in the menu.
    """
    # ───────────── ADDITIONAL setup (row 2, columns 2-4) ─────────────
    app.v_add = tk.StringVar()
    tk.Label(meta, text="Additional:").grid(row=2, column=2, sticky="w")

    app.ent_add = ttk.Combobox(
        meta,
        textvariable=app.v_add,
        values=app.add_history,  # cached list of full strings
        width=34,
        state="normal"
    )
    app.ent_add.grid(row=2, column=3, sticky="w")

    app.add_menubutton = tk.Menubutton(meta, text="Additional", indicatoron=True, borderwidth=1, relief="raised")
    app.add_menubutton.grid(row=2, column=4, sticky="w", padx=4)
    app.add_menu = tk.Menu(app.add_menubutton, tearoff=False)
    app.add_menubutton.configure(menu=app.add_menu)

    app.add_choices = {}
    for choice in ADDITIONAL_LIST:  # fixed list for the menu checkbuttons
        app.add_choices[choice] = tk.IntVar(value=0)
        app.add_menu.add_checkbutton(
            label=choice,
            variable=app.add_choices[choice],
            onvalue=1, offvalue=0,
            command=lambda c=choice: update_add_text()
        )

    def add_additional_to_history(app):
        new_val = app.v_add.get().strip()
        if new_val and new_val not in app.add_history:
            app.add_history.append(new_val)
            app.ent_add['values'] = app.add_history
            save_dropdown_cache(app.format_history, app.add_history)

    # Bind saving logic on focus out and Enter keypress
    app.ent_add.bind("<FocusOut>", lambda e: add_additional_to_history(app))
    app.ent_add.bind("<Return>", lambda e: add_additional_to_history(app))

    def update_add_text():
        current_text = app.v_add.get()
        tokens = [t.strip() for t in current_text.split(",") if t.strip()]
        for name, var in app.add_choices.items():
            if var.get() == 1 and name not in tokens:
                tokens.append(name)
            elif var.get() == 0 and name in tokens:
                tokens.remove(name)
        new_text = ", ".join(tokens)
        if new_text != current_text:
            app.v_add.set(new_text)
        add_to_add_history(new_text)

    def add_to_add_history(text):
        text = text.strip()
        if text and text not in app.add_history:
            app.add_history.append(text)
            app.ent_add['values'] = app.add_history
            save_dropdown_cache(app.format_history, app.add_history)

    def sync_add_menu_with_text(*args):
        current_text = app.v_add.get()
        tokens = set(t.strip() for t in current_text.split(",") if t.strip())
        for name, var in app.add_choices.items():
            desired = 1 if name in tokens else 0
            if var.get() != desired:
                var.set(desired)

    app.v_add.trace_add("write", sync_add_menu_with_text)

    def on_add_selected(event):
        selected = app.ent_add.get()
        app.v_add.set(selected)
        add_to_add_history(selected)

    def on_add_focus_out(event):
        typed = app.ent_add.get()
        add_to_add_history(typed)

    app.ent_add.bind("<<ComboboxSelected>>", on_add_selected)
    app.ent_add.bind("<FocusOut>", on_add_focus_out)
