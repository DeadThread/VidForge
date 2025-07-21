import tkinter as tk
import os
from tkinter import ttk


def enable_inline_autocomplete(cb: ttk.Combobox, values_cb):
    """
    Enables inline autocomplete for a Combobox.
    """
    cb._disable_autocomplete = False

    def _complete(ev=None):
        if cb._disable_autocomplete:
            cb._disable_autocomplete = False
            return

        # Ignore Tab here so global tab handler manages it
        if ev and ev.keysym in ("Tab", "Right", "End", "Return"):
            cb.icursor("end")
            cb.select_clear()
            if ev.keysym != "Tab":   # block non-Tab keys
                return "break"
            # For Tab, allow propagation by NOT returning "break"
            return

        if ev and (len(ev.keysym) == 1 and not ev.char.isprintable()):
            return

        typed = cb.get()
        if not typed:
            cb.select_clear()
            return

        tnorm = typed.lower()
        for cand in values_cb():
            if cand.lower().startswith(tnorm):
                if cand != typed:
                    cb.delete(0, "end")
                    cb.insert(0, cand)
                    cb.select_range(len(typed), "end")
                break
        else:
            cb.select_clear()

    def _on_keypress(ev):
        if ev.keysym in ("BackSpace", "Delete"):
            cb._disable_autocomplete = True

    for event_name in ("<KeyRelease>", "<Right>", "<End>", "<Return>", "<Tab>"):
        cb.bind(event_name, _complete, add="+")
    cb.bind("<KeyPress>", _on_keypress, add="+")


def setup_autocomplete(app):
    """
    Set up autocomplete for the artist, venue, and city comboboxes.
    """
    enable_inline_autocomplete(app.cb_artist, lambda: app.cb_artist["values"])
    enable_inline_autocomplete(app.cb_venue, lambda: app.cb_venue["values"])
    enable_inline_autocomplete(app.cb_city, lambda: app.cb_city["values"])


def setup_custom_tab_order(app):
    """
    Set up a custom tab order, skipping Clear Fields button & Override Date checkbox.
    """
    tab_order = [
        app.cb_artist,
        app.cb_venue,
        app.cb_city,
        app.cb_year,
        app.cb_month,
        app.cb_day,
        app.v_format,
        app.v_add,
        app.cb_make_poster,
        app.cb_template,
    ]

    setup_global_tab_order(app, tab_order)

    def on_tab_press(event):
        if event.widget == tab_order[-1]:
            tab_order[0].focus_set()
            return "break"  # Prevent default behavior to avoid losing focus cycle

    # Bind on last widget for both Tab and Shift+Tab
    tab_order[-1].bind("<Tab>", on_tab_press)


def setup_context_menu(app):
    """
    Set up a context menu for the tree widget with options to rename, delete, open, and open location.
    """
    menu = tk.Menu(app, tearoff=0)
    menu.add_command(label="Rename",  command=lambda: rename_item(app))
    menu.add_command(label="Delete",  command=lambda: delete_item(app))
    menu.add_command(label="Open",    command=lambda: open_item(app))
    menu.add_command(label="Open File Location",
                     command=lambda: open_file_location(app))

    loc_idx = menu.index("end")  # index of the last item (open-location)

    def on_right_click(event):
        iid = app.tree.identify_row(event.y)
        if not iid:
            return
        app.tree.selection_set(iid)

        path  = app.tree.item(iid, "values")[0]
        label = "Open Folder Location" if os.path.isdir(path) \
                else "Open File Location"
        menu.entryconfig(loc_idx, label=label)   # update label

        menu.tk_popup(event.x_root, event.y_root)

    app.context_menu = menu
    app.tree.bind("<Button-3>",         on_right_click)  # Win/Linux
    app.tree.bind("<Control-Button-1>", on_right_click)  # macOS


def prompt_photoshop_path_if_first_boot(app):
    """
    Check if it's the first boot and prompt for Photoshop path.
    """
    # Your existing logic for this function goes here
    pass

def setup_global_tab_order(root, tab_order):
    """
    Set up a custom tab order for the root widget.
    """
    def on_tab_press(event):
        widget = event.widget
        # Only handle if widget is in tab_order
        if widget not in tab_order:
            return  # allow default tab behavior

        idx = tab_order.index(widget)

        if event.state & 0x1:  # Shift pressed
            next_idx = (idx - 1) % len(tab_order)
        else:
            next_idx = (idx + 1) % len(tab_order)

        tab_order[next_idx].focus_set()
        return "break"

    # Bind globally on root for Tab and Shift+Tab keys
    root.bind_all("<Tab>", on_tab_press, add="+")
    root.bind_all("<Shift-Tab>", on_tab_press, add="+")
