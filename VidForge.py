#!/usr/bin/env python
# VidForge.py  – stable baseline
# ----------------------------------------------------------------------
import os, sys, logging, subprocess, configparser, json
import sys
import logging
log = logging.getLogger("vidforge")
import subprocess                     # ← NEW: needed on macOS/Linux
import configparser
import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox, ttk
from datetime import datetime
import threading                                     # (only used in _process_queue)
from utils.cache_manager import load_cache, cache_add_value, cache_get_list  # Updated import
from gui.gui_builder      import build_gui, _set_poster_controls_state
from gui.naming_editor import SchemeEditor, SAMPLE_META  # <-- changed from NamingEditor to SchemeEditor
from utils.logger_setup    import logger, appflow
from utils.queue_manager   import process_queue
from utils.metadata_manager import refresh_dropdowns
from utils.file_helpers    import create_missing_txt_files
from utils.ref_file_manager import load_reference_list
from utils.text_utils      import infer_from_name
from utils.template_manager import scan_templates, update_template_dropdown
from utils.poster_generator import generate_poster, close_photoshop
from utils.theme_manager   import load_ttk_theme
from utils.queue_helpers   import save_current, remove_selected, clear_queue
from utils.pane_persistence import install_pane_persistence
from utils import theme_manager
from constants import CONFIG_DIR, CONFIG_FILE, ASSETS_DIR, TEMPL_DIR, ICON_PATH
from utils.tree_manager import fast_populate_tree as populate_tree
from gui.gui_builder import load_dropdown_cache

# ── ensure dirs ───────────────────────────────────────────────────────
os.makedirs(CONFIG_DIR, exist_ok=True)
os.makedirs(ASSETS_DIR,  exist_ok=True)
os.makedirs(TEMPL_DIR,   exist_ok=True)

DEFAULT_FOLDER_SCHEME   = "%artist%/$year(date)"
DEFAULT_FILENAME_SCHEME = "%artist% - %date% - %venue% - %city% [%format%] [%additional%]"

# ----------------------------------------------------------------------
class VideoTagger(tk.Tk):
    # ──────────────────────────────────────────────────────────────────
    #  constructor
    # ──────────────────────────────────────────────────────────────────
    def __init__(self):
        super().__init__()

        # ---------- basic window setup ----------
        self.title("VidForge")
        self.geometry("1600x900")
        try:
            self.iconbitmap(ICON_PATH)
        except Exception:
            pass
        self.assets_dir = ASSETS_DIR

        # ---------- configuration parser ----------
        self.config_parser = configparser.ConfigParser(interpolation=None)
        os.makedirs(CONFIG_DIR, exist_ok=True)          # make sure config dir exists
        self.config_parser.read(CONFIG_FILE)

        # ----- output folder (start blank unless user previously CHOSE one) -----
        _saved = self.config_parser.get("Settings", "output_folder", fallback="").strip()
        self.output_dir = tk.StringVar(value=_saved if _saved and os.path.isdir(_saved) else "")

        # ---------- naming scheme (robust load) ----------
        raw_scheme = self.config_parser.get("Settings", "naming_scheme", fallback="")
        try:
            if raw_scheme.strip().startswith("{"):              # JSON style
                self.naming_scheme = json.loads(raw_scheme)
                if not isinstance(self.naming_scheme, dict):
                    raise ValueError("naming_scheme JSON must be an object")
                
                # Fix old folder scheme here
                if self.naming_scheme.get("folder") == "%artist%/%year%":
                    self.naming_scheme["folder"] = "%artist%/$year(date)"
                
                self.naming_scheme.setdefault("folder", "%artist%/$year(date)")
                self.naming_scheme.setdefault("filename", "%artist% - %date% - %venue% - %city% [%format%] [%additional%]")
            else:                                               # legacy single string
                self.naming_scheme = {
                    "folder":   "%artist%/$year(date)",
                    "filename": raw_scheme or "%artist% - %date% - %venue% - %city% [%format%] [%additional%]",
                }
        except Exception as e:
            print(f"[WARN] Could not parse naming_scheme from config.ini: {e}")
            self.naming_scheme = {
                "folder":   "%artist%/$year(date)",
                "filename": "%artist% - %date% - %venue% - %city% [%format%] [%additional%]",
            }

        # ------------------- temporary logger ------------------------
        self._log = lambda m: (logger.info(m), appflow.info(m))

        # ------------------- state -----------------------------------
        self.root_dir   = tk.StringVar()
        self.current_fp = None
        self.queue, self.meta = [], {}
        self.hist = {"additional": set()}

        # Load reference data
        cache_data = load_cache(log_func=lambda m: None)  # silent load

        self.artists_list = cache_data.get("Artists.txt", load_reference_list("Artists.txt"))
        self.cities_list  = cache_data.get("Cities.txt",  load_reference_list("Cities.txt"))
        self.venues_list  = cache_data.get("Venues.txt",  load_reference_list("Venues.txt"))

        from utils.metadata_manager import normalize_name
        self.artist = {normalize_name(a): a for a in self.artists_list}
        self.city   = {normalize_name(c): c for c in self.cities_list}
        self.venue  = {normalize_name(v): v for v in self.venues_list}

        # --- Initialize artist aliases dict ---
        self.artist_aliases = {}
        self.load_artist_aliases()

        # ------------------- template map ----------------------------
        self.tpl_map    = scan_templates(TEMPL_DIR)
        self.tpl_stage  = "folders"
        self.tpl_artist = None

        # ------------------- theme -----------------------------------
        theme = self.config_parser.get("Theme", "file", fallback=None)
        self._pending_logs: list[str] = []
        if theme and os.path.isfile(theme):
            load_ttk_theme(self, theme, lambda m: self._pending_logs.append(m))
        else:
            self._pending_logs.append("No saved theme loaded")

        # pre‑bind template‑select callback
        self._template_selected = self._on_template_selected

        # ------------------- GUI build -------------------------------
        build_gui(self)  # creates self.log, frames…

        # combobox dropdown data
        self.cb_artist["values"] = self.artists_list
        self.cb_city["values"]   = self.cities_list
        self.cb_venue["values"]  = self.venues_list

        # ------------------- GUI‑aware logger ------------------------
        def gui_log(msg: str):
            self.log.insert("end", f"[{datetime.now():%H:%M:%S}] {msg}\n")
            self.log.see("end")
            logger.info(msg)
            appflow.info(msg)
        self._log = gui_log

        # log widget context menu
        self._setup_log_context_menu()

        # flush any logs collected before GUI existed
        for m in self._pending_logs:
            self._log(m)

        self._reload_metadata()

    def load_artist_aliases(self):
        # Load aliases from file or memory
        # For example, read from a JSON or TXT file:
        aliases_path = ASSETS_DIR / "artist_aliases.json"
        if aliases_path.exists():
            with open(aliases_path, "r", encoding="utf-8") as f:
                self.artist_aliases = json.load(f)
        else:
            self.artist_aliases = {}

        # ------------------- initial status lines --------------------
        self._log(f"Current Folder Scheme: {self.naming_scheme.get('folder', '')}")
        self._log(f"Current Filename Scheme: {self.naming_scheme.get('filename', '')}")
        self._log(f"Current Output Folder: {self.output_dir.get() or '(File root)'}")

    def save_artist_aliases(self):
        aliases_path = ASSETS_DIR / "artist_aliases.json"
        try:
            with open(aliases_path, "w", encoding="utf-8") as f:
                json.dump(self.artist_aliases, f, indent=2, ensure_ascii=False)
            self._log(f"Saved {len(self.artist_aliases)} artist aliases to {aliases_path}")
        except Exception as e:
            self._log(f"Error saving artist aliases: {e}")

    def open_naming_scheme_editor(self, current_scheme):
        def on_save_callback(new_scheme):
            save_to_cache("naming_scheme", new_scheme)
            self.on_scheme_save(new_scheme)  # <-- Use your central save handler

        SchemeEditor(self, initial_scheme=current_scheme, on_save=on_save_callback)

    def on_save_callback(new_scheme):
        save_to_cache("naming_scheme", new_scheme)

        # Get current metadata for token evaluation
        current_meta = self._get_live_metadata() if hasattr(self, '_get_live_metadata') else SAMPLE_META

        # Evaluate the folder template to get actual folder path
        ev = _Evaluator(current_meta)
        evaluated_folder = ev.eval(new_scheme.get("folder", "(none)"))

        save_to_cache("output_folder", evaluated_folder)

        self._log(f"Current Naming Scheme: {json.dumps(new_scheme)}")
        self._log(f"Current Output Folder: {evaluated_folder}")        

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


    # ────────────────────────────────────────────────────────────────
    # Edit ▸ Reset Naming Scheme to Default   (called from gui_builder)
    # ────────────────────────────────────────────────────────────────
    def reset_naming_scheme_to_defaults(self):
        self.naming_scheme = {
            "folder":  DEFAULT_FOLDER_SCHEME,
            "filename": DEFAULT_FILENAME_SCHEME,
        }

        self.config_parser.setdefault("Settings", {})
        self.config_parser.set("Settings", "folder_scheme", DEFAULT_FOLDER_SCHEME)
        self.config_parser.set("Settings", "filename_scheme", DEFAULT_FILENAME_SCHEME)
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



    # ──────────────────────────────────────────────────────────────────
    #  callback helpers
    # ──────────────────────────────────────────────────────────────────
    def _get_live_meta(self):
        return {
            "artist": self.v_artist.get(), "venue": self.v_venue.get(),
            "city":   self.v_city.get(),   "year":  self.v_year.get(),
            "month":  self.v_month.get(),  "day":   self.v_day.get(),
            "format": self.v_format.get(), "additional": self.v_add.get(),
        }

    # 1. Update GUI after resetting naming scheme
    def _reset_naming_scheme(self):
        self.naming_scheme = {
            "folder": "",
            "filename": "ARTIST - DATE - VENUE - CITY [FORMAT] [ADDITIONAL]"
        }
        self._log("Naming scheme reset to default.")
        # Update GUI editor with the filename scheme part, if you want:
        self.naming_scheme_editor.set(self.naming_scheme["filename"])

    # 2. Ensure renaming uses the correct scheme
    def _build_proposed_name(self, md):
        year, month, day = md.get("year", ""), md.get("month", ""), md.get("day", "")
        date_str = f"{year}-{month.zfill(2)}-{day.zfill(2)}" if (year and month and day) else ""

        # Use the filename part of naming_scheme dict, fallback to default string
        scheme = self.naming_scheme.get("filename", "ARTIST - DATE - VENUE - CITY [FORMAT] [ADDITIONAL]")

        name = scheme
        name = name.replace("ARTIST", md.get("artist", ""))
        name = name.replace("VENUE",  md.get("venue",  ""))
        name = name.replace("DATE",   date_str)
        name = name.replace("CITY",   md.get("city",   ""))
        name = name.replace("[FORMAT]",     f"[{md.get('format','')}]"     if md.get("format")     else "")
        name = name.replace("[ADDITIONAL]", f"[{md.get('additional','')}]" if md.get("additional") else "")
        name = " ".join(name.split()).strip()
        for sep in (" - ", "--", "- -"):
            if name.startswith(sep): name = name[len(sep):]
            if name.endswith(sep):   name = name[:-len(sep)]
        return name
    
    def _remove_theme(self):
        theme_manager.remove_theme(self, self.config_parser, CONFIG_FILE, self._log)
    # ------------------------------------------------------------------
    #  Template combo‑box two‑stage drill‑down
    # ------------------------------------------------------------------
    def _on_template_selected(self, _=None):
        sel = self.v_template.get()
        if self.tpl_stage == "folders":
            if sel in ("", "Default"):
                return
            self.tpl_artist = sel
            self.cb_template["values"] = ["⬅ Back"] + self.tpl_map.get(sel, [])
            self.v_template.set("")
            self.tpl_stage = "psds"
            self.after(10, lambda: self.cb_template.event_generate("<Button-1>"))
        else:
            if sel == "⬅ Back":
                self.cb_template["values"] = ["Default"] + sorted(self.tpl_map.keys())
                self.v_template.set("Default")
                self.tpl_stage = "folders"
                self.tpl_artist = None
                self.after(10, lambda: self.cb_template.event_generate("<Button-1>"))

    def evaluate_output_folder(self, md: dict) -> str:
        """
        Evaluate the folder scheme using metadata, returning the full output folder path.
        If folder scheme evaluates to absolute path, return it directly.
        If relative, join with self.output_dir (root output folder).
        """
        folder_template = self.naming_scheme.get("folder", "")
        if not folder_template:
            # no folder scheme, fallback to root output folder or current directory
            return self.output_dir.get() or os.getcwd()

        # Replace tokens in folder template (reuse your replace_tokens_in_path)
        folder_path = self.replace_tokens_in_path(folder_template, md, md.get("artist",""), md.get("date",""))

        if os.path.isabs(folder_path):
            return folder_path
        else:
            root = self.output_dir.get() or os.getcwd()
            return os.path.normpath(os.path.join(root, folder_path))


    # ------------------------------------------------------------------
    #  other menu / UI callbacks  (same as your last good version)
    # ------------------------------------------------------------------
    def _open_txt_file(self, filename: str):
        """Open a text file for editing in the default system editor."""
        file_path = os.path.join(self.assets_dir, filename)  # Path to the file in /assets
        if os.path.exists(file_path):
            try:
                if sys.platform == 'win32':  # Windows
                    subprocess.Popen(['start', '', file_path], shell=True)  # Using Popen instead of run
                elif sys.platform == 'darwin':  # macOS
                    subprocess.Popen(['open', file_path])  # macOS uses `open` to launch the default editor
                else:  # Linux and others
                    subprocess.Popen(['xdg-open', file_path])  # Linux uses `xdg-open` for the default editor
            except subprocess.CalledProcessError as e:
                self._log(f"Error opening {filename} with system editor: {e}")
        else:
            messagebox.showerror("File Not Found", f"The file {filename} does not exist.")

    def _maybe_sync_output_dir(self, folder_template: str):
        """
        If the folder template starts with an absolute path, copy that absolute
        prefix into self.output_dir.  Otherwise do nothing.
        """
        # Evaluate %tokens% with empty meta, just to expose any hard‑coded prefix
        abs_check = self.evaluate_scheme(folder_template, {})
        if os.path.isabs(abs_check):
            # keep only the drive / first directory of the absolute template
            root_prefix = os.path.splitdrive(abs_check)[0] or abs_check.split(os.sep)[0]
            if root_prefix and root_prefix != self.output_dir.get():
                self.output_dir.set(root_prefix)
                self._log(f"Output folder auto‑synced to: {root_prefix}")

    def _browse(self):
        d = filedialog.askdirectory()
        if not d:
            return

        # 1) remember the new root
        self.root_dir.set(d)
        populate_tree(self, d)

        # 2) if the user has **not** explicitly chosen an output‑folder
        #    this session, make it follow the root automatically
        if not self.output_dir.get():
            self.output_dir.set(d)
            self._log(f"Output folder now follows root → {d}")


    def _change_output_folder(self):
        d = filedialog.askdirectory(title="Select Output Folder")
        if not d:
            return
        self.output_dir.set(d)
        self.config_parser.setdefault("Settings", {})
        self.config_parser.set("Settings", "output_folder", d)
        with open(CONFIG_FILE, "w") as f:
            self.config_parser.write(f)
        self._log(f"Output folder changed to {d}")
        logger.info(f"Output folder saved to config.ini: {d}")

    def extract_root_folder(self, folder_scheme: str) -> str | None:
        """
        Extract the root folder from the folder scheme by cutting off at the first token (%...%).
        Returns None if no literal root path found.
        """
        idx = folder_scheme.find('%')
        if idx == -1:
            root = folder_scheme.strip()
        elif idx == 0:
            root = ""
        else:
            root = folder_scheme[:idx].rstrip('/\\')
        return root if root else None

    def on_scheme_save(self, new_scheme):
        self.naming_scheme = new_scheme

        folder_scheme = self.naming_scheme.get("folder", "")
        filename_scheme = self.naming_scheme.get("filename", "")
        root_folder = self.extract_root_folder(folder_scheme)

        current_meta = self._get_live_meta()

        # 1. Evaluate filename scheme first (simple token replace)
        evaluated_filename = self.replace_tokens_in_path(
            filename_scheme,
            current_meta,
            current_meta.get("artist", ""),
            current_meta.get("year", ""),
        )

        # 2. Replace %filename% in folder scheme with evaluated filename string
        folder_scheme_with_filename = folder_scheme.replace("%filename%", evaluated_filename)

        # 3. Handle special token $year(...) in folder scheme
        def repl_year(match):
            date_key = match.group(1)
            date_str = current_meta.get(date_key, "")
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                return str(dt.year)
            except Exception:
                return ""

        folder_scheme_with_filename = re.sub(r"\$year\((\w+)\)", repl_year, folder_scheme_with_filename)

        # 4. Now replace remaining tokens (%key%) in folder scheme
        evaluated_folder = self.replace_tokens_in_path(
            folder_scheme_with_filename,
            current_meta,
            current_meta.get("artist", ""),
            current_meta.get("year", ""),
        )

        self._log(f"Current Folder Scheme (evaluated): {evaluated_folder}")
        self._log(f"Current Filename Scheme (evaluated): {evaluated_filename}")

        # If the extracted root folder is an absolute existing path, update output_dir
        if root_folder and os.path.isabs(root_folder) and os.path.isdir(root_folder):
            if root_folder != self.output_dir.get():
                self.output_dir.set(root_folder)
                self._log(f"Output folder auto-synced to: {root_folder}")

                # Save updated output folder to config file
                self.config_parser.setdefault("Settings", {})
                self.config_parser.set("Settings", "output_folder", root_folder)
                with open(CONFIG_FILE, "w") as f:
                    self.config_parser.write(f)

        # Also log the evaluated output folder path
        # If relative path, prepend output_dir or cwd
        if not os.path.isabs(evaluated_folder):
            base = self.output_dir.get() or os.getcwd()
            evaluated_folder = os.path.normpath(os.path.join(base, evaluated_folder))

        self._log(f"Current Output Folder: {evaluated_folder}")


    def open_naming_editor(app):
        def get_live_meta():
            meta = app.get_current_metadata() or {}
            meta = dict(meta)  # copy to avoid side effects
            meta["output_folder"] = app.output_dir.get() or "(Root)"
            return meta

        print(f"[DEBUG] Opening naming editor with scheme: {app.naming_scheme}")

        editor = SchemeEditor(
            master=app,
            get_live_metadata=get_live_meta,
            initial_scheme=app.naming_scheme,
            on_save=app.on_scheme_save,
        )
        editor.wait_window()


    def _select_photoshop_location(self):
        """Menu‑bar handler: let the user pick / change the Photoshop exe."""
        path = filedialog.askopenfilename(
            title="Select Photoshop Executable",
            filetypes=[("Executable files", "*.exe" if os.name == "nt" else "*"),
                    ("All files", "*.*")]
        )
        if not path:                # user hit Cancel
            self._log("Photoshop location unchanged.")
            return

        # ── persist ───────────────────────────────────────────────────────
        self.photoshop_path = path
        self.config_parser.setdefault("Settings", {})
        self.config_parser.set("Settings", "photoshop_path", path)
        with open(CONFIG_FILE, "w", encoding="utf-8") as fh:
            self.config_parser.write(fh)

        # ── log & re‑enable poster UI ─────────────────────────────────────
        self._log(f"Photoshop location set to: {path}")
        _set_poster_controls_state(self, enabled=True)      #  ←  ADD THIS LINE
        self.update_idletasks()                    #  ← add this line

    def _scan_templates(self):
        # Re-scan folder, update map
        self.tpl_map = scan_templates(TEMPL_DIR)
        self._log(f"Template folders re-scanned: {len(self.tpl_map)} folders found")

        # Update the template dropdown with new data
        # IMPORTANT: self.cb_template must exist at this point
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

        # Infer metadata from filename using your existing dictionaries
        meta = infer_from_name(
            os.path.basename(fp),
            self.artist,
            self.city,
            self.venue,
            self.artist_aliases,
        )

        # Now set the GUI variables from meta
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
        log.debug(f"Selected {norm_fp} → {meta}")

    def extract_root_folder(path_pattern: str) -> str:
        # Normalize slashes for consistent splitting
        normalized = path_pattern.replace("\\", "/")

        token_pos = normalized.find("%")
        if token_pos == -1:
            # no tokens, whole path is root
            return normalized.rstrip("/")

        # Take substring before first token (literal path)
        root = normalized[:token_pos].rstrip("/")
        return root

    def replace_tokens_in_path(path_template: str, md: dict, artist: str, date: str) -> str:
        year = md.get("year", "") or (date[:4] if date else "")
        month = md.get("month", "")
        day = md.get("day", "")

        date_tok = ""
        if year and month and day:
            date_tok = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        elif year and month:
            date_tok = f"{year}-{month.zfill(2)}"
        elif year:
            date_tok = year

        repl = {
            "%artist%": artist,
            "%year%": year,
            "%date%": date_tok or date,
            "%venue%": md.get("venue", ""),
            "%city%": md.get("city", ""),
            "%format%": md.get("format", ""),
            "%additional%": md.get("additional", ""),
        }
        out = path_template
        for token, val in repl.items():
            out = out.replace(token, val)
        return out

    def _process_queue(self):
        """Run the queued rename/move jobs, then reset the queue UI."""
        if not self.queue:
            messagebox.showinfo("Queue empty", "Add files first.")
            return
        if not self.root_dir.get():
            messagebox.showerror("No root", "Pick root folder.")
            return

        self._log("Starting queue processing …")

        # ── extract folder & filename patterns as plain strings ───────
        folder_pattern = ""
        filename_pattern = ""
        ns = self.naming_scheme  # may be dict, JSON‑text, or legacy str

        if isinstance(ns, dict):
            folder_pattern = ns.get("folder", "")
            filename_pattern = ns.get("filename", "")

        elif isinstance(ns, str):
            stripped = ns.strip()
            # If the single string looks like JSON, parse it; else treat as legacy filename pattern
            if stripped.startswith("{") and stripped.endswith("}"):
                try:
                    ns_dict = json.loads(stripped)
                    if isinstance(ns_dict, dict):
                        folder_pattern = ns_dict.get("folder", "")
                        filename_pattern = ns_dict.get("filename", "")
                    else:
                        filename_pattern = stripped
                except json.JSONDecodeError:
                    filename_pattern = stripped
            else:
                filename_pattern = stripped  # legacy: whole string is filename pattern

        # ---- hand work off to the worker ----------------------------
        process_queue(
            queue=self.queue,
            meta=self.meta,
            root_dir=self.root_dir.get(),
            log_func=self._log,
            generate_poster_func=self._generate_poster,
            close_photoshop_func=close_photoshop,
            tpl_map=self.tpl_map,
            templ_dir=TEMPL_DIR,
            output_dir=self.output_dir.get() or None,
            folder_scheme=folder_pattern,  # <- folder pattern string
            filename_scheme=filename_pattern,  # <- filename pattern string
        )

        # ---- finished → reset UI & internal state -------------------
        clear_queue(self)
        self._log("Queue processed and cleared.")

        from gui.gui_builder import load_dropdown_cache, save_dropdown_cache
        

        def move_last_to_top(lst, last):
            if not lst or not last:
                return lst
            lst = [item for item in lst if item != last]
            return [last] + lst

        # Load existing cache history
        cache = load_dropdown_cache()

        format_hist = cache.get("format_history", [])
        add_hist = cache.get("add_history", [])

        current_format = self.v_format.get().strip()
        current_add = self.v_add.get().strip()

        if current_format:
            format_hist = [current_format] + [f for f in format_hist if f != current_format]

        if current_add:
            add_hist = [current_add] + [a for a in add_hist if a != current_add]

        save_dropdown_cache(format_hist, add_hist)

        # Update combobox values with MRU on top
        self.ent_format['values'] = format_hist
        self.ent_add['values'] = add_hist

        # Set selected values again
        self.v_format.set(current_format)
        self.v_add.set(current_add)

        self._reload_metadata()

        if self.root_dir.get():
            populate_tree(self, self.root_dir.get())  
            
        # ------------------------------------------------------------------
    #  Log widget right-click Copy context menu
    # ------------------------------------------------------------------
    def _setup_log_context_menu(self):
        self.log_context_menu = tk.Menu(self.log, tearoff=0)
        self.log_context_menu.add_command(label="Copy", command=self._copy_log_selection)
        # Bind right-click (Windows/Linux: Button-3, macOS: Button-2)
        self.log.bind("<Button-3>", self._show_log_context_menu)
        self.log.bind("<Button-2>", self._show_log_context_menu)

    def _show_log_context_menu(self, event):
        try:
            self.log_context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.log_context_menu.grab_release()

    def _copy_log_selection(self):
        try:
            selected_text = self.log.selection_get()
        except tk.TclError:
            # No selection, copy all
            selected_text = self.log.get("1.0", "end-1c")
        self.clipboard_clear()
        self.clipboard_append(selected_text)
        self._log("Log text copied to clipboard.")



    # ------------------------------------------------------------------
    #  queue‑tree setup
    # ------------------------------------------------------------------
    def _setup_queue_tree(self):
        frame = self.frame_queue
        for w in frame.winfo_children():
            w.destroy()

        self.queue_tree = ttk.Treeview(frame,
                                       columns=("original", "proposed"),
                                       show="headings", selectmode="extended")
        self.queue_tree.heading("original", text="Original Filename")
        self.queue_tree.heading("proposed", text="Proposed Filename")
        self.queue_tree.column("original", width=400, anchor="w")
        self.queue_tree.column("proposed", width=600, anchor="w")

        vsb = ttk.Scrollbar(frame, orient="vertical",
                            command=self.queue_tree.yview)
        hsb = ttk.Scrollbar(frame, orient="horizontal",
                            command=self.queue_tree.xview)
        self.queue_tree.configure(yscrollcommand=vsb.set,
                                  xscrollcommand=hsb.set)

        self.queue_tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(0, weight=1)

    # ------------------------------------------------------------------
    #  build proposed filename (unchanged)
    # ------------------------------------------------------------------
    def _build_proposed_name(self, md):
        year, month, day = md.get("year", ""), md.get("month", ""), md.get("day", "")
        date_str = f"{year}-{month.zfill(2)}-{day.zfill(2)}" if (year and month and day) else ""

        name = self.naming_scheme
        name = name.replace("ARTIST", md.get("artist", ""))
        name = name.replace("VENUE",  md.get("venue",  ""))
        name = name.replace("DATE",   date_str)
        name = name.replace("CITY",   md.get("city",   ""))
        name = name.replace("[FORMAT]",     f"[{md.get('format','')}]"     if md.get("format")     else "")
        name = name.replace("[ADDITIONAL]", f"[{md.get('additional','')}]" if md.get("additional") else "")
        name = " ".join(name.split()).strip()
        for sep in (" - ", "--", "- -"):
            if name.startswith(sep): name = name[len(sep):]
            if name.endswith(sep):   name = name[:-len(sep)]
        return name

    def askstring_focused(self, title: str, prompt: str, parent) -> str | None:
        dialog = tk.Toplevel(parent)
        dialog.title(title)
        dialog.transient(parent)
        dialog.grab_set()

        # Create label and entry
        tk.Label(dialog, text=prompt).pack(padx=10, pady=(10, 0))
        entry_var = tk.StringVar()
        entry = tk.Entry(dialog, textvariable=entry_var)
        entry.pack(padx=10, pady=10)
        entry.focus_set()

        # Buttons frame
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

        # Bind Enter key to OK button action
        entry.bind("<Return>", lambda event: on_ok())

        # --- Center the dialog over parent ---
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

    def open_alias_editor(self):
        """GUI editor for managing artist aliases."""
        win = tk.Toplevel(self)
        win.title("Edit Artist Aliases")
        win.geometry("400x300")
        win.transient(self)
        win.grab_set()

        # ── Treeview to show alias -> full name ──
        tree = ttk.Treeview(win, columns=("Alias", "FullName"), show="headings")
        tree.heading("Alias", text="Alias")
        tree.heading("FullName", text="Full Artist Name")
        tree.pack(fill="both", expand=True, padx=10, pady=10)


        def refresh_tree():
            tree.delete(*tree.get_children())
            for alias, full in self.artist_aliases.items():
                tree.insert("", "end", values=(alias, full))

        def add_alias():
            win.focus_set()
            win.lift()
            alias = simpledialog.askstring("New Alias", "Enter alias:", parent=win)
            if not alias:
                return
            win.focus_set()
            win.lift()
            full = self.askstring_focused("Full Artist Name", "Enter full artist name:", win)
            if not full:
                return
            self.artist_aliases[alias.strip()] = full.strip()
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
            # Update dict safely
            if alias != new_alias:
                if alias in self.artist_aliases:
                    del self.artist_aliases[alias]
            self.artist_aliases[new_alias.strip()] = new_full.strip()
            refresh_tree()

        def delete_selected():
            selected = tree.selection()
            if not selected:
                messagebox.showinfo("Delete Alias", "No alias selected.", parent=win)
                return
            alias = tree.item(selected[0])["values"][0]
            if messagebox.askyesno("Confirm Delete", f"Delete alias '{alias}'?", parent=win):
                if alias in self.artist_aliases:
                    del self.artist_aliases[alias]
                refresh_tree()

        def save_and_close():
            self._log("✅ Artist aliases updated.")
            win.destroy()


        # ── Buttons ──
        btns = ttk.Frame(win)
        btns.pack(pady=5)

        ttk.Button(btns, text="Add", width=10, command=add_alias).grid(row=0, column=0, padx=5)
        ttk.Button(btns, text="Edit", width=10, command=edit_selected).grid(row=0, column=1, padx=5)
        ttk.Button(btns, text="Delete", width=10, command=delete_selected).grid(row=0, column=2, padx=5)
        ttk.Button(btns, text="Done", width=10, command=save_and_close).grid(row=0, column=3, padx=5)

        refresh_tree()

        # --- Center the alias editor window relative to parent ---
        self.update_idletasks()
        win.update_idletasks()

        parent_x = self.winfo_rootx()
        parent_y = self.winfo_rooty()
        parent_width = self.winfo_width()
        parent_height = self.winfo_height()

        win_width = win.winfo_width()
        win_height = win.winfo_height()

        x = parent_x + (parent_width // 2) - (win_width // 2)
        y = parent_y + (parent_height // 2) - (win_height // 2)

        win.geometry(f"{win_width}x{win_height}+{x}+{y}")

        win.focus_set()
        win.lift()

        # Bind Enter to add_alias function
        win.bind("<Return>", lambda event: add_alias())

    # ──────────────────────────────────────────────────────────────
    #  Refresh metadata lists from text files in assets/
    # ──────────────────────────────────────────────────────────────
    def _reload_metadata(self):
        from utils.text_utils import normalize_name

        def read_txt_lines(filename):
            try:
                with open(os.path.join(self.assets_dir, filename), "r", encoding="utf-8") as f:
                    return [line.strip() for line in f if line.strip()]
            except Exception as e:
                self._log(f"Error reading {filename}: {e}")
                return []

        # 1. Re-read all metadata files
        artist_list = read_txt_lines("Artists.txt")
        city_list   = read_txt_lines("Cities.txt")
        venue_list  = read_txt_lines("Venues.txt")

        # 2. Update internal dictionaries
        self.artist = {normalize_name(a): a for a in artist_list}
        self.city   = {normalize_name(c): c for c in city_list}
        self.venue  = {normalize_name(v): v for v in venue_list}

        # 4. Update dropdowns
        self.cb_artist["values"] = artist_list
        self.cb_city["values"]   = city_list
        self.cb_venue["values"]  = venue_list

        # 5. Clear invalid selections
        if self.v_artist.get() not in artist_list:
            self.v_artist.set("")
        if self.v_city.get() not in city_list:
            self.v_city.set("")
        if self.v_venue.get() not in venue_list:
            self.v_venue.set("")

        self._log("Reference metadata refreshed from text files.")


        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------
    #  save‑on‑exit
    # ------------------------------------------------------------------
    def _on_close(self):
        try:
            # Ensure 'Settings' section exists
            if not self.config_parser.has_section("Settings"):
                self.config_parser.add_section("Settings")

            # Save naming_scheme as JSON string
            self.config_parser.set(
                "Settings",
                "naming_scheme",
                json.dumps(self.naming_scheme, ensure_ascii=False)
            )

            # Save or remove output_folder option
            if self.output_dir.get():
                self.config_parser.set("Settings", "output_folder", self.output_dir.get())
            elif self.config_parser.has_option("Settings", "output_folder"):
                self.config_parser.remove_option("Settings", "output_folder")

            # Write config file
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                self.config_parser.write(f)

            self._log("Configuration saved on exit.")

            # Save artist aliases JSON
            aliases_path = ASSETS_DIR / "artist_aliases.json"
            try:
                with open(aliases_path, "w", encoding="utf-8") as f:
                    json.dump(self.artist_aliases, f, indent=2, ensure_ascii=False)
                self._log(f"Saved {len(self.artist_aliases)} artist aliases on exit.")
            except Exception as e:
                self._log(f"Failed to save artist aliases on exit: {e}")
                logger.exception(e)

        except Exception as e:
            self._log(f"Failed to save configuration on exit: {e}")
            logger.exception(e)
        finally:
            self.destroy()

# ----------------------------------------------------------------------
if __name__ == "__main__":
    create_missing_txt_files(ASSETS_DIR, ["Artists.txt", "Cities.txt", "Venues.txt"])
    # stop duplicate console logging
    logging.getLogger("vidforge").propagate     = False
    logging.getLogger("vidforge.app").propagate = False

    app = VideoTagger()
    app.mainloop()