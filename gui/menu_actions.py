import os
import sys
import shutil
import subprocess
from tkinter import simpledialog, messagebox
from utils.logger_setup import logger  # Assuming logger utility is present for logging actions


def rename_item(app):
    selected = app.tree.selection()
    if not selected:
        return
    iid = selected[0]
    old_path = app.tree.item(iid, "values")[0]
    old_name = os.path.basename(old_path)

    new_name = simpledialog.askstring("Rename", f"Rename '{old_name}' to:", initialvalue=old_name)
    if not new_name or new_name == old_name:
        return

    new_path = os.path.join(os.path.dirname(old_path), new_name)
    try:
        os.rename(old_path, new_path)
        app.tree.item(iid, text=new_name, values=(new_path,))
        app._log(f"Renamed '{old_name}' → '{new_name}'")
    except Exception as e:
        messagebox.showerror("Error", f"Rename failed: {e}")

def delete_item(app):
    sel = app.tree.selection()
    if not sel:
        return
    iid  = sel[0]
    path = app.tree.item(iid, "values")[0]
    if not messagebox.askyesno("Delete", f"Delete '{path}'?"):
        return
    try:
        (shutil.rmtree if os.path.isdir(path) else os.remove)(path)
        app.tree.delete(iid)
        app._log(f"Deleted '{path}'")
    except Exception as e:
        messagebox.showerror("Error", f"Delete failed: {e}")

def open_item(app):
    sel = app.tree.selection()
    if not sel:
        return
    path = app.tree.item(sel[0], "values")[0]
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception as e:
        messagebox.showerror("Error", f"Open failed: {e}")

def open_file_location(app):
    sel = app.tree.selection()
    if not sel:
        return
    path = app.tree.item(sel[0], "values")[0]
    if not os.path.exists(path):
        messagebox.showerror("Error", "Path no longer exists.")
        return
    try:
        if sys.platform.startswith("win"):
            args = ["explorer"]
            args += ["/select,", os.path.normpath(path)] if os.path.isfile(path) \
                    else [os.path.normpath(path)]
            subprocess.Popen(args)

        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R" if os.path.isfile(path) else "", path])

        else:  # Linux / *nix
            folder = path if os.path.isdir(path) else os.path.dirname(path)
            fm_cmds = [
                ("nautilus", ["nautilus", "--select", path]),
                ("dolphin",  ["dolphin",  "--select", path]),
                ("thunar",   ["thunar",   "--select", path]),
                ("nemo",     ["nemo",     "--no-desktop", folder]),
            ]
            for exe, cmd in fm_cmds:
                if shutil.which(exe):
                    subprocess.Popen(cmd)
                    break
            else:
                subprocess.Popen(["xdg-open", folder])
    except Exception as e:
        messagebox.showerror("Error", f"Open File Location failed: {e}")

def setup_tree_context_menu(app):
    app.tree_context_menu = tk.Menu(app.tree, tearoff=0)
    app.tree_context_menu.add_command(label="Rename", command=lambda: rename_item(app))
    app.tree_context_menu.add_command(label="Delete", command=lambda: delete_item(app))
    app.tree_context_menu.add_command(label="Open", command=lambda: open_item(app))
    app.tree_context_menu.add_command(label="Open File Location", command=lambda: open_file_location(app))

    app.tree.bind("<Button-3>", _show_tree_context_menu)

def _show_tree_context_menu(event):
    try:
        app.tree_context_menu.tk_popup(event.x_root, event.y_root)
    finally:
        app.tree_context_menu.grab_release()
