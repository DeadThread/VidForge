#!/usr/bin/env python3
"""
Naming‑scheme editor (token list • two editors • live preview)
"""

from __future__ import annotations
import os, sys, subprocess, re, datetime, tkinter as tk
from tkinter import ttk, font, messagebox
import json
from utils.logger_setup import logger
from utils.evaluator import Evaluator
from constants import TOKENS, SAMPLE_META

class SchemeEditor(tk.Toplevel):
    def __init__(self, master=None, *, root_path: str = "(Root)",
                 get_live_metadata=None, initial_scheme=None, on_save=None):
        super().__init__(master)
        self.title("Naming‑Scheme Editor")
        self.geometry("900x520")
        self.minsize(720, 420)

        self._root_path = root_path or "(Root)"
        self._get_meta = get_live_metadata  # Now accepts 'app'
        self._on_save = on_save

        self._build_gui()
        self._load_initial(initial_scheme)
        self._refresh_preview()  # first paint


    # ───────────────────────────────────────── UI
    def _build_gui(self):
        menubar = tk.Menu(self)
        self.config(menu=menubar)
        helpm = tk.Menu(menubar, tearoff=False)
        menubar.add_cascade(label="Help", menu=helpm)
        helpm.add_command(label="Open README", command=self._open_readme)

        main = ttk.PanedWindow(self, orient="horizontal")
        main.pack(fill="both", expand=True, padx=8, pady=8)

        # token list
        left = ttk.Frame(main, padding=4)
        main.add(left, weight=1)
        ttk.Label(left, text="Tokens / Functions").pack(anchor="w")
        self.lb = tk.Listbox(left, activestyle="none", exportselection=False)
        self.lb.pack(side="left", fill="both", expand=True)
        for t in TOKENS:
            self.lb.insert("end", t)
        ttk.Scrollbar(left, command=self.lb.yview).pack(side="right", fill="y")
        self.lb.bind("<Double-Button-1>", self._insert_token)

        # editors & preview
        right = ttk.Frame(main, padding=4)
        main.add(right, weight=3)

        fixed = font.nametofont("TkFixedFont")

        # Create bold font variant for all text fields
        fixed_bold = fixed.copy()
        fixed_bold.configure(weight="bold")

        ttk.Label(right, text="Folder Scheme").pack(anchor="w")
        self.txt_folder = tk.Text(right, height=2, wrap="none", font=fixed_bold)
        self.txt_folder.pack(fill="x")
        self.txt_folder.bind("<<Modified>>", self._on_edit)

        ttk.Label(right, text="Filename Scheme").pack(anchor="w", pady=(6, 0))
        self.txt_file = tk.Text(right, height=2, wrap="none", font=fixed_bold)
        self.txt_file.pack(fill="x")
        self.txt_file.bind("<<Modified>>", self._on_edit)

        ttk.Label(right, text="Live Preview").pack(anchor="w", pady=(6, 0))

        # Get ttk theme's entry background for consistent background color
        style = ttk.Style(self)
        bg_col = style.lookup("TEntry", "fieldbackground") or "#eaeaea"

        # Helper to invert hex color
        def invert_color(color_str):
            if not color_str.startswith("#") or len(color_str) != 7:
                return color_str  # fallback
            r = 255 - int(color_str[1:3], 16)
            g = 255 - int(color_str[3:5], 16)
            b = 255 - int(color_str[5:7], 16)
            return f"#{r:02x}{g:02x}{b:02x}"

        # Get folder scheme selection colors
        folder_sel_bg = self.txt_folder.cget("selectbackground") or "#3399FF"
        folder_sel_fg = self.txt_folder.cget("selectforeground") or "#FFFFFF"

        # Invert for live preview selection colors
        live_sel_bg = invert_color(folder_sel_bg)
        live_sel_fg = invert_color(folder_sel_fg)

        self.txt_prev = tk.Text(
            right,
            height=5,
            wrap="word",
            background=bg_col,
            font=fixed_bold,
            selectbackground=live_sel_bg,
            selectforeground=live_sel_fg
        )
        self.txt_prev.pack(fill="both", expand=True)
        self._make_read_only(self.txt_prev)

        bar = ttk.Frame(right)
        bar.pack(fill="x", pady=(8, 0))
        ttk.Button(bar, text="Save", command=self._save).pack(side="right", padx=4)
        ttk.Button(bar, text="Reset", command=self._reset).pack(side="right")

    def _make_read_only(self, w: tk.Text):
        # block key presses but allow selection and copy (Ctrl+C)
        def block(event):
            # Allow Ctrl+C to pass through
            if (event.state & 0x4) and event.keysym.lower() == 'c':  # Ctrl+C
                return None  # don't block
            return "break"

        for seq in ("<Key>", "<<Paste>>", "<Control-v>", "<Button-2>"):
            w.bind(seq, block)

        # context menu
        def ctx(e):
            m = tk.Menu(w, tearoff=0)
            m.add_command(label="Copy", command=lambda: w.event_generate("<<Copy>>"))
            m.tk_popup(e.x_root, e.y_root)
            m.grab_release()

        w.bind("<Button-3>", ctx)

    def _insert_token(self, *_):
        token = self.lb.get("active")
        focused_widget = self.focus_get()
        print(f"Focused widget: {focused_widget}")

        if focused_widget not in (self.txt_folder, self.txt_file):
            print("Focus is NOT on folder or file editor. Forcing focus to folder editor.")
            focused_widget = self.txt_folder
            focused_widget.focus_set()

        # Show insertion index for debugging
        insert_pos = focused_widget.index("insert")
        print(f"Inserting token at position: {insert_pos}")

        focused_widget.insert("insert", token)
        self._refresh_preview()

    # ───────────────────────────────────────── helpers
    def _load_initial(self, scheme):
        folder_default = "%artist%/$year(date)"
        filename_default = "%artist% - %date% - %venue% - %city% [%format%] [%additional%]"
        if isinstance(scheme, dict):
            folder_def = scheme.get("folder", folder_default)
            filename_def = scheme.get("filename", filename_default)
        elif isinstance(scheme, (list, tuple)) and len(scheme) == 2:
            folder_def, filename_def = scheme
        elif isinstance(scheme, str):
            folder_def = folder_default
            filename_def = scheme
        else:
            folder_def = folder_default
            filename_def = filename_default
        self.txt_folder.insert("1.0", folder_def)
        self.txt_file.insert("1.0", filename_def)

    def _on_edit(self, e):
        e.widget.edit_modified(False)
        self._refresh_preview()

    # ───────────────────────────────────────── preview

    def _refresh_preview(self):
        """Refresh the preview of the naming scheme."""
        print("Refreshing preview...")

        try:
            # Ensure SAMPLE_META is merged with live metadata from self._get_meta()
            meta = self._get_meta() or SAMPLE_META.copy()  # Use SAMPLE_META if _get_meta returns None

            # Get folder and file schemes from text widgets
            folder_scheme = self.txt_folder.get("1.0", "end-1c")
            file_scheme = self.txt_file.get("1.0", "end-1c")

            print(f"Folder scheme: {folder_scheme}")
            print(f"File scheme: {file_scheme}")

            # Create Evaluator instance for file scheme
            ev = Evaluator(meta)
            evaluated_file = ev.eval(file_scheme)

            # Add filename to the metadata and create a new Evaluator for folder scheme
            meta_with_filename = meta.copy()
            meta_with_filename["filename"] = evaluated_file
            ev2 = Evaluator(meta_with_filename)
            evaluated_folder = ev2.eval(folder_scheme)

            # Check if the evaluated folder path is an absolute path
            is_abs_path = os.path.isabs(evaluated_folder) or re.match(r"^[a-zA-Z]:[\\/]", evaluated_folder)

            if is_abs_path:
                preview_path = os.path.join(evaluated_folder, evaluated_file)
            else:
                root_folder = meta.get("output_folder") or self._root_path or "(Root)"
                preview_path = os.path.join(root_folder, evaluated_folder, evaluated_file)

            # Normalize the path to fix mixed slashes
            preview_path = os.path.normpath(preview_path)

            # Truncate the preview path if it's too long
            if len(preview_path) > 400:
                preview_path = preview_path[:397] + "…"

            # Update the preview text widget with the generated path
            self.txt_prev.config(state="normal")
            self.txt_prev.delete("1.0", "end")
            self.txt_prev.insert("1.0", preview_path)
            self.txt_prev.config(state="disabled")

        except Exception as e:
            print(f"Error refreshing preview: {e}")
            self.txt_prev.config(state="normal")
            self.txt_prev.delete("1.0", "end")
            self.txt_prev.insert("1.0", "Error generating preview.")
            self.txt_prev.config(state="disabled")

    # ───────────────────────────────────────── buttons
    def _save(self):
        folder_scheme = self.txt_folder.get("1.0", "end-1c")
        filename_scheme = self.txt_file.get("1.0", "end-1c")
        new_scheme = {"folder": folder_scheme, "filename": filename_scheme}

        if callable(self._on_save):
            self._on_save(new_scheme)

        self.destroy()

    def _reset(self):
        self.txt_folder.delete("1.0", "end")
        self.txt_file.delete("1.0", "end")
        self._load_initial(None)
        self._refresh_preview()

    # ───────────────────────────────────────── README
    def _open_readme(self):
        try:
            path = os.path.join(os.path.dirname(__file__), "read_me_scheme.md")
            if not os.path.isfile(path):
                raise FileNotFoundError(path)
            if sys.platform.startswith("win"):
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            messagebox.showerror("Error", f"Could not open README: {e}")


# Updated `open_naming_editor_popup` function
def open_naming_editor_popup(app):
    """
    Opens the Naming‑Scheme Editor modal, seeds it with live metadata,
    and keeps the GUI log + config.ini in sync.
    """
    saved = get_naming_scheme_from_config(app) or {
        "folder": "%artist%/$year(date)",
        "filename": "%artist% - %date% - %venue% - %city% [%format%] [%additional%]",
    }

    init_root = (
        _extract_root(saved.get("folder", "")) or
        _clean_root(app.output_dir.get() or "(Root)") or
        "(Root)"
    )

    # Pass the correct metadata retrieval lambda
    editor = SchemeEditor(
        master=app,
        root_path=init_root,
        get_live_metadata=lambda: app._get_live_metadata(),  # Pass the method correctly
        initial_scheme=saved,
        on_save=lambda new_scheme: save_naming_scheme(new_scheme, app),
    )

    editor.grab_set()
    editor.focus_set()
    app.wait_window(editor)
    


