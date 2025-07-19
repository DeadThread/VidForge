"""
Tree-manager helpers
────────────────────
fast_populate_tree(app, root_path)
    Lazily fills app.tree with folders & files.
    Only the first visible level is inserted at start; deeper levels are
    populated when the user expands a folder, so the GUI never stalls.
"""

from __future__ import annotations
import os
import tkinter as tk
from tkinter import messagebox
from utils.text_utils import infer_from_name
import logging

log = logging.getLogger("vidforge")


# ───────────────────────────────── helpers ────────────────────────────
def _add_dummy_child(tree, parent_iid: str) -> None:
    """Insert a dummy child so the ▶ expander arrow appears."""
    tree.insert(parent_iid, "end")  # empty row (no values/text)


def _populate_children(app, parent_iid: str, folder_path: str) -> None:
    """Insert the real children of *folder_path* under *parent_iid*."""
    try:
        entries = sorted(os.scandir(folder_path),
                         key=lambda e: (not e.is_dir(), e.name.lower()))
    except Exception as e:
        log.warning("Cannot open %s: %s", folder_path, e)
        entries = []

    for ent in entries:
        iid = app.tree.insert(parent_iid, "end",
                              text=ent.name,
                              open=False,
                              values=(ent.path,))
        if ent.is_dir():
            _add_dummy_child(app.tree, iid)  # placeholder for lazy load


def _on_open(event: tk.Event) -> None:
    """<<TreeviewOpen>> handler – populate children on first expand."""
    tree: tk.ttk.Treeview = event.widget
    iid = tree.focus()
    # Skip if already populated (dummy removed)
    if not iid or tree.get_children(iid) and tree.item(tree.get_children(iid)[0], "values"):
        return

    app = tree._app_ref  # back-reference set in fast_populate_tree
    folder_path = tree.item(iid, "values")[0]
    # Remove dummy then populate real children
    tree.delete(*tree.get_children(iid))
    _populate_children(app, iid, folder_path)


# ─────────────────────────── public API ───────────────────────────────
def fast_populate_tree(app, root_path: str):
    """
    Clear the Treeview and lazily populate it starting at *root_path*.
    Use this instead of the old progress-bar bulk loader.
    """
    if not root_path or not os.path.isdir(root_path):
        messagebox.showerror("Error", "Select valid root folder")
        return

    app.tree.delete(*app.tree.get_children())
    app._log(f"Scanning {root_path}")

    # Populate the top-level items
    _populate_children(app, "", root_path)

    # Attach <<TreeviewOpen>> handler once
    if not getattr(app.tree, "_lazy_bound", False):
        # store back-reference so handler can reach app
        app.tree._app_ref = app
        app.tree.bind("<<TreeviewOpen>>", _on_open)
        app.tree._lazy_bound = True
