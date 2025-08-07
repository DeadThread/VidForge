#!/usr/bin/env python3
"""
Naming‑scheme editor (token list • two editors • live preview) - with color coding
"""

from __future__ import annotations
import os, sys, subprocess, re, datetime, tkinter as tk
from tkinter import ttk, font, messagebox
import json
from utils.logger_setup import logger
from utils.evaluator import Evaluator
from constants import TOKENS, SAMPLE_META

# Import PresetManager from scheme_editor module
from scheme_editor.preset_manager import PresetManager

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

        # Instantiate PresetManager
        self.preset_mgr = PresetManager()

        # Define color scheme
        self.filename_bg = "#e6f2ff"   # Light blue background
        self.filename_fg = "#003366"   # Dark blue text

        self.folder_bg = "#fff0e6"     # Light orange background
        self.folder_fg = "#663300"     # Dark orange text

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

        # --- Preset selector ---
        preset_frame = ttk.Frame(right)
        preset_frame.pack(fill="x", pady=(0, 6))

        ttk.Label(preset_frame, text="Preset:").pack(side="left")
        self.preset_combo = ttk.Combobox(preset_frame, state="readonly")
        self.preset_combo.pack(side="left", fill="x", expand=True, padx=(4, 0))
        self.preset_combo.bind("<<ComboboxSelected>>", self._on_preset_selected)

        # --- Folder Scheme with color coding ---
        lbl_folder = ttk.Label(right, text="Folder Scheme")
        lbl_folder.pack(anchor="w")
        lbl_folder.configure(foreground=self.folder_fg)

        self.txt_folder = tk.Text(
            right, height=2, wrap="none", font=fixed_bold,
            background=self.folder_bg,
            foreground=self.folder_fg,
            insertbackground=self.folder_fg
        )
        self.txt_folder.pack(fill="x")
        self.txt_folder.bind("<<Modified>>", self._on_edit)

        # --- Filename Scheme with color coding ---
        lbl_file = ttk.Label(right, text="Filename Scheme")
        lbl_file.pack(anchor="w", pady=(6, 0))
        lbl_file.configure(foreground=self.filename_fg)

        self.txt_file = tk.Text(
            right, height=2, wrap="none", font=fixed_bold,
            background=self.filename_bg,
            foreground=self.filename_fg,
            insertbackground=self.filename_fg
        )
        self.txt_file.pack(fill="x")
        self.txt_file.bind("<<Modified>>", self._on_edit)

        # --- Live Preview with color-coded content ---
        ttk.Label(right, text="Live Preview").pack(anchor="w", pady=(6, 0))

        style = ttk.Style(self)
        bg_col = style.lookup("TEntry", "fieldbackground") or "#eaeaea"

        self.txt_prev = tk.Text(
            right,
            height=5,
            wrap="word",
            background=bg_col,
            font=fixed_bold,
            state="disabled"
        )
        self.txt_prev.pack(fill="both", expand=True)

        # Configure tags for preview coloring
        self.txt_prev.tag_configure("folder_scheme", foreground=self.folder_fg)
        self.txt_prev.tag_configure("filename_scheme", foreground=self.filename_fg)

        self._make_read_only(self.txt_prev)

        # --- Buttons bar ---
        bar = ttk.Frame(right)
        bar.pack(fill="x", pady=(8, 0))

        ttk.Button(bar, text="Save", command=self._save).pack(side="right", padx=4)
        ttk.Button(bar, text="Reset", command=self._reset).pack(side="right")

        # Preset name entry + save button
        ttk.Label(bar, text="Preset Name:").pack(side="left", padx=(0, 4))
        self.preset_name_entry = ttk.Entry(bar, width=20)
        self.preset_name_entry.pack(side="left", padx=(0, 4))
        ttk.Button(bar, text="Save Preset", command=self._save_preset).pack(side="left")
        
        self._load_presets_into_combo()


    def _make_read_only(self, w: tk.Text):
        def block(event):
            # Allow Ctrl+C to pass through
            if (event.state & 0x4) and event.keysym.lower() == 'c':  # Ctrl+C
                return None
            return "break"

        for seq in ("<Key>", "<<Paste>>", "<Control-v>", "<Button-2>"):
            w.bind(seq, block)

        def ctx(e):
            m = tk.Menu(w, tearoff=0)
            m.add_command(label="Copy", command=lambda: w.event_generate("<<Copy>>"))
            m.tk_popup(e.x_root, e.y_root)
            m.grab_release()

        w.bind("<Button-3>", ctx)


    def _insert_token(self, *_):
        token = self.lb.get("active")
        focused_widget = self.focus_get()

        if focused_widget not in (self.txt_folder, self.txt_file):
            focused_widget = self.txt_folder
            focused_widget.focus_set()

        insert_pos = focused_widget.index("insert")
        focused_widget.insert("insert", token)
        self._refresh_preview()

    def _load_initial(self, scheme):
        folder_default = "%artist%/$year(date)"
        filename_default = "%artist% - %date% - %venue% - %city% [%format%] [%additional%]"
        if isinstance(scheme, dict):
            folder_def = scheme.get("folder") or scheme.get("folder_scheme") or folder_default
            filename_def = (
                scheme.get("filename") or 
                scheme.get("filename_scheme") or 
                scheme.get("saving_scheme") or 
                filename_default
            )
        elif isinstance(scheme, (list, tuple)) and len(scheme) == 2:
            folder_def, filename_def = scheme
        elif isinstance(scheme, str):
            folder_def = folder_default
            filename_def = scheme
        else:
            folder_def = folder_default
            filename_def = filename_default

        self.txt_folder.delete("1.0", "end")
        self.txt_file.delete("1.0", "end")
        self.txt_folder.insert("1.0", folder_def)
        self.txt_file.insert("1.0", filename_def)

    def _on_edit(self, e):
        e.widget.edit_modified(False)
        self._refresh_preview()

    def _refresh_preview(self):
        try:
            meta = self._get_meta() or SAMPLE_META.copy()

            folder_scheme = self.txt_folder.get("1.0", "end-1c")
            file_scheme = self.txt_file.get("1.0", "end-1c")

            ev = Evaluator(meta)
            evaluated_file = ev.eval(file_scheme)

            meta_with_filename = meta.copy()
            meta_with_filename["filename"] = evaluated_file
            ev2 = Evaluator(meta_with_filename)
            evaluated_folder = ev2.eval(folder_scheme)

            is_abs_path = os.path.isabs(evaluated_folder) or re.match(r"^[a-zA-Z]:[\\/]", evaluated_folder)

            if is_abs_path:
                preview_path_folder = evaluated_folder
                preview_path_file = evaluated_file
            else:
                root_folder = meta.get("output_folder") or self._root_path or "(Root)"
                preview_path_folder = os.path.join(root_folder, evaluated_folder)
                preview_path_file = evaluated_file

            # Normalize paths
            preview_path_folder = os.path.normpath(preview_path_folder).replace("\\", "/")
            preview_path_file = os.path.normpath(preview_path_file).replace("\\", "/")
            
            full_path = os.path.join(preview_path_folder, preview_path_file)
            full_path = os.path.normpath(full_path).replace("\\", "/")

            if len(full_path) > 400:
                full_path = full_path[:397] + "…"

            # Update preview with color coding
            self.txt_prev.config(state="normal")
            self.txt_prev.delete("1.0", "end")

            # Insert folder part with folder color
            if preview_path_folder != self._root_path and preview_path_folder != "(Root)":
                self.txt_prev.insert("end", preview_path_folder, "folder_scheme")
                if preview_path_file:
                    self.txt_prev.insert("end", "/")
            
            # Insert filename part with filename color
            if preview_path_file:
                self.txt_prev.insert("end", preview_path_file, "filename_scheme")

            self.txt_prev.config(state="disabled")

        except Exception as e:
            self.txt_prev.config(state="normal")
            self.txt_prev.delete("1.0", "end")
            self.txt_prev.insert("1.0", "Error generating preview.")
            self.txt_prev.config(state="disabled")


    def _save(self):
        folder_scheme = self.txt_folder.get("1.0", "end-1c")
        filename_scheme = self.txt_file.get("1.0", "end-1c")
        new_scheme = {"folder": folder_scheme, "filename": filename_scheme}

        print(f"Debug: Saving scheme: {new_scheme}")

        if callable(self._on_save):
            print("Debug: Calling _on_save callback")
            self._on_save(new_scheme)
        else:
            print("Debug: No _on_save callback found")

        self.destroy()


    def _reset(self):
        self.txt_folder.delete("1.0", "end")
        self.txt_file.delete("1.0", "end")
        self._load_initial(None)
        self._refresh_preview()


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


    # ────────────── PresetManager integration ──────────────
    def _load_presets_into_combo(self):
        presets = self.preset_mgr.load_presets()
        self.preset_combo["values"] = presets
        if presets:
            self.preset_combo.current(0)
            self._apply_preset(presets[0])

    def _on_preset_selected(self, event):
        preset_name = self.preset_combo.get()
        self._apply_preset(preset_name)

    def _apply_preset(self, preset_name):
        print(f"\n=== DEBUG _apply_preset('{preset_name}') ===")
        
        preset = self.preset_mgr.get_preset(preset_name)
        print(f"get_preset() returned: {preset}")
        
        if preset:
            folder_scheme = preset.get("folder_scheme", "")
            filename_scheme = preset.get("filename_scheme", "")
            
            print(f"folder_scheme to apply: '{folder_scheme}'")
            print(f"filename_scheme to apply: '{filename_scheme}'")
            
            # Clear and set folder
            print("Clearing folder text widget...")
            self.txt_folder.delete("1.0", "end")
            print(f"Inserting folder scheme: '{folder_scheme}'")
            self.txt_folder.insert("1.0", folder_scheme)
            
            # Clear and set filename
            print("Clearing filename text widget...")
            self.txt_file.delete("1.0", "end")
            print(f"Inserting filename scheme: '{filename_scheme}'")
            self.txt_file.insert("1.0", filename_scheme)
            
            # Verify what was actually inserted
            actual_folder = self.txt_folder.get("1.0", "end-1c")
            actual_filename = self.txt_file.get("1.0", "end-1c")
            print(f"Actual folder content after insert: '{actual_folder}'")
            print(f"Actual filename content after insert: '{actual_filename}'")
            
            print("Calling _refresh_preview()...")
            self._refresh_preview()
            print("=== END DEBUG ===\n")
        else:
            print("No preset data returned!")
            print("=== END DEBUG ===\n")

    def _save_preset(self):
        name = self.preset_name_entry.get().strip()
        if not name:
            messagebox.showerror("Error", "Please enter a preset name.")
            return
        folder_scheme = self.txt_folder.get("1.0", "end-1c")
        filename_scheme = self.txt_file.get("1.0", "end-1c")
        
        # Use filename_scheme instead of saving_scheme to match your preset file format
        self.preset_mgr.add_preset(name, filename_scheme, folder_scheme)
        self._load_presets_into_combo()
        self.preset_combo.set(name)
        messagebox.showinfo("Success", f"Preset '{name}' saved.")


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

    editor = SchemeEditor(
        master=app,
        root_path=init_root,
        get_live_metadata=lambda: app._get_live_metadata(),
        initial_scheme=saved,
        on_save=lambda new_scheme: save_naming_scheme(new_scheme, app),
    )

    editor.grab_set()
    editor.focus_set()
    app.wait_window(editor)