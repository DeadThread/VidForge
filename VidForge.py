#!/usr/bin/env python3
# VidForge.py  – stable baseline
# ----------------------------------------------------------------------
import configparser
import datetime
import json
import logging
import os
import re
import subprocess
import sys
import threading
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, simpledialog, ttk

from constants import ASSETS_DIR, CONFIG_DIR, CONFIG_FILE, ICON_PATH, TEMPL_DIR, SAMPLE_META
from gui.gui_builder import (
    build_gui,
    load_dropdown_cache,
    save_dropdown_cache,
)
from gui.naming_editor import SchemeEditor
from utils import theme_manager
from utils.artist_aliases import load_artist_aliases, open_alias_editor, save_artist_aliases
from utils.cache_manager import (
    cache_add_value,
    cache_get_list,
    load_cache,
    load_naming_scheme,
    save_naming_scheme,
)
from utils.cache_utils import save_cache
from utils.file_helpers import create_missing_txt_files, _browse
from utils.logger_setup import appflow, logger
from utils.metadata_manager import (
    extract_root_folder,
    refresh_dropdowns,
    reload_metadata,
    replace_tokens_in_path,
    gather_meta,
    normalize_name
)
from utils.naming_renderer import build_proposed_name
from utils.pane_persistence import install_pane_persistence
from utils.poster_generator import close_photoshop, generate_poster
from utils.queue_helpers import clear_queue, remove_selected, save_current
from utils.queue_manager import process_queue, process_queue_with_ui
from utils.ref_file_manager import load_reference_list
from utils.template_manager import (
    on_template_selected,
    scan_templates,
    update_template_dropdown,
)
from utils.text_utils import infer_from_name
from utils.theme_manager import load_ttk_theme, remove_theme, restore_saved_theme, load_and_apply_theme
from utils.tree_manager import fast_populate_tree as populate_tree
from gui.template_dropdown import set_poster_controls_state  # <-- Add this import

# ── ensure dirs ───────────────────────────────────────
os.makedirs(CONFIG_DIR, exist_ok=True)
os.makedirs(ASSETS_DIR, exist_ok=True)
os.makedirs(TEMPL_DIR, exist_ok=True)

DEFAULT_FOLDER_SCHEME = "%artist%/$year(date)"
DEFAULT_FILENAME_SCHEME = "%artist% - %date% - %venue% - %city% [%format%] [%additional%]"


class VideoTagger(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("VidForge")
        self.geometry("1600x900")
        try:
            self.iconbitmap(ICON_PATH)
        except Exception:
            pass

        self.assets_dir = ASSETS_DIR

        self.config_parser = configparser.ConfigParser(interpolation=None)
        self.config_parser.read(CONFIG_FILE)

        _saved = self.config_parser.get("Settings", "output_folder", fallback="").strip()
        self.output_dir = tk.StringVar(value=_saved if _saved and os.path.isdir(_saved) else "")

        self.cache = load_cache(log_func=lambda m: None)

        saved_scheme = load_naming_scheme()
        if saved_scheme:
            self.naming_scheme = saved_scheme
        else:
            raw_scheme = self.config_parser.get("Settings", "naming_scheme", fallback="")
            try:
                if raw_scheme.strip().startswith("{"):
                    self.naming_scheme = json.loads(raw_scheme)
                    if not isinstance(self.naming_scheme, dict):
                        raise ValueError("naming_scheme JSON must be an object")
                    if self.naming_scheme.get("folder") == "%artist%/%year%":
                        self.naming_scheme["folder"] = "%artist%/$year(date)"
                    self.naming_scheme.setdefault("folder", DEFAULT_FOLDER_SCHEME)
                    self.naming_scheme.setdefault("filename", DEFAULT_FILENAME_SCHEME)
                else:
                    self.naming_scheme = {
                        "folder": DEFAULT_FOLDER_SCHEME,
                        "filename": raw_scheme or DEFAULT_FILENAME_SCHEME,
                    }
            except Exception as e:
                print(f"[WARN] Could not parse naming_scheme from config.ini: {e}")
                self.naming_scheme = {
                    "folder": DEFAULT_FOLDER_SCHEME,
                    "filename": DEFAULT_FILENAME_SCHEME,
                }

        self._log = lambda msg: (logger.info(msg), appflow.info(msg))

        self.root_dir = tk.StringVar()
        self.current_fp = None
        self.queue, self.meta = [], {}
        self.hist = {"additional": set()}

        cache_data = load_cache(log_func=lambda m: None)
        self.artists_list = cache_data.get("Artists.txt", load_reference_list("Artists.txt"))
        self.cities_list = cache_data.get("Cities.txt", load_reference_list("Cities.txt"))
        self.venues_list = cache_data.get("Venues.txt", load_reference_list("Venues.txt"))

        self.artist = {normalize_name(a): a for a in self.artists_list}
        self.city = {normalize_name(c): c for c in self.cities_list}
        self.venue = {normalize_name(v): v for v in self.venues_list}

        self.artist_aliases = load_artist_aliases(self.assets_dir, log_func=self._log)

        self.tpl_map = scan_templates(TEMPL_DIR)
        self._current_mode = "top"
        self._current_artist = None

        build_gui(self)

        self.cb_artist["values"] = self.artists_list
        self.cb_city["values"] = self.cities_list
        self.cb_venue["values"] = self.venues_list

        self._pending_logs = []

        self.cb_template.bind("<<ComboboxSelected>>", lambda e=None: on_template_selected(self))

        def gui_log(msg: str):
            self.log.insert("end", f"[{datetime.now():%H:%M:%S}] {msg}\n")
            self.log.see("end")
            logger.info(msg)
            appflow.info(msg)

        self._log = gui_log

        for m in self._pending_logs:
            self._log(m)

        self._load_and_apply_theme()
        reload_metadata(self)

    def _load_and_apply_theme(self):
        load_and_apply_theme(self, self.config_parser, self._log)

    def _remove_theme(self):
        theme_manager.remove_theme(self, self.config_parser, CONFIG_FILE, self._log)

    def save_artist_aliases(self):
        save_artist_aliases(self.artist_aliases, self.assets_dir, log_func=self._log)

    def open_naming_scheme_editor(self, current_scheme):
        """
        Open the naming scheme editor window to allow the user to modify the folder and filename scheme.
        """
        def on_save_callback(new_scheme):
            """
            Callback when naming scheme is saved.
            """
            self.on_scheme_save(new_scheme)

        def get_live_metadata(app):
            """
            Extract live metadata for the scheme editor.
            If live metadata is not available, merge with SAMPLE_META.
            """
            meta = app._get_live_metadata() or SAMPLE_META.copy()  # Ensure SAMPLE_META is merged
            meta["output_folder"] = app.output_dir.get() or "(Root)"
            return meta

        # Create and open the SchemeEditor with the necessary parameters
        editor = SchemeEditor(
            master=self,
            root_path=self.output_dir.get() or "(Root)",
            get_live_metadata=lambda: get_live_metadata(self),  # Pass the merged metadata lambda
            initial_scheme=current_scheme,
            on_save=on_save_callback
        )

        editor.grab_set()
        editor.focus_set()
        self.wait_window(editor)


    def on_scheme_save(self, new_scheme):
        """
        Save naming scheme persistently and update UI/logging.
        """
        # Save naming scheme persistently (to JSON file)
        save_naming_scheme(new_scheme)

        # Update in-memory scheme
        self.naming_scheme = new_scheme

        # Evaluate folder for display/logging
        current_meta = self._get_live_metadata() if hasattr(self, "_get_live_metadata") else SAMPLE_META
        ev = _Evaluator(current_meta)
        evaluated_folder = ev.eval(new_scheme.get("folder", "(none)"))

        self._log(f"Naming scheme saved: {json.dumps(new_scheme)}")
        self._log(f"Evaluated output folder: {evaluated_folder}")

        # Optionally update GUI output folder variable
        # self.output_dir.set(evaluated_folder)

    def open_alias_editor(self):
        open_alias_editor(self, self.artist_aliases, self.save_artist_aliases)

    def _generate_poster(self, artist, md, dest_dir, last_job, make_poster, template_sel, template_folder):
        from utils.photoshop_helper import get_photoshop_path

        PS_EXE = get_photoshop_path()
        if not PS_EXE:
            self._log("❌ Photoshop is not configured. Set it from the menu.")
            return

        generate_poster(
            PS_EXE=PS_EXE,
            artist=artist,
            md=md,
            dest_dir=dest_dir,
            last_job=last_job,
            make_poster=make_poster,
            template_sel=template_sel,
            template_folder=template_folder,
            tpl_map=self.tpl_map,
            templ_dir=TEMPL_DIR,
            close_photoshop_func=close_photoshop,
            log_func=self._log,
        )

    def _add_reload_metadata_menu(self):
        # Find Tools menu if exists, else create it
        tools_menu = None
        for i in range(self.menubar.index("end") + 1):
            if self.menubar.type(i) == "cascade" and self.menubar.entrycget(i, "label") == "Tools":
                tools_menu = self.menubar.nametowidget(self.menubar.entrycget(i, "menu"))
                break
        if tools_menu is None:
            tools_menu = tk.Menu(self.menubar, tearoff=0)
            self.menubar.add_cascade(label="Tools", menu=tools_menu)

        # Add separator and the Refresh Metadata command
        tools_menu.add_separator()
        tools_menu.add_command(label="Refresh Metadata", command=self._reload_metadata)

    def reset_naming_scheme_to_defaults(self):
        self.naming_scheme = {
            "folder": DEFAULT_FOLDER_SCHEME,
            "filename": DEFAULT_FILENAME_SCHEME,
        }

        # Update config_parser
        if not self.config_parser.has_section("Settings"):
            self.config_parser.add_section("Settings")
        self.config_parser.set("Settings", "folder_scheme", DEFAULT_FOLDER_SCHEME)
        self.config_parser.set("Settings", "filename_scheme", DEFAULT_FILENAME_SCHEME)
        # Also save naming_scheme as JSON string
        self.config_parser.set("Settings", "naming_scheme", json.dumps(self.naming_scheme, ensure_ascii=False))

        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            self.config_parser.write(f)

        if hasattr(self, "folder_scheme"):
            self.folder_scheme.set(DEFAULT_FOLDER_SCHEME)
        if hasattr(self, "filename_scheme"):
            self.filename_scheme.set(DEFAULT_FILENAME_SCHEME)

        if getattr(self, "scheme_editor", None) and self.scheme_editor.winfo_exists():
            ed = self.scheme_editor
            ed.txt_folder.delete("1.0", "end")
            ed.txt_file.delete("1.0", "end")
            ed.txt_folder.insert("1.0", DEFAULT_FOLDER_SCHEME)
            ed.txt_file.insert("1.0", DEFAULT_FILENAME_SCHEME)
            ed._refresh_preview()

        self._log("Naming schemes reset to defaults")
        logger.info("Naming schemes reset to defaults via Edit menu")

    def _get_live_metadata(self) -> dict:
        """Gather live metadata from the app fields."""
        artist = self.v_artist.get() or "Phish"
        year = self.v_year.get() or "1995"  # Default to 1995 if empty
        month = self.v_month.get() or "12"  # Default to December if empty
        day = self.v_day.get() or "31"  # Default to 31st if empty
        date = f"{year}-{month}-{day}"  # Construct the date string
        venue = self.v_venue.get() or "Madison Square Garden"
        city = self.v_city.get() or "New York, NY"
        fmt = self.v_format.get() or "2160p"
        addl = self.v_add.get() or "SBD"
        raw_root = self.output_dir.get() or "(Root)"
        
        return {
            "artist": artist,
            "date": date,  # Ensure date is correctly set
            "venue": venue,
            "city": city,
            "format": fmt,
            "additional": addl,
            "output_folder": raw_root,
        }

    def evaluate_output_folder(self, md: dict) -> str:
        """
        Evaluate the folder scheme using metadata, returning the full output folder path.
        If folder scheme evaluates to an absolute path, return it directly.
        If relative, join with self.output_dir (root output folder).
        """
        folder_template = self.naming_scheme.get("folder", "")

        if not folder_template:
            return self.output_dir.get() or os.getcwd()

        # Replace tokens in the folder template (use the function from metadata_manager)
        folder_path = replace_tokens_in_path(folder_template, md, md.get("artist", ""), md.get("date", ""))

        if os.path.isabs(folder_path):
            return folder_path
        else:
            root = self.output_dir.get() or os.getcwd()
            return os.path.normpath(os.path.join(root, folder_path))

    def on_scheme_save(self, new_scheme):
        """
        Update naming scheme and save it in config.ini
        Also evaluates folder and filename and updates output folder.
        """
        self.naming_scheme = new_scheme

        folder_scheme = new_scheme.get("folder", "")
        filename_scheme = new_scheme.get("filename", "")

        root_folder = extract_root_folder(folder_scheme)
        current_meta = self._get_live_metadata()

        # Evaluate filename scheme
        evaluated_filename = replace_tokens_in_path(
            filename_scheme,
            current_meta,
            current_meta.get("artist", ""),
            current_meta.get("year", ""),
        )

        # Replace %filename% token in folder scheme
        folder_scheme_with_filename = folder_scheme.replace("%filename%", evaluated_filename)

        # Replace $year(<key>) token in folder scheme
        def repl_year(match):
            date_key = match.group(1)
            date_str = current_meta.get(date_key, "")
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                return str(dt.year)
            except Exception:
                return ""

        folder_scheme_with_filename = re.sub(r"\$year\((\w+)\)", repl_year, folder_scheme_with_filename)

        # Replace remaining tokens in folder scheme
        evaluated_folder = replace_tokens_in_path(
            folder_scheme_with_filename,
            current_meta,
            current_meta.get("artist", ""),
            current_meta.get("year", ""),
        )

        self._log(f"Current Folder Scheme (evaluated): {evaluated_folder}")
        self._log(f"Current Filename Scheme (evaluated): {evaluated_filename}")

        # Auto-sync output folder if root folder exists
        if root_folder and os.path.isabs(root_folder) and os.path.isdir(root_folder):
            if root_folder != self.output_dir.get():
                self.output_dir.set(root_folder)
                self._log(f"Output folder auto-synced to: {root_folder}")

                if not self.config_parser.has_section("Settings"):
                    self.config_parser.add_section("Settings")
                self.config_parser.set("Settings", "output_folder", root_folder)
                with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                    self.config_parser.write(f)

        # Normalize evaluated folder to absolute path
        if not os.path.isabs(evaluated_folder):
            base = self.output_dir.get() or os.getcwd()
            evaluated_folder = os.path.normpath(os.path.join(base, evaluated_folder))

        self._log(f"Current Output Folder: {evaluated_folder}")

        # Save updated naming scheme to config.ini
        if not self.config_parser.has_section("Settings"):
            self.config_parser.add_section("Settings")
        self.config_parser.set("Settings", "naming_scheme", json.dumps(new_scheme, ensure_ascii=False))
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            self.config_parser.write(f)

    def _select_photoshop_location(self):
        """Menu‑bar handler: let the user pick / change the Photoshop exe."""
        path = filedialog.askopenfilename(
            title="Select Photoshop Executable",
            filetypes=[("Executable files", "*.exe" if os.name == "nt" else "*"), ("All files", "*.*")]
        )
        if not path:
            self._log("Photoshop location unchanged.")
            return

        self.photoshop_path = path
        if not self.config_parser.has_section("Settings"):
            self.config_parser.add_section("Settings")
        self.config_parser.set("Settings", "photoshop_path", path)
        with open(CONFIG_FILE, "w", encoding="utf-8") as fh:
            self.config_parser.write(fh)

        self._log(f"Photoshop location set to: {path}")
        set_poster_controls_state(self, enabled=True)  # This will work now
        self.update_idletasks()

    def _scan_templates(self):
        self.tpl_map = scan_templates(TEMPL_DIR)
        self._log(f"Template folders re-scanned: {len(self.tpl_map)} folders found")
        update_template_dropdown(self)

    def _open_readme(self):
        import webbrowser

        readme_path = os.path.join(os.path.dirname(__file__), "README.md")
        if os.path.isfile(readme_path):
            webbrowser.open(readme_path)
            self._log(f"Opened README at {readme_path}")
        else:
            messagebox.showerror("Error", "README file not found.")
            self._log("Failed to open README: file not found")

    def _open_tips(self):
        import webbrowser

        tips_path = os.path.join(os.path.dirname(__file__), "TIPS.md")
        if os.path.isfile(tips_path):
            webbrowser.open(tips_path)
            self._log(f"Opened Useful Tips at {tips_path}")
        else:
            messagebox.showerror("Error", "Tips file not found.")
            self._log("Failed to open Useful Tips: file not found")

    def _select_node(self, event=None):
        sel = self.tree.selection()
        if not sel:
            return
        fp = self.tree.item(sel[0], "values")[0]
        if not os.path.isfile(fp):
            return
        self.current_fp = fp

        meta = infer_from_name(
            os.path.basename(fp),
            self.artist,
            self.city,
            self.venue,
            self.artist_aliases,
        )

        self.v_artist.set(meta.get("artist", ""))
        self.v_format.set(meta.get("format", ""))
        self.v_venue.set(meta.get("venue", ""))
        self.v_city.set(meta.get("city", ""))
        self.v_add.set(meta.get("additional", ""))

        if meta.get("date"):
            y, m, d = meta["date"].split("-")
            self.v_year.set(y)
            self.v_month.set(m)
            self.v_day.set(d)
        else:
            self.v_year.set("")
            self.v_month.set("")
            self.v_day.set("")

        norm_fp = os.path.normpath(fp)
        self._log(f"Selected {norm_fp} → {meta}")

    def _process_queue(self):
        process_queue_with_ui(self)

    def save_config(self):
        """Save naming scheme and output folder to config.ini persistently."""
        try:
            if not self.config_parser.has_section("Settings"):
                self.config_parser.add_section("Settings")
            self.config_parser.set("Settings", "naming_scheme", json.dumps(self.naming_scheme, ensure_ascii=False))
            if self.output_dir.get():
                self.config_parser.set("Settings", "output_folder", self.output_dir.get())
            elif self.config_parser.has_option("Settings", "output_folder"):
                self.config_parser.remove_option("Settings", "output_folder")

            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                self.config_parser.write(f)

            self._log("Configuration saved.")

            # Save artist aliases
            aliases_path = os.path.join(ASSETS_DIR, "artist_aliases.json")
            save_artist_aliases(self.artist_aliases, self.assets_dir, log_func=self._log)

        except Exception as e:
            logger.error(f"Error saving config: {e}")
            self._log(f"Error saving config: {e}")

    def on_closing(self):
        self._log("Application closing. Saving config...")
        self.save_config()
        self.destroy()


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    create_missing_txt_files(ASSETS_DIR, ["Artists.txt", "Cities.txt", "Venues.txt"])
    logging.getLogger("vidforge").propagate = False
    logging.getLogger("vidforge.app").propagate = False
    app = VideoTagger()
    app.mainloop()
