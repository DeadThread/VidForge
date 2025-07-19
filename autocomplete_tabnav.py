import tkinter as tk
from tkinter import ttk

def enable_inline_autocomplete(cb: ttk.Combobox, values_cb):
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

def setup_global_tab_order(root, tab_order):
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
