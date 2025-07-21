import json
from pathlib import Path
import tkinter as tk
from tkinter import ttk, simpledialog, messagebox

# Function to load artist aliases from a file
def load_artist_aliases(assets_dir, log_func=print):
    aliases_path = Path(assets_dir) / "artist_aliases.json"
    if aliases_path.exists():
        try:
            with open(aliases_path, "r", encoding="utf-8") as f:
                aliases = json.load(f)
            log_func(f"Loaded {len(aliases)} artist aliases.")
            return aliases
        except Exception as e:
            log_func(f"Failed to load artist aliases: {e}")
            return {}
    else:
        log_func("No artist_aliases.json found, starting with empty dict.")
        return {}

# Function to save artist aliases to a file
def save_artist_aliases(artist_aliases, assets_dir, log_func=print):
    aliases_path = Path(assets_dir) / "artist_aliases.json"
    try:
        with open(aliases_path, "w", encoding="utf-8") as f:
            json.dump(artist_aliases, f, indent=2, ensure_ascii=False)
        log_func(f"Saved {len(artist_aliases)} artist aliases to {aliases_path}")
    except Exception as e:
        log_func(f"Error saving artist aliases: {e}")

# Function to extract artist from filename
def extract_artist(filename, artist_aliases, log_func=print):
    filename_lower = filename.lower()
    log_func(f"[DEBUG] Attempting artist extraction from filename: '{filename}'")

    tokens = filename.split(" ")
    log_func(f"[DEBUG] Filename tokens: {tokens}")

    matches = []

    for alias, real_artist in artist_aliases.items():
        log_func(f"[DEBUG] Checking if alias '{alias}' exists as an exact match in filename tokens...")

        if alias.lower() in [token.lower() for token in tokens]:
            log_func(f"[DEBUG] Exact alias match found: '{alias}' → '{real_artist}'")
            matches.append((alias, real_artist))

    if matches:
        exact_matches = [match for match in matches if match[0].lower() in [token.lower() for token in tokens]]
        if exact_matches:
            matched_artist = exact_matches[0][1]
            log_func(f"[DEBUG] Final exact match: '{matched_artist}'")
        else:
            matched_artist = matches[0][1]
            log_func(f"[DEBUG] Final match after checking all tokens: '{matched_artist}'")
    else:
        log_func(f"[DEBUG] [ARTIST] No exact match found for artist in filename: '{filename}'")

    return matched_artist

# Function to open the artist alias editor GUI
def open_alias_editor(parent, artist_aliases, save_callback):
    """GUI editor for managing artist aliases."""
    win = tk.Toplevel(parent)
    win.title("Edit Artist Aliases")
    win.geometry("500x400")
    win.transient(parent)
    win.grab_set()

    tree = ttk.Treeview(win, columns=("Alias", "FullName"), show="headings")
    tree.heading("Alias", text="Alias")
    tree.heading("FullName", text="Full Artist Name")
    tree.pack(fill="both", expand=True, padx=10, pady=10)

    def refresh_tree():
        tree.delete(*tree.get_children())
        for alias, full in artist_aliases.items():
            tree.insert("", "end", values=(alias, full))

    def add_alias():
        win.focus_set()
        win.lift()
        alias = simpledialog.askstring("New Alias", "Enter alias:", parent=win)
        if not alias:
            return
        win.focus_set()
        win.lift()
        full = askstring_focused("Full Artist Name", "Enter full artist name:", win)
        if not full:
            return
        artist_aliases[alias.strip()] = full.strip()
        refresh_tree()

    def edit_selected():
        selected = tree.selection()
        if not selected:
            messagebox.showinfo("Edit Alias", "No alias selected.", parent=win)
            return
        alias, full = tree.item(selected[0])["values"]
        win.focus_set()
        win.lift()
        new_alias = simpledialog.askstring("Edit Alias", "Alias:", initialvalue=alias, parent=win)
        if new_alias is None:
            return
        win.focus_set()
        win.lift()
        new_full = simpledialog.askstring("Edit Full Name", "Full Artist Name:", initialvalue=full, parent=win)
        if new_full is None:
            return
        if alias != new_alias:
            if alias in artist_aliases:
                del artist_aliases[alias]
        artist_aliases[new_alias.strip()] = new_full.strip()
        refresh_tree()

    def delete_selected():
        selected = tree.selection()
        if not selected:
            messagebox.showinfo("Delete Alias", "No alias selected.", parent=win)
            return
        alias = tree.item(selected[0])["values"][0]
        if messagebox.askyesno("Confirm Delete", f"Delete alias '{alias}'?", parent=win):
            if alias in artist_aliases:
                del artist_aliases[alias]
            refresh_tree()

    def save_and_close():
        save_artist_aliases(artist_aliases, "assets", print)
        save_callback()
        win.destroy()

    btns = ttk.Frame(win)
    btns.pack(pady=5)

    ttk.Button(btns, text="Add", width=10, command=add_alias).grid(row=0, column=0, padx=5)
    ttk.Button(btns, text="Edit", width=10, command=edit_selected).grid(row=0, column=1, padx=5)
    ttk.Button(btns, text="Delete", width=10, command=delete_selected).grid(row=0, column=2, padx=5)
    ttk.Button(btns, text="Done", width=10, command=save_and_close).grid(row=0, column=3, padx=5)

    refresh_tree()

    win.update_idletasks()
    parent.update_idletasks()

    parent_x = parent.winfo_rootx()
    parent_y = parent.winfo_rooty()
    parent_width = parent.winfo_width()
    parent_height = parent.winfo_height()

    win_width = win.winfo_width()
    win_height = win.winfo_height()

    x = parent_x + (parent_width // 2) - (win_width // 2)
    y = parent_y + (parent_height // 2) - (win_height // 2)

    win.geometry(f"{win_width}x{win_height}+{x}+{y}")

    win.focus_set()
    win.lift()

    win.bind("<Return>", lambda event: add_alias())

# Helper function for getting a focused string from the user
def askstring_focused(title: str, prompt: str, parent) -> str | None:
    dialog = tk.Toplevel(parent)
    dialog.title(title)
    dialog.transient(parent)
    dialog.grab_set()

    tk.Label(dialog, text=prompt).pack(padx=10, pady=(10, 0))
    entry_var = tk.StringVar()
    entry = tk.Entry(dialog, textvariable=entry_var)
    entry.pack(padx=10, pady=10)
    entry.focus_set()

    btn_frame = tk.Frame(dialog)
    btn_frame.pack(pady=(0, 10))

    result = {"value": None}

    def on_ok():
        result["value"] = entry_var.get()
        dialog.destroy()

    def on_cancel():
        dialog.destroy()

    tk.Button(btn_frame, text="OK", width=8, command=on_ok).pack(side="left", padx=5)
    tk.Button(btn_frame, text="Cancel", width=8, command=on_cancel).pack(side="left", padx=5)

    entry.bind("<Return>", lambda event: on_ok())

    parent.update_idletasks()
    dialog.update_idletasks()

    pw = parent.winfo_width()
    ph = parent.winfo_height()
    px = parent.winfo_rootx()
    py = parent.winfo_rooty()

    dw = dialog.winfo_reqwidth()
    dh = dialog.winfo_reqheight()

    x = px + (pw // 2) - (dw // 2)
    y = py + (ph // 2) - (dh // 2)

    dialog.geometry(f"+{x}+{y}")

    dialog.wait_window()
    return result["value"]
